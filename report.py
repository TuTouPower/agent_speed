#!/usr/bin/env python3
"""report.py — 从 data/results.jsonl 生成三份分榜。

用法：
  python3 report.py [--results data/results.jsonl] [--out data/latest.json]
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent_speed.report import SCENARIO_BOARD_FILES, generate_latest_json
from agent_speed.board_preview import refresh_board_preview


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="生成三档分榜（200k / 10k / sentence）")
    ap.add_argument("--results", default=str(REPO_ROOT / "data" / "results.jsonl"), help="输入 results.jsonl 路径")
    ap.add_argument("--out", default=str(REPO_ROOT / "data" / "latest.json"), help="输出 latest.json 路径（200k 档）")
    ap.add_argument("--out-10k", default=None, help="输出 latest_10k.json 路径（默认与 --out 同目录）")
    ap.add_argument("--out-sentence", default=None, help="输出 latest_sentence.json 路径（默认与 --out 同目录）")
    args = ap.parse_args(argv)

    results_file = Path(args.results)
    out_file = Path(args.out)
    out_dir = out_file.parent
    out_10k = Path(args.out_10k) if args.out_10k else (out_dir / SCENARIO_BOARD_FILES["10k"])
    out_sentence = Path(args.out_sentence) if args.out_sentence else (out_dir / SCENARIO_BOARD_FILES["sentence"])

    rows200 = generate_latest_json(results_file, out_file, scenario="200k")
    print(f"Generated {len(rows200)} rows to {out_file} (scenario=200k)")
    rows10 = generate_latest_json(results_file, out_10k, scenario="10k")
    print(f"Generated {len(rows10)} rows to {out_10k} (scenario=10k)")
    rows_sen = generate_latest_json(results_file, out_sentence, scenario="sentence")
    print(f"Generated {len(rows_sen)} rows to {out_sentence} (scenario=sentence)")
    preview = refresh_board_preview(latest=out_file)
    if preview is not None:
        print(f"Updated board preview: {preview}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
