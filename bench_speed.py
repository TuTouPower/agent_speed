#!/usr/bin/env python3
"""bench_speed.py — 模型速度基准：opencode / grok / codex，10 组 x 3 档 prompt x 3 次，严格串行。

矩阵（见 MATRIX）：opencode-go/deepseek-v4.1-flash(high/max)、
opencode-go/muse-spark-1.3-contributor(high/xhigh)、cpa/gemini-3.8-flash(high)、
grok-4.5(high)、grok-4.6(xhigh)、gpt-5.6-luna(high/max)、gpt-6-astra(high)。

调用形状与 call_agents skill 的 agents_lib 一致，唯二偏离（见 README）：
- grok 直调二进制并透传 --effort（agents_lib.run_grok 暂不支持 effort）；
- codex 全部直调，luna-max 直传 max（绕开 call_agents 的 max->ultra 全局归一，
  luna 只支持到 max，无 ultra）。

用法：
  bench_speed.py --dry-run                 # 只打印矩阵与任务数，不调用
  bench_speed.py --step0                   # 每组 1 次最小 prompt，连通性+强度验收
  bench_speed.py --smoke                   # 第 1 组 x short x 1 次，全链路冒烟
  bench_speed.py                           # 全量 90 次，默认全部并发
  bench_speed.py --workers 1                 # 严格串行（测纯净单次速度）
  bench_speed.py --workers 10                # 限 10 并发（被限流时降档用）
  bench_speed.py --groups ds-high,gm-high --tiers short --reps 2

结果：<out>/<stamp>/results.jsonl（每 call 一行，实时追加）+ summary.json/md。
"""

from __future__ import annotations

import argparse
import json
import os
import random
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
PROMPTS_DIR = HERE / "prompts"

MATRIX = [
    {"id": "ds-high", "channel": "opencode", "model": "opencode-go/deepseek-v4.1-flash", "effort": "high"},
    {"id": "ds-max", "channel": "opencode", "model": "opencode-go/deepseek-v4.1-flash", "effort": "max"},
    {"id": "mu-high", "channel": "opencode", "model": "opencode-go/muse-spark-1.3-contributor", "effort": "high"},
    {"id": "mu-xhigh", "channel": "opencode", "model": "opencode-go/muse-spark-1.3-contributor", "effort": "xhigh"},
    {"id": "gm-high", "channel": "opencode", "model": "cpa/gemini-3.8-flash", "effort": "high"},
    {"id": "g45-high", "channel": "grok", "model": "grok-4.5", "effort": "high"},
    {"id": "g46-xhigh", "channel": "grok", "model": "grok-4.6", "effort": "xhigh"},
    {"id": "luna-high", "channel": "codex", "model": "gpt-5.6-luna", "effort": "high"},
    {"id": "luna-max", "channel": "codex", "model": "gpt-5.6-luna", "effort": "max"},
    {"id": "astra-high", "channel": "codex", "model": "gpt-6-astra", "effort": "high"},
    # 官方直连（key/URL 经 OPENCODE_CONFIG 临时配置，不进仓库，见 README）
    {"id": "dsoff-high", "channel": "opencode", "model": "ds-off/deepseek-flash", "effort": "high"},
    {"id": "dsoff-max", "channel": "opencode", "model": "ds-off/deepseek-flash", "effort": "max"},
]

TIERS = {
    "short": {"file": "short.md", "guard": (200, 4000)},
    "medium": {"file": "medium.md", "guard": (2000, 30000)},
    "long": {"file": "long.md", "guard": (5000, 60000)},
}

STEP0_PROMPT = "只回复两个字符：OK。不要调用任何工具，不要读写文件，不要执行命令。"


def find_bin(env_key: str, name: str) -> str | None:
    env_bin = os.environ.get(env_key)
    if env_bin and Path(env_bin).is_file():
        return env_bin
    return shutil.which(name)


def bin_version(binary: str) -> str:
    try:
        p = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=15)
        return (p.stdout or p.stderr or "").strip().splitlines()[0][:120]
    except Exception:
        return ""


def opencode_extract(jsonl_path: str) -> tuple[str, list[dict]]:
    """从 opencode --format json 事件流抽 text；附带权限受阻检测。"""
    texts: list[str] = []
    blocked: list[dict] = []
    try:
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                part = obj.get("part")
                if obj.get("type") == "text" and isinstance(part, dict):
                    t = part.get("text")
                    if t:
                        texts.append(t)
                if isinstance(part, dict) and part.get("type") == "tool":
                    state = part.get("state") or {}
                    if state.get("status") == "error":
                        err = str(state.get("error") or "")
                        if "permission" in err.lower() or "rejected" in err.lower():
                            tool_input = state.get("input") or {}
                            path = tool_input.get("filePath") or tool_input.get("path") or tool_input.get("command") or ""
                            blocked.append({"tool": str(part.get("tool") or ""), "path": str(path), "error": err[:300]})
    except OSError:
        pass
    return "\n".join(texts), blocked


