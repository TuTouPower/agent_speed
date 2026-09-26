#!/usr/bin/env python3
"""report.py — 从 data/results.jsonl 生成分档榜 data/latest_{200k,10k,sentence}.json。

用法：
  python3 report.py [--results data/results.jsonl] [--out data/latest_200k.json]
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent_speed.config import load_benchmark_config
from agent_speed.report import generate_all_boards
from agent_speed.board_preview import refresh_board_preview


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="生成分档榜 data/latest_{200k,10k,sentence}.json")
    ap.add_argument("--results", default=str(REPO_ROOT / "data" / "results.jsonl"), help="输入 results.jsonl 路径")
    ap.add_argument("--out", default=str(REPO_ROOT / "data" / "latest_200k.json"), help="200k 榜输出路径（同目录另写 latest_10k / latest_sentence）")
    args = ap.parse_args(argv)

    results_file = Path(args.results)
    out_file = Path(args.out)

    boards = generate_all_boards(results_file, out_file, cells=load_benchmark_config().cells)
    for scen, rows in boards.items():
        print(f"Generated {len(rows)} rows for scenario={scen}")
    preview = refresh_board_preview(latest=out_file)
    if preview is not None:
        print(f"Updated board preview: {preview}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
