#!/usr/bin/env python3
"""merge_final.py — 合并基准数据，输出最终分档原始表。

输入：
  runs/stream-20260919-035923/results_v2.jsonl（90 行，15 行截断坏行）
  runs/backfill-0919-0416/results_v2.jsonl（rescan_stream.py 生成，22 行）
  两处 events/（服务端窗口：opencode text.time；grok result.duration_api_ms）

规则：同 key 取 ok=True 者（backfill 优先）；tps 列=生成吞吐
（opencode=服务端窗口，grok=文本增量窗口，codex=端到端*）；
tps_srv 列=服务端口径（opencode=同tps，grok=api时长口径，codex=空）。
"""

import json
import sys
from pathlib import Path
from statistics import mean

BASE = Path("runs/stream-20260919-035923")
BACK = Path("runs/backfill-0919-0416")


def load_v2(p: Path):
    out = {}
    with open(p, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            out[(r["group"], r["tier"], r["rep"])] = r
    return out


def event_lines(events_dir: Path, key):
    p = events_dir / f"{key[0]}_{key[1]}_rep{key[2]}.jsonl"
    if not p.is_file():
        return []
    rows = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            try:
                o = json.loads(e["line"])
            except (json.JSONDecodeError, ValueError, TypeError):
                continue
            rows.append((e["t"], o))
    return rows


def server_window(channel, lines):
    """opencode: text.time 起止；grok: result.duration_api_ms；codex: 无。"""
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


def main() -> int:
    base = load_v2(BASE / "results_v2.jsonl")
    back = load_v2(BACK / "results_v2.jsonl")
    merged = dict(base)
    for k, r in back.items():
        if r["ok"] and (k not in merged or not merged[k]["ok"] or k in back):
            merged[k] = r
    # backfill ok 行无条件覆盖同 key（新捕获无截断）
    for k, r in back.items():
        if r["ok"]:
            merged[k] = r

    final = []
    for key in sorted(merged):
        r = merged[key]
        evdir = BACK / "events" if (BACK / "events" / f"{key[0]}_{key[1]}_rep{key[2]}.jsonl").is_file() \
            and key in back and back[key]["ok"] else BASE / "events"
        win = server_window(r["channel"], event_lines(evdir, key))
        tps_srv = round(r["out_tokens"] / win, 1) if win and r["out_tokens"] else None
        if r["channel"] == "opencode" and win and r["out_tokens"]:
            tps, kind = round(r["out_tokens"] / win, 1), "srv"
        elif r["channel"] == "grok":
            tps, kind = r["tps"], "stream"
        else:
            tps, kind = r["tps"], "e2e*"
        final.append({**r, "tps": tps, "tps_kind": kind, "tps_srv": tps_srv,
                      "srv_win_sec": round(win, 2) if win else None})

    with open("runs/final.jsonl", "w", encoding="utf-8") as f:
        for r in final:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    for tier in ("long", "medium", "short"):
        print(f"## {tier}")
        print(f"{'group':<10} {'rep':>3} {'wall':>8} {'ttft':>8} {'out':>6} "
              f"{'tps(kind)':>13} {'tps_srv':>8}")
        for r in [x for x in final if x["tier"] == tier]:
            print(f"{r['group']:<10} rep{r['rep']} {str(r['wall_sec']):>8} "
                  f"{str(r['ttft_sec']):>8} {str(r['out_tokens']):>6} "
                  f"{str(r['tps']):>7}({r['tps_kind']}) {str(r['tps_srv']):>8}")
        print()
    n_ok = sum(1 for r in final if r["ok"])
    n_ttft = sum(1 for r in final if r["ttft_sec"] is not None)
    n_srv = sum(1 for r in final if r["tps_srv"] is not None)
    print(f"共 {len(final)} 行：ok={n_ok} 有ttft={n_ttft} 有tps_srv={n_srv}")
    print("written: runs/final.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