def run_opencode(model: str, effort: str, prompt: str, cwd: str, timeout: int) -> dict:
    binary = find_bin("OPENCODE_BIN", "opencode")
    if not binary:
        return {"ok": False, "text": "", "exit_code": -1, "error": "opencode binary not found"}
    fd, jsonl_path = tempfile.mkstemp(suffix=".jsonl", prefix="bench_opencode_")
    os.close(fd)
    cmd = [binary, "run", "--format", "json", "--dir", cwd, "--variant", effort, "-m", model, prompt]
    t0 = time.monotonic()
    try:
        with open(jsonl_path, "w", encoding="utf-8") as out:
            proc = subprocess.run(cmd, cwd=cwd, stdout=out, text=True, timeout=timeout,
                                  stderr=subprocess.PIPE)
        elapsed = time.monotonic() - t0
        text, blocked = opencode_extract(jsonl_path)
        err = (proc.stderr or "")[-1000:]
        if blocked:
            return {"ok": False, "text": text, "exit_code": proc.returncode,
                    "elapsed_sec": elapsed, "error": f"permission blocked: {blocked[0]}", "blocked": blocked}
        return {"ok": proc.returncode == 0 and bool(text.strip()), "text": text,
                "exit_code": proc.returncode, "elapsed_sec": elapsed,
                "error": "" if proc.returncode == 0 else f"exit {proc.returncode}: {err[:300]}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "text": "", "exit_code": -1,
                "elapsed_sec": time.monotonic() - t0, "error": f"timed out after {timeout}s"}
    finally:
        try:
            os.unlink(jsonl_path)
        except OSError:
            pass


def run_grok(model: str, effort: str, prompt: str, cwd: str, timeout: int) -> dict:
    binary = find_bin("GROK_BIN", "grok")
    if not binary:
        return {"ok": False, "text": "", "exit_code": -1, "error": "grok binary not found"}
    fd, prompt_path = tempfile.mkstemp(suffix=".md", prefix="bench_grok_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(prompt)
        cmd = [binary, "--output-format", "plain", "-m", model, "--effort", effort,
               "--always-approve", "--cwd", cwd, "--prompt-file", prompt_path]
        t0 = time.monotonic()
        try:
            proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
            elapsed = time.monotonic() - t0
            text = proc.stdout or ""
            err = (proc.stderr or "")[-1000:]
            return {"ok": proc.returncode == 0 and bool(text.strip()), "text": text,
                    "exit_code": proc.returncode, "elapsed_sec": elapsed,
                    "error": "" if proc.returncode == 0 else f"exit {proc.returncode}: {err[:300]}"}
        except subprocess.TimeoutExpired:
            return {"ok": False, "text": "", "exit_code": -1,
                    "elapsed_sec": time.monotonic() - t0, "error": f"timed out after {timeout}s"}
    finally:
        try:
            os.unlink(prompt_path)
        except OSError:
            pass


def run_codex(model: str, effort: str, prompt: str, cwd: str, timeout: int) -> dict:
    binary = find_bin("CODEX_BIN", "codex")
    if not binary:
        return {"ok": False, "text": "", "exit_code": -1, "error": "codex binary not found"}
    cmd = [binary, "exec", "--skip-git-repo-check", "--sandbox", "read-only",
           "-C", cwd, "-c", f'model_reasoning_effort="{effort}"', "-m", model, "-"]
    t0 = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=cwd, input=prompt, capture_output=True, text=True, timeout=timeout)
        elapsed = time.monotonic() - t0
        text = proc.stdout or ""
        err = (proc.stderr or "")[-1000:]
        return {"ok": proc.returncode == 0 and bool(text.strip()), "text": text,
                "exit_code": proc.returncode, "elapsed_sec": elapsed,
                "error": "" if proc.returncode == 0 else f"exit {proc.returncode}: {err[:300]}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "text": "", "exit_code": -1,
                "elapsed_sec": time.monotonic() - t0, "error": f"timed out after {timeout}s"}


RUNNERS = {"opencode": run_opencode, "grok": run_grok, "codex": run_codex}


def load_prompt(tier: str) -> str:
    return (PROMPTS_DIR / TIERS[tier]["file"]).read_text(encoding="utf-8")


