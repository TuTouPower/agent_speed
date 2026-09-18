#!/usr/bin/env python3
"""rescan_stream.py — 离线重扫 bench_stream.py 落盘的 events/*.jsonl。

修正首轮扫描的 bug（opencode step_finish 下划线、grok/codex 文本路径），
不产生新 API 调用。输出 results_v2.jsonl + summary_v2.md，并打印原始表。

用法：python3 rescan_stream.py runs/stream-<stamp>
"""

import json
import statistics
import sys
from pathlib import Path


def parse_opencode(lines):
    ttft = None
    texts = []
    usage = {"out": None, "in": None, "rea": None, "cost": None}
    for t, o in lines:
        if not isinstance(o, dict):
            continue
        if o.get("type") == "text":
            if ttft is None:
                ttft = t
            part = o.get("part")
            if isinstance(part, dict) and part.get("text"):
                texts.append(part["text"])
        if o.get("type") in ("step_finish", "step-finish"):
            part = o.get("part") or {}
            toks = part.get("tokens") or {}
            usage = {"out": toks.get("output"), "in": toks.get("input"),
                     "rea": toks.get("reasoning"), "cost": part.get("cost")}
    return ttft, "text-event(整块到达)", "\n".join(texts), usage, None


def parse_grok(lines):
    ttft_think = ttft_text = last_text = None
    deltas = []
    usage = {"out": None, "in": None, "rea": None, "cost": None}
    full = ""
    for t, o in lines:
        if not isinstance(o, dict):
            continue
        if o.get("type") == "stream_event":
            e = o.get("event") or {}
            d = e.get("delta") or {}
            if e.get("type") == "content_block_delta":
                if d.get("type") == "thinking_delta":
                    if ttft_think is None:
                        ttft_think = t
                elif d.get("type") == "text_delta":
                    if ttft_text is None:
                        ttft_text = t
                    last_text = t
                    if isinstance(d.get("text"), str):
                        deltas.append(d["text"])
            if e.get("type") == "message_delta" and isinstance(e.get("usage"), dict):
                u = e["usage"]
                usage = {"out": u.get("output_tokens"), "in": u.get("input_tokens"),
                         "rea": None, "cost": None}
        elif o.get("type") == "result":
            u = o.get("usage") or {}
            usage = {"out": u.get("output_tokens", usage["out"]),
                     "in": u.get("input_tokens", usage["in"]),
                     "rea": None, "cost": o.get("total_cost_usd")}
            if isinstance(o.get("result"), str):
                full = o["result"]
    text = full or "".join(deltas)
    tps = None
    if usage["out"] and ttft_text is not None and last_text is not None and last_text > ttft_text:
        tps = round(usage["out"] / (last_text - ttft_text), 1)
    return ttft_text, "text-delta首达", text, usage, tps


def parse_codex(lines):
    ttft = None
    text = ""
    usage = {"out": None, "in": None, "rea": None, "cost": None}
    for t, o in lines:
        if not isinstance(o, dict):
            continue
        if o.get("type") == "item.completed":
            item = o.get("item") or {}
            if isinstance(item.get("text"), str):
                if ttft is None:
                    ttft = t
                text = item["text"]
        if o.get("type") == "turn.completed":
            u = o.get("usage") or {}
            usage = {"out": u.get("output_tokens"), "in": u.get("input_tokens"),
                     "rea": u.get("reasoning_output_tokens"), "cost": None}
    return ttft, "整消息到达(无流式增量)", text, usage, None


PARSERS = {"opencode": parse_opencode, "grok": parse_grok, "codex": parse_codex}


def main() -> int:
    run_dir = Path(sys.argv[1])
    events_dir = run_dir / "events"
    orig = {}
    with open(run_dir / "results.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            orig[(r["group"], r["tier"], r["rep"])] = r
    out = []
    for evf in sorted(events_dir.glob("*.jsonl")):
        tag = evf.stem
        gid, tier, rep = tag.rsplit("_rep", 1)[0].rsplit("_", 1)[0], None, None
        # tag 形如 <gid>_<tier>_rep<N>；gid 本身无下划线
        parts = tag.split("_")
        gid, tier, rep = parts[0], parts[1], int(parts[2].replace("rep", ""))
        o = orig.get((gid, tier, rep), {})
        channel = o.get("channel", "")
        lines = []
        with open(evf, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                try:
                    obj = json.loads(r["line"])
                except (json.JSONDecodeError, ValueError, TypeError):
                    obj = None
                lines.append((r["t"], obj))
        ttft, kind, text, usage, tps_stream = PARSERS[channel](lines)
        wall = o.get("wall_sec")
        tps = tps_stream
        tps_kind = "stream"
        if tps is None and usage["out"] and wall:
            tps = round(usage["out"] / wall, 1)
            tps_kind = "e2e"
        out.append({"group": gid, "channel": channel, "model": o.get("model"),
                    "effort": o.get("effort"), "tier": tier, "rep": rep,
                    "wall_sec": wall, "ttft_sec": ttft, "ttft_kind": kind,
                    "out_tokens": usage["out"], "in_tokens": usage["in"],
                    "reasoning_tokens": usage["rea"], "cost_usd": usage["cost"],
                    "tps": tps, "tps_kind": tps_kind,
                    "output_chars": len(text), "exit_code": o.get("exit_code"),
                    "ok": o.get("exit_code") == 0 and bool(text.strip())})
    out.sort(key=lambda r: (r["group"], r["tier"], r["rep"]))
    with open(run_dir / "results_v2.jsonl", "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    cells = {}
    for r in out:
        cells.setdefault((r["group"], r["tier"]), []).append(r)
    ml = ["# stream v2 汇总（中位数；tps_kind: stream=增量窗口，e2e=out/wall）", "",
          "| group | tier | wall | ttft | out_tok | tps(tps_kind) | n |",
          "|---|---|---|---|---|---|---|"]
    for (gid, tier) in sorted(cells):
        rs = cells[(gid, tier)]
        def med(k):
            vs = [x[k] for x in rs if x[k] is not None]
            return round(statistics.median(vs), 1) if vs else None
        kinds = {x["tps_kind"] for x in rs if x["tps"] is not None}
        ml.append(f"| {gid} | {tier} | {med('wall_sec')} | {med('ttft_sec')} | "
                  f"{med('out_tokens')} | {med('tps')}({','.join(sorted(kinds))}) | "
                  f"{sum(1 for x in rs if x['ok'])}/{len(rs)} |")
    (run_dir / "summary_v2.md").write_text("\n".join(ml) + "\n", encoding="utf-8")

    for r in out:
        print(f"{r['group']:<10} {r['tier']:<6} rep{r['rep']}  wall={r['wall_sec']:>8}  "
              f"ttft={str(r['ttft_sec']):>8}  out={str(r['out_tokens']):>6}  "
              f"in={str(r['in_tokens']):>7}  rea={str(r['reasoning_tokens']):>6}  "
              f"tps={str(r['tps']):>7}({r['tps_kind']})  ok={r['ok']}")
    print(f"\nwritten: {run_dir}/results_v2.jsonl summary_v2.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
