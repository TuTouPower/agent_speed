#!/usr/bin/env python3
"""bench_ctx.py — 长输入档基准：fixture(1k/10k/100k/300k) + 任务 prompt，自然输出。

复用 bench_stream.run_stream 做流式采集，复用 rescan_stream.PARSERS 解析。
输入通道：opencode 经 `-f <fixture>` 附件（message 必须在 -f 之前）；
grok 经 --prompt-file（任务+fixture 拼一份临时文件）；
codex 经 stdin（任务+fixture）。
输出不限制，只记录。

用法：
  python3 bench_ctx.py --dry-run
  nohup python3 bench_ctx.py --fixture fixtures/input_300k.txt --task fixtures/task_ctx.md --tier ctx300k > runs/ctx.log 2>&1 &
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from bench_speed import MATRIX, find_bin  # noqa: E402
from bench_stream import run_stream  # noqa: E402
from rescan_stream import PARSERS  # noqa: E402


def kimi_session_stats(workdir: str) -> dict:
    """从本地 session 落盘挖 token：按 workDir 匹配最新 session，汇总 step.end。
    返回 {in_tokens, out_tokens, srv_ttft_ms, srv_decode_ms}，找不到全 None。"""
    blank = {"in_tokens": None, "out_tokens": None, "srv_ttft_ms": None, "srv_decode_ms": None}
    try:
        idx = Path.home() / ".kimi-code" / "session_index.jsonl"
        cands = []
        for line in idx.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if o.get("workDir") == workdir:
                cands.append(o)
        if not cands:
            return blank
        wire = Path(cands[-1]["sessionDir"]) / "agents" / "main" / "wire.jsonl"
        tin = tou = dec = 0
        first_ttft = None
        for line in wire.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if (isinstance(o, dict) and o.get("type") == "context.append_loop_event"
                    and isinstance(o.get("event"), dict)
                    and o["event"].get("type") == "step.end"):
                e = o["event"]
                u = e.get("usage") or {}
                tin += u.get("inputOther", 0) + u.get("inputCacheRead", 0) + u.get("inputCacheCreation", 0)
                tou += u.get("output", 0)
                if e.get("llmServerDecodeMs"):
                    dec += e["llmServerDecodeMs"]
                if first_ttft is None and e.get("llmServerFirstTokenMs") is not None:
                    first_ttft = e["llmServerFirstTokenMs"]
        return {"in_tokens": tin or None, "out_tokens": tou or None,
                "srv_ttft_ms": first_ttft, "srv_decode_ms": dec or None}
    except OSError:
        return blank


def parse_kimi(lines):
    """kimi stream-json 通用解析：首个长行到达为 TTFT；usage 走通用正则。"""
    from bench_stream import scan_usage
    raw = [(t, o if isinstance(o, str) else json.dumps(o, ensure_ascii=False)) for t, o in lines]
    ttft = None
    for t, s in raw:
        if len(s) > 100:
            ttft = t
            break
    if ttft is None and raw:
        ttft = raw[0][0]
    usage = scan_usage(raw)
    texts = []
    for _, o in lines:
        if isinstance(o, dict):
            for key in ("text", "content", "delta", "message", "result"):
                v = o.get(key)
                if isinstance(v, str) and len(v) > 20:
                    texts.append(v)
    return ttft, "heuristic", "\n".join(texts), \
        {"out": usage["out_tokens"], "in": usage["in_tokens"],
         "rea": usage["reasoning_tokens"], "cost": usage["cost"]}, None


def server_window(channel: str, lines) -> float | None:
    if channel == "opencode":
        for t, o in lines:
            if isinstance(o, dict) and o.get("type") == "text":
                tm = (o.get("part") or {}).get("time") or {}
                if tm.get("start") and tm.get("end") and tm["end"] > tm["start"]:
                    return (tm["end"] - tm["start"]) / 1000
        return None
    if channel == "grok":
        for t, o in lines:
            if isinstance(o, dict) and o.get("type") == "result" and o.get("duration_api_ms"):
                return o["duration_api_ms"] / 1000
        return None
    return None


def kimi_global_effort() -> str:
    """kimi 无 per-call 强度参数，读全局 [thinking] effort。"""
    import re
    p = Path.home() / ".kimi-code" / "config.toml"
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.search(r"\[thinking\][^\[]*?effort\s*=\s*\"([^\"]+)\"", text, re.S)
    return m.group(1) if m else ""


def build_cmd(channel: str, model: str, effort: str, task: str, fixture: Path,
                cwd: str, attach_dir: str = ""):
    if channel == "kimi":
        b = find_bin("KIMI_BIN", "kimi")
        prompt = (f"项目代码在文件 {fixture}（约300k token）。先用读文件工具完整读取"
                  f"该文件的全部内容，然后分析整体架构：分层与模块划分、核心模块及其职责、"
                  f"主要数据流向、关键技术选型。直接输出答案。")
        return [b, "-m", model, "-p", prompt, "--output-format", "stream-json"], None
    if channel == "opencode":
        b = find_bin("OPENCODE_BIN", "opencode")
        # message 必须在 -f 之前（-f 是 array，会吞掉后面参数）
        cmd = [b, "run", "--format", "json", "--dir", cwd,
               "--variant", effort, "-m", model, task]
        if attach_dir:
            for f in sorted(Path(attach_dir).glob("*")):
                if f.is_file():
                    cmd += ["-f", str(f.resolve())]
        else:
            cmd += ["-f", str(fixture)]
        return cmd, None
    if channel == "grok":
        b = find_bin("GROK_BIN", "grok")
        pf = Path(cwd) / "ctx_prompt.md"
        pf.write_text(task + "\n\n===== INPUT =====\n" + fixture.read_text(encoding="utf-8"),
                      encoding="utf-8")
        return [b, "--output-format", "streaming-messages-json", "--include-partial-messages",
                "-m", model, "--effort", effort, "--always-approve", "--cwd", cwd,
                "--prompt-file", str(pf)], None
    b = find_bin("CODEX_BIN", "codex")
    full = task + "\n\n===== INPUT =====\n" + fixture.read_text(encoding="utf-8")
    return [b, "exec", "--json", "--skip-git-repo-check", "--sandbox", "read-only",
            "-C", cwd, "-c", f'model_reasoning_effort="{effort}"', "-m", model, "-"], full


ALIAS_MAP: dict[str, list[str]] = {
    "mimo": ["mf-high", "mp-high"],
    "mimo-flash": ["mf-high"],
    "mimo-pro": ["mp-high"],
    "mimo-flash-high": ["mf-high"],
    "mimo-pro-high": ["mp-high"],
    "grok-4.7": ["g47-xhigh"],
    "grok47": ["g47-xhigh"],
    "g47": ["g47-xhigh"],
    "grok-4.7-fast": ["g47f-high", "g47f-xhigh"],
    "g47f": ["g47f-high", "g47f-xhigh"],
    "g47-fast": ["g47f-high", "g47f-xhigh"],
    "fast": ["g47f-high", "g47f-xhigh"],
}


def main(argv: list[str]) -> int:
    default_fixture = HERE / "fixtures" / "input_300k.txt"
    default_task = HERE / "fixtures" / "task_ctx.md"
    default_chunks = HERE / "fixtures" / "chunks_300k"

    ap = argparse.ArgumentParser(description="长输入档基准")
    ap.add_argument("--fixture", default=str(default_fixture),
                    help="长输入文本 fixture（默认 fixtures/input_300k.txt）")
    ap.add_argument("--attach-dir", default="",
                    help="opencode 用：目录内文件逐个 -f 附件（默认自动探测 fixtures/chunks_300k）")
    ap.add_argument("--task", default=str(default_task),
                    help="任务 prompt（默认 fixtures/task_ctx.md）")
    ap.add_argument("--tier", default="ctx300k")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--groups", default="",
                    help="模型组列表，支持别名如 mimo、mf-high、mp-high 等")
    ap.add_argument("--mimo", action="store_true",
                    help="快捷模式：只测 opencode MIMO 2.6 flash 与 pro (300k)")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--timeout-sec", type=int, default=1200)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--stagger-sec", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-shuffle", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    if args.mimo:
        args.groups = "mf-high,mp-high"

    target_groups: set[str] = set()
    if args.groups:
        for item in args.groups.split(","):
            item = item.strip()
            if not item:
                continue
            if item in ALIAS_MAP:
                target_groups.update(ALIAS_MAP[item])
            else:
                target_groups.add(item)

    groups = [g for g in MATRIX if not target_groups or g["id"] in target_groups]

    # 若未手动指定 attach_dir，且存在 chunks 目录且涉及 opencode，默认走分块规避 50KB 截断
    attach_dir = args.attach_dir
    if not attach_dir and default_chunks.is_dir() and any(g["channel"] == "opencode" for g in groups):
        attach_dir = str(default_chunks.resolve())

    fixture = Path(args.fixture).resolve()
    task = Path(args.task).read_text(encoding="utf-8")
    jobs = [(g, args.tier, rep) for g in groups for rep in range(1, args.reps + 1)]
    if not args.no_shuffle:
        random.Random(args.seed).shuffle(jobs)
    workers = args.workers if args.workers > 0 else len(jobs)
    print(f"jobs={len(jobs)} workers={workers} fixture={fixture} ({fixture.stat().st_size} bytes)")
    if attach_dir:
        print(f"attach_dir={attach_dir}")
    if args.dry_run:
        for g, t, rep in jobs:
            print(f"  {g['id']:<10} {t} rep{rep}")
        return 0

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = Path(args.out).resolve() if args.out else (HERE / "runs" / f"ctx-{stamp}")
    events_dir = run_dir / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    work_root = run_dir / "work"
    for (g, t, rep) in jobs:
        (work_root / f"{g['id']}_{t}_rep{rep}").mkdir(parents=True, exist_ok=True)
    results_path = run_dir / "results.jsonl"
    lock = threading.Lock()
    status = {"rc": 0}

    def run_one(idx: int, total: int, g: dict, tier: str, rep: int) -> None:
        tag = f"{g['id']}_{tier}_rep{rep}"
        cwd = str(work_root / tag)
        with lock:
            print(f"[{idx}/{total}] {tag} ...", flush=True)
        cmd, stdin_text = build_cmd(g["channel"], g["model"], g["effort"], task, fixture, cwd,
                                    attach_dir)
        if g["channel"] == "kimi" and g["effort"] != kimi_global_effort():
            with lock:
                print(f"[{idx}/{total}] {tag} SKIP（全局 effort={kimi_global_effort()} "
                      f"≠ 任务 {g['effort']}，拒绝瞎标）", flush=True)
            return
        if not cmd[0]:
            rec = {"group": g["id"], "tier": tier, "rep": rep, "ok": False,
                   "error": f"{g['channel']} binary not found"}
        else:
            r = run_stream(cmd, cwd, stdin_text, args.timeout_sec)
            parsed = []
            with open(events_dir / f"{tag}.jsonl", "w", encoding="utf-8") as f:
                for t, line in r["lines"]:
                    f.write(json.dumps({"t": t, "line": line}, ensure_ascii=False) + "\n")
                    try:
                        o = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        o = None
                    parsed.append((t, o))
            if g["channel"] == "kimi":
                ttft, kind, text, usage, _ = parse_kimi(parsed)
                ks = kimi_session_stats(cwd)
                if ks["out_tokens"]:
                    usage = {"out": ks["out_tokens"], "in": ks["in_tokens"],
                             "rea": None, "cost": None}
                kimi_srv_tps = (round(ks["out_tokens"] / (ks["srv_decode_ms"] / 1000), 1)
                                if ks["out_tokens"] and ks["srv_decode_ms"] else None)
            else:
                ttft, kind, text, usage, _ = PARSERS[g["channel"]](parsed)
                kimi_srv_tps = None
            win = server_window(g["channel"], parsed)
            wall = r["wall"]
            out = usage["out"]
            if g["channel"] == "opencode" and win and out:
                tps, tps_kind, tps_srv = round(out / win, 1), "srv", round(out / win, 1)
            elif g["channel"] == "kimi" and kimi_srv_tps:
                tps, tps_kind, tps_srv = kimi_srv_tps, "srv", kimi_srv_tps
            elif g["channel"] == "grok":
                last = max([t for t, o in parsed if isinstance(o, dict)
                            and o.get("type") == "stream_event"
                            and (o.get("event") or {}).get("type") == "content_block_delta"], default=None)
                tps_stream = round(out / (last - ttft), 1) if out and ttft and last and last > ttft else None
                tps_srv = round(out / win, 1) if out and win else None
                tps, tps_kind = tps_stream, "stream"
            else:
                tps = round(out / wall, 1) if out and wall > 0 else None
                tps_kind, tps_srv = "e2e*", None
            rec = {"group": g["id"], "channel": g["channel"], "model": g["model"],
                   "effort": g["effort"], "tier": tier, "rep": rep,
                   "wall_sec": wall, "ttft_sec": ttft, "ttft_kind": kind,
                   "out_tokens": out, "in_tokens": usage["in"],
                   "reasoning_tokens": usage["rea"], "tps": tps, "tps_kind": tps_kind,
                   "tps_srv": tps_srv, "output_chars": len(text),
                   "exit_code": r["exit"], "ok": r["exit"] == 0 and bool(text.strip()),
                   "error": "" if r["exit"] == 0 else (r.get("error") or "")[:200]}
        with lock:
            with open(results_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"  -> {tag} ok={rec['ok']} wall={rec.get('wall_sec')} "
                  f"ttft={rec.get('ttft_sec')} out={rec.get('out_tokens')} "
                  f"tps={rec.get('tps')}({rec.get('tps_kind')}) srv={rec.get('tps_srv')} "
                  f"{rec.get('error','')[:80]}", flush=True)
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
        print("\n[interrupt]", flush=True)
        return 130
    print(f"\n结果目录：{run_dir}")
    return status["rc"]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
