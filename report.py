#!/usr/bin/env python3
"""report.py — 从 results.jsonl 生成 latest.json。

用法：
  python3 report.py [--results results.jsonl] [--out latest.json]
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent_speed.report import generate_latest_json


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="生成 latest.json")
    ap.add_argument("--results", default=str(REPO_ROOT / "results.jsonl"), help="输入 results.jsonl 路径")
    ap.add_argument("--out", default=str(REPO_ROOT / "latest.json"), help="输出 latest.json 路径")
    args = ap.parse_args(argv)

    results_file = Path(args.results)
    out_file = Path(args.out)

    rows = generate_latest_json(results_file, out_file)
    print(f"Generated {len(rows)} rows to {out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
