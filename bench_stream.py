#!/usr/bin/env python3
"""bench_stream.py — 流式重测：wall / TTFT / 输出 token / token-s，90 组全并发。

背景：bench_speed.py 只记了 wall+字符数，TTFT/token 需要逐行到达时间戳，
本轮 stdout 全程 pipe+打点，每任务事件落盘 events/，可审计。

- opencode：--format json；TTFT=首个 type=text 事件到达；token=step-finish.tokens
  （实测 opencode text 事件整块到达，TTFT≈wall，如实记录）。
- grok：--output-format streaming-messages-json --include-partial-messages；
  TTFT=首个内容行到达；token=事件流里 output/completion_tokens 正则。
- codex：exec --json；同上通用规则。
- token/s = out_tokens/(wall-TTFT)；chars/s 恒有；token 拿不到记 null。

用法：
  python3 bench_stream.py --dry-run
  nohup python3 bench_stream.py > runs/stream_<stamp>.log 2>&1 &
  python3 bench_stream.py --groups ds-high --tiers short --reps 1 --workers 4
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from bench_speed import MATRIX, TIERS, load_prompt, find_bin  # noqa: E402

RE_OUT = re.compile(r'"(?:output_tokens|outputTokens|completion_tokens)"\s*:\s*(\d+)')
RE_IN = re.compile(r'"(?:input_tokens|inputTokens|prompt_tokens|promptTokens)"\s*:\s*(\d+)')
RE_REASON = re.compile(r'"reasoning(?:_tokens|Tokens)?"\s*:\s*(\d+)')
CONTENT_HINTS = ('"text":', '"delta"', '"content":', '"message"', 'stream_event')


def run_stream(cmd: list[str], cwd: str, input_text: str | None, timeout: int) -> dict:
    """stdout 逐行打到达时间戳。返回 {wall, lines:[(t,line)], exit, stderr}。"""
    t0 = time.monotonic()
    lines: list[tuple[float, str]] = []
    err_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False, encoding="utf-8") as ef:
            err_path = ef.name
        with open(err_path, "w", encoding="utf-8") as errf:
            proc = subprocess.Popen(cmd, cwd=cwd,
                                    stdin=subprocess.PIPE if input_text else subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=errf, text=True, bufsize=1)
            if input_text and proc.stdin:
                try:
                    proc.stdin.write(input_text)
                    proc.stdin.close()
                except (BrokenPipeError, OSError):
                    pass

            def reader() -> None:
                assert proc.stdout is not None
                for line in proc.stdout:
                    lines.append((round(time.monotonic() - t0, 3), line.rstrip("\n")))

            th = threading.Thread(target=reader, daemon=True)
            th.start()
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=30)
                return {"wall": round(time.monotonic() - t0, 3), "lines": lines,
                        "exit": -1, "error": f"timed out after {timeout}s"}
            th.join(timeout=15)
            wall = round(time.monotonic() - t0, 3)
            err = Path(err_path).read_text(encoding="utf-8", errors="replace")[-500:] if err_path else ""
            return {"wall": wall, "lines": lines, "exit": proc.returncode, "error": err}
    finally:
        if err_path:
            try:
                os.unlink(err_path)
            except OSError:
                pass


def scan_usage(lines: list[tuple[float, str]]) -> dict:
    """通用 token 扫描：opencode 精确路径优先，其余正则兜底。"""
    out = {"out_tokens": None, "in_tokens": None, "reasoning_tokens": None, "cost": None}
    for _, line in lines:
        try:
            o = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            o = None
        if isinstance(o, dict):
            part = o.get("part") if isinstance(o.get("part"), dict) else o
            if isinstance(part, dict) and o.get("type") in ("step-finish", "step_finish"):
                toks = part.get("tokens") or {}
                if isinstance(toks, dict):
                    out["out_tokens"] = toks.get("output", out["out_tokens"])
                    out["in_tokens"] = toks.get("input", out["in_tokens"])
                    out["reasoning_tokens"] = toks.get("reasoning", out["reasoning_tokens"])
                if part.get("cost") is not None:
                    out["cost"] = part.get("cost")
        m = RE_OUT.search(line)
        if m:
            out["out_tokens"] = int(m.group(1))
        m = RE_IN.search(line)
        if m:
            out["in_tokens"] = int(m.group(1))
        m = RE_REASON.search(line)
        if m and out["reasoning_tokens"] is None:
            out["reasoning_tokens"] = int(m.group(1))
    return out


def first_text_time(channel: str, lines: list[tuple[float, str]]) -> tuple[float | None, str]:
    """TTFT：opencode 用 type=text 事件；grok/codex 用内容行启发式。"""
    if channel == "opencode":
        for t, line in lines:
            try:
                o = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(o, dict) and o.get("type") == "text":
                return t, "opencode:text-event"
        return None, "opencode:no-text-event"
    for t, line in lines:
        if any(h in line for h in CONTENT_HINTS):
            return t, "heuristic:content-line"
    if lines:
        return lines[0][0], "fallback:first-line"
    return None, "no-lines"


def extract_text(channel: str, lines: list[tuple[float, str]]) -> str:
    texts: list[str] = []
    for _, line in lines:
        try:
            o = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            if channel != "opencode":
                texts.append(line)
            continue
        if not isinstance(o, dict):
            continue
        part = o.get("part")
        if o.get("type") == "text" and isinstance(part, dict) and part.get("text"):
            texts.append(part["text"])
        elif o.get("type") == "item.completed" and isinstance(o.get("item"), dict):
            v = o["item"].get("text")
            if isinstance(v, str) and v:
                texts.append(v)
        elif o.get("type") == "result" and isinstance(o.get("result"), str):
            texts.append(o["result"])
        elif channel in ("grok", "codex"):
            for key in ("text", "delta", "content"):
                v = o.get(key)
                if isinstance(v, str) and v:
                    texts.append(v)
    return "\n".join(texts)


def build_cmd(channel: str, model: str, effort: str, prompt: str, cwd: str) -> tuple[list[str], str | None]:
    if channel == "opencode":
        b = find_bin("OPENCODE_BIN", "opencode")
        return [b, "run", "--format", "json", "--dir", cwd, "--variant", effort, "-m", model, prompt], None
    if channel == "grok":
        b = find_bin("GROK_BIN", "grok")
        pf = os.path.join(cwd, "prompt.md")
        with open(pf, "w", encoding="utf-8") as f:
            f.write(prompt)
        return [b, "--output-format", "streaming-messages-json", "--include-partial-messages",
                "-m", model, "--effort", effort, "--always-approve", "--cwd", cwd,
                "--prompt-file", pf], None
    b = find_bin("CODEX_BIN", "codex")
    return [b, "exec", "--json", "--skip-git-repo-check", "--sandbox", "read-only",
            "-C", cwd, "-c", f'model_reasoning_effort="{effort}"', "-m", model, "-"], prompt


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="流式重测 wall/TTFT/token/token-s")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--groups", default="")
    ap.add_argument("--tiers", default="long")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--timeout-sec", type=int, default=600)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--stagger-sec", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-shuffle", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--only", default="",
                    help="定向补跑，格式 gid:tier:rep,...（如 ds-max:medium:1,gm-high:long:2）")
    args = ap.parse_args(argv)

    groups = [g for g in MATRIX if not args.groups or g["id"] in args.groups.split(",")]
    tiers = [t for t in args.tiers.split(",") if t in TIERS]
    jobs = [(g, t, rep) for g in groups for t in tiers for rep in range(1, args.reps + 1)]
    if args.only:
        want = set()
        for spec in args.only.split(","):
            gid, tier, rep = spec.strip().split(":")
            want.add((gid, tier, int(rep)))
        jobs = [(g, t, rep) for (g, t, rep) in jobs if (g["id"], t, rep) in want]
        if not jobs:
            print("error: --only 无匹配", file=sys.stderr)
            return 2
    if not args.no_shuffle:
        random.Random(args.seed).shuffle(jobs)
    workers = args.workers if args.workers > 0 else len(jobs)
    print(f"jobs={len(jobs)} workers={workers}")
    if args.dry_run:
        return 0

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = Path(args.out).resolve() if args.out else (HERE / "runs" / f"stream-{stamp}")
    events_dir = run_dir / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    work_root = run_dir / "work"
    for (g, t, rep, *_) in jobs:
        (work_root / f"{g['id']}_{t}_rep{rep}").mkdir(parents=True, exist_ok=True)
    results_path = run_dir / "results.jsonl"
    lock = threading.Lock()
    status = {"rc": 0}

    def run_one(idx: int, total: int, g: dict, tier: str, rep: int) -> None:
        tag = f"{g['id']}_{tier}_rep{rep}"
        cwd = run_dir / "work" / tag
        cwd.mkdir(parents=True, exist_ok=True)
        prompt = load_prompt(tier)
        with lock:
            print(f"[{idx}/{total}] {tag} ...", flush=True)
        cmd, stdin_text = build_cmd(g["channel"], g["model"], g["effort"], prompt, str(cwd))
        if not cmd[0]:
            rec = {"group": g["id"], "tier": tier, "rep": rep, "ok": False,
                   "error": f"{g['channel']} binary not found"}
        else:
            r = run_stream(cmd, str(cwd), stdin_text, args.timeout_sec)
            with open(events_dir / f"{tag}.jsonl", "w", encoding="utf-8") as f:
                for t, line in r["lines"]:
                    f.write(json.dumps({"t": t, "line": line}, ensure_ascii=False) + "\n")
            ttft, method = first_text_time(g["channel"], r["lines"])
            usage = scan_usage(r["lines"])
            text = extract_text(g["channel"], r["lines"])
            wall = r["wall"]
            # e2e 口径（out/wall，含等待）；增量窗口 tps 由 rescan_stream.py 离线算
            tps = round(usage["out_tokens"] / wall, 1) if usage["out_tokens"] and wall > 0 else None
            rec = {"group": g["id"], "channel": g["channel"], "model": g["model"],
                   "effort": g["effort"], "tier": tier, "rep": rep,
                   "wall_sec": wall, "ttft_sec": ttft, "ttft_method": method,
                   "out_tokens": usage["out_tokens"], "in_tokens": usage["in_tokens"],
                   "reasoning_tokens": usage["reasoning_tokens"], "cost": usage["cost"],
                   "tps": tps, "output_chars": len(text),
                   "chars_per_sec": round(len(text) / wall, 1) if wall > 0 else None,
                   "n_events": len(r["lines"]), "exit_code": r["exit"],
                   "ok": r["exit"] == 0 and bool(text.strip()),
                   "error": "" if r["exit"] == 0 else (r.get("error") or f"exit {r['exit']}")[:200]}
        with lock:
            with open(results_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"  -> {tag} ok={rec['ok']} wall={rec.get('wall_sec')}s "
                  f"ttft={rec.get('ttft_sec')}s out_tok={rec.get('out_tokens')} "
                  f"tps={rec.get('tps')} {rec.get('error','')[:100]}", flush=True)
            if not rec["ok"]:
                status["rc"] = 1

    try:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = []
            for i, (g, t, rep) in enumerate(jobs, 1):
                futs.append(ex.submit(run_one, i, len(jobs), g, t, rep))
                time.sleep(args.stagger_sec)
            for fu in futs:
                fu.result()
    except KeyboardInterrupt:
        print("\n[interrupt] 部分结果已落盘", flush=True)
        return 130

    recs = [json.loads(l) for l in open(results_path, encoding="utf-8")]
    cells = {}
    for r in recs:
        cells.setdefault((r["group"], r["tier"]), []).append(r)
    mlines = ["# stream 汇总（中位数）", "",
              "| group | tier | wall | ttft | out_tok | tps | chars/s | n |",
              "|---|---|---|---|---|---|---|---|"]
    for (gid, tier) in sorted(cells):
        rs = cells[(gid, tier)]
        med = lambda k: round(statistics.median([x[k] for x in rs if x[k] is not None]), 1) \
            if any(x[k] is not None for x in rs) else None
        mliness = [gid, tier, med("wall_sec"), med("ttft_sec"), med("out_tokens"),
                   med("tps"), med("chars_per_sec"), f"{sum(1 for x in rs if x['ok'])}/{len(rs)}"]
        mlines.append("| " + " | ".join(str(v) for v in mliness) + " |")
    (run_dir / "summary.md").write_text("\n".join(mlines) + "\n", encoding="utf-8")
    print(f"\n结果目录：{run_dir}")
    print("\n".join(mlines))
    return status["rc"]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