def summarize(records: list[dict]) -> dict:
    """按 组x档 统计：clean=成功且长度守卫内；计分用 rep>1（去 warmup），不足则全用。"""
    cells: dict[tuple[str, str], list[dict]] = {}
    for r in records:
        cells.setdefault((r["group"], r["tier"]), []).append(r)
    table = []
    for (gid, tier), rs in sorted(cells.items()):
        lo, hi = TIERS[tier]["guard"]
        for r in rs:
            n = r.get("output_chars", len(r.get("text", "")))
            r["in_guard"] = bool(r["ok"]) and lo <= n <= hi
        clean = [r for r in rs if r["in_guard"]]
        scored = [r for r in clean if r["rep"] > 1] or clean
        med = round(statistics.median([r["elapsed_sec"] for r in scored]), 1) if scored else None
        table.append({"group": gid, "tier": tier, "median_sec": med,
                      "n_clean": len(clean), "n_total": len(rs),
                      "all_sec": [round(r["elapsed_sec"], 1) for r in sorted(rs, key=lambda x: x["rep"])]})
    overall = []
    groups = sorted({t["group"] for t in table})
    for gid in groups:
        meds = [t["median_sec"] for t in table if t["group"] == gid and t["median_sec"] is not None]
        overall.append({"group": gid,
                        "score_sec": round(sum(meds) / len(meds), 1) if meds else None,
                        "tiers_hit": f"{len(meds)}/3"})
    overall.sort(key=lambda x: (x["score_sec"] is None, x["score_sec"] or 0))
    return {"cells": table, "overall": overall}


