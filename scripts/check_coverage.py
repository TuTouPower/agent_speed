#!/usr/bin/env python3
"""check_coverage.py — 自动检测各档缺数据（只读，不写盘）。

矩阵格集合对三档通用；上榜口径与 report.py 完全一致
（≥2 次有效成功 + 账单输入中位数 ≥ cl100k 一半）。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent_speed.config import load_benchmark_config
from agent_speed.coverage import compute_coverage
from agent_speed.scenarios import VALID_SCENARIOS

ICON = {"onboard": "ok ", "thin": "thin", "missing": "MISS", "gate-blocked": "GATE"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="检测各档矩阵格数据缺口（只读）")
    ap.add_argument("--config", default=str(REPO_ROOT / "config" / "benchmark.yaml"))
    ap.add_argument("--scenarios", help="只查这些档，逗号分隔（默认全部）")
    args = ap.parse_args(argv)

    bench_cfg = load_benchmark_config(args.config)
    results_path = REPO_ROOT / bench_cfg.defaults.get("results_file", "data/results.jsonl")
    records = []
    if results_path.exists():
        with open(results_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except Exception:
                    continue

    scenarios = VALID_SCENARIOS
    if args.scenarios:
        scenarios = tuple(s for s in args.scenarios.split(",") if s in VALID_SCENARIOS)

    combined_path = REPO_ROOT / "data" / "latest.json"
    flat: list = []
    if combined_path.exists():
        try:
            loaded = json.load(open(combined_path, encoding="utf-8"))
            if isinstance(loaded, list):
                flat = loaded
        except Exception:
            flat = []

    for scen in scenarios:
        board_rows: list = [r for r in flat if isinstance(r, dict) and r.get("scenario") == scen]
        statuses, stale = compute_coverage(bench_cfg.cells, records, scen, board_rows)

        print(f"== {scen}（矩阵 {len(statuses)} 格，榜 {len(board_rows)} 行）")
        for s in statuses:
            if s.status == "onboard":
                continue
            eff = s.effort if s.effort else "-"
            print(f"  [{ICON[s.status]}] {s.model} / {eff} / {s.source} / {s.harness}"
                  f"  total={s.total} valid={s.valid} {s.note}".rstrip())
        n_ok = sum(1 for s in statuses if s.status == "onboard")
        print(f"  onboard {n_ok}/{len(statuses)}")

        gaps = [s for s in statuses if s.status in ("missing", "thin")]
        by_source: dict[str, list[str]] = defaultdict(list)
        for s in gaps:
            by_source[s.source].append(s.model)
        for src, models in sorted(by_source.items()):
            print(f"  run: uv run python scripts/run_bench.py --scenario {scen} --sources {src}")
        if not gaps and all(s.status == "onboard" for s in statuses):
            print("  complete: 无需补跑")
        gated = [s for s in statuses if s.status == "gate-blocked"]
        if gated:
            print("  note: GATE 格补跑也上不了榜（输入门槛），先看 note 再定: "
                  + ", ".join(f"{s.model}/{s.source}" for s in gated))
        if stale:
            print("  stale board rows（榜上有、矩阵已无）: "
                  + ", ".join(f"{m}/{e}/{s}" for _, m, e, s, _ in stale))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