def write_summary(run_dir: Path, records: list[dict]) -> dict:
    summary = summarize(records)
    summary["generated_at"] = datetime.now(timezone.utc).isoformat()
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")
    lines = ["# bench_speed 汇总", ""]
    lines.append("overall（三档 median 均值，越小越快）：")
    lines.append("| rank | group | score_sec | tiers |")
    lines.append("|---|---|---|---|")
    for i, o in enumerate(summary["overall"], 1):
        lines.append(f"| {i} | {o['group']} | {o['score_sec']} | {o['tiers_hit']} |")
    lines += ["", "cells（median 为去 warmup 后 clean 样本中位数；all_sec 按 rep 顺序）：",
              "| group | tier | median_sec | n_clean/n_total | all_sec |",
              "|---|---|---|---|---|"]
    for c in summary["cells"]:
        lines.append(f"| {c['group']} | {c['tier']} | {c['median_sec']} | {c['n_clean']}/{c['n_total']} | {c['all_sec']} |")
    lines += ["", "注：n_clean < n_total 说明有失败/超时/长度越界样本，查 results.jsonl 的 error/in_guard。"]
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def print_summary(summary: dict) -> None:
    print("\n== overall ==")
    for i, o in enumerate(summary["overall"], 1):
        print(f"  {i}. {o['group']:<10} {o['score_sec']}s  (tiers {o['tiers_hit']})")
    print("== cells ==")
    for c in summary["cells"]:
        print(f"  {c['group']:<10} {c['tier']:<6} median={c['median_sec']}s  {c['n_clean']}/{c['n_total']}  {c['all_sec']}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="模型速度基准：10组 x 3档 x 3次，严格串行")
    ap.add_argument("--dry-run", action="store_true", help="只打印矩阵与任务数")
    ap.add_argument("--step0", action="store_true", help="每组 1 次最小 prompt，连通性验收")
    ap.add_argument("--smoke", action="store_true", help="第 1 组 x short x 1 次冒烟")
    ap.add_argument("--list", action="store_true", help="打印矩阵")
    ap.add_argument("--groups", default="", help="逗号分隔的 group id 子集")
    ap.add_argument("--tiers", default="short,medium,long", help="档位子集")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--timeout-sec", type=int, default=600)
    ap.add_argument("--gap-sec", type=float, default=5.0, help="仅串行模式有效")
    ap.add_argument("--workers", type=int, default=0, help="并发数；0=全部任务同时跑，1=严格串行")
    ap.add_argument("--stagger-sec", type=float, default=0.5, help="并发提交间隔，防本地服务惊群")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-shuffle", action="store_true")
    ap.add_argument("--out", default="", help="结果目录（缺省 bench_speed/runs/<stamp>）")
    args = ap.parse_args(argv)

    if args.list:
        for g in MATRIX:
            print(f"{g['id']:<10} {g['channel']:<8} {g['model']}  effort={g['effort']}")
        return 0

    groups = [g for g in MATRIX if not args.groups or g["id"] in args.groups.split(",")]
    if not groups:
        print("error: --groups 无匹配", file=sys.stderr)
        return 2
    tiers = [t for t in args.tiers.split(",") if t in TIERS]
    if not tiers:
        print("error: --tiers 无匹配", file=sys.stderr)
        return 2

    if args.smoke:
        jobs = [(groups[0], "short", 1, None)]
    elif args.step0:
        jobs = [(g, "step0", 1, STEP0_PROMPT) for g in groups]
    else:
        jobs = [(g, t, rep, None) for g in groups for t in tiers for rep in range(1, args.reps + 1)]
    if not args.no_shuffle and not (args.smoke or args.step0):
        rnd = random.Random(args.seed)
        rnd.shuffle(jobs)

    print(f"groups={len(groups)} tiers={tiers} jobs={len(jobs)} timeout={args.timeout_sec}s "
          f"workers={args.workers if args.workers > 0 else len(jobs)}")
    if args.dry_run:
        for g, t, rep, _ in jobs:
            print(f"  {g['id']:<10} {t:<6} rep{rep}  {g['channel']}/{g['model']} effort={g['effort']}")
        return 0

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = Path(args.out) if args.out else (HERE / "runs" / stamp)
    work_root = run_dir / "work"
    work_root.mkdir(parents=True, exist_ok=True)

    env = {}
    for key, name in (("OPENCODE_BIN", "opencode"), ("GROK_BIN", "grok"), ("CODEX_BIN", "codex")):
        b = find_bin(key, name)
        env[name] = {"binary": b or "", "version": bin_version(b) if b else ""}
    workers = args.workers if args.workers > 0 else len(jobs)
    meta = {"stamp": stamp, "seed": args.seed, "timeout_sec": args.timeout_sec,
            "gap_sec": args.gap_sec, "workers": workers, "reps": args.reps,
            "order": [f"{g['id']}/{t}/rep{rep}" for g, t, rep, _ in jobs],
            "matrix": MATRIX, "env": env,
            "started_at": datetime.now(timezone.utc).isoformat()}
    (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    results_path = run_dir / "results.jsonl"
    records: list[dict] = []
    if (run_dir / "results.jsonl").exists():
        with open(results_path, encoding="utf-8") as f:
            for line in f:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    done = {(r["group"], r["tier"], r["rep"]) for r in records}
    lock = threading.Lock()
    status = {"rc": 0}

    def run_one(idx: int, total: int, g: dict, tier: str, rep: int, override: str | None) -> None:
        key = (g["id"], tier, rep)
        with lock:
            if key in done:
                print(f"[{idx}/{total}] skip {g['id']}/{tier}/rep{rep}（已存在）", flush=True)
                return
            print(f"[{idx}/{total}] {g['id']}/{tier}/rep{rep}  {g['model']} effort={g['effort']} ...", flush=True)
        cwd = work_root / f"{g['id']}_{tier}_rep{rep}"
        cwd.mkdir(parents=True, exist_ok=True)
        prompt = override if override is not None else load_prompt(tier)
        res = RUNNERS[g["channel"]](g["model"], g["effort"], prompt, str(cwd), args.timeout_sec)
        rec = {"group": g["id"], "channel": g["channel"], "model": g["model"],
               "effort": g["effort"], "tier": tier, "rep": rep,
               "start_iso": datetime.now(timezone.utc).isoformat(),
               "elapsed_sec": round(res.get("elapsed_sec", -1), 1),
               "exit_code": res.get("exit_code", -1), "ok": bool(res.get("ok")),
               "output_chars": len(res.get("text", "")),
               "error": res.get("error", "") or "",
               "text": res.get("text", "")[:2000]}
        with lock:
            records.append(rec)
            with open(results_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"  -> {rec['group']}/{rec['tier']}/rep{rec['rep']} ok={rec['ok']} "
                  f"{rec['elapsed_sec']}s chars={rec['output_chars']} {rec['error'][:120]}", flush=True)
            if not rec["ok"]:
                status["rc"] = 1

    rc = 0
    try:
        if workers == 1:
            for i, (g, tier, rep, override) in enumerate(jobs, 1):
                run_one(i, len(jobs), g, tier, rep, override)
                if i < len(jobs):
                    time.sleep(args.gap_sec)
        else:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = []
                for i, (g, tier, rep, override) in enumerate(jobs, 1):
                    futures.append(ex.submit(run_one, i, len(jobs), g, tier, rep, override))
                    time.sleep(args.stagger_sec)
                for fu in futures:
                    fu.result()
        rc = status["rc"]
    except KeyboardInterrupt:
        print("\n[interrupt] 部分结果已落盘，生成当前汇总", flush=True)
        rc = 130
    tiered = [r for r in records if r["tier"] in TIERS]
    print(f"\n结果目录：{run_dir}")
    if tiered:
        summary = write_summary(run_dir, tiered)
        print_summary(summary)
    else:
        print("step0 完成：查 results.jsonl 确认每组 ok=true（连通 + 强度参数被接受）")
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
