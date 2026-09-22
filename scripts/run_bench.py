#!/usr/bin/env python3
"""run_bench.py — 矩阵队列测速驱动程序。

按 source+harness 分队列调度：
- 同一队列内串行，跨队列并行，无全局上限；
- 每格 3 次属于同一 batch_id；失败在队列末尾补测 1 次；
- 指标实时写入 results.jsonl（追加写入）。
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent_speed.matrix import BENCH_MATRIX_200K
from agent_speed.models import GridCell, CallRecord
from agent_speed.harness import get_harness
from agent_speed.scheduler import QueueScheduler
from agent_speed.collector import append_result_record


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    default_prompt = repo_root / "prompts/task_200k.md"
    default_fixture = repo_root / "fixtures/django_200k.txt"
    default_out = repo_root / "results.jsonl"

    ap = argparse.ArgumentParser(description="按 source+harness 分队列基准测速驱动")
    ap.add_argument("--prompt", default=str(default_prompt), help="任务 prompt 文件")
    ap.add_argument("--fixture", default=str(default_fixture), help="代码切片文件")
    ap.add_argument("--out", default=str(default_out), help="结果输出 results.jsonl 路径")
    ap.add_argument("--sources", help="以逗号分隔的 source 过滤白名单")
    ap.add_argument("--harnesses", help="以逗号分隔的 harness 过滤白名单")
    ap.add_argument("--models", help="以逗号分隔的 model 过滤白名单")
    ap.add_argument("--reps", type=int, default=3, help="每格执行次数（默认 3）")
    ap.add_argument("--timeout", type=int, default=300, help="单次调用超时（秒）")
    args = ap.parse_args(argv)

    prompt_path = Path(args.prompt)
    fixture_path = Path(args.fixture)
    out_path = Path(args.out)

    if not prompt_path.exists():
        sys.exit(f"Prompt file not found: {prompt_path}")
    if not fixture_path.exists():
        sys.exit(f"Fixture file not found: {fixture_path}")

    prompt_text = prompt_path.read_text(encoding="utf-8")
    fixture_text = fixture_path.read_text(encoding="utf-8")

    # 筛选待执行 cells
    cells = list(BENCH_MATRIX_200K)
    if args.sources:
        src_set = set(args.sources.split(","))
        cells = [c for c in cells if c.source in src_set]
    if args.harnesses:
        harn_set = set(args.harnesses.split(","))
        cells = [c for c in cells if c.harness in harn_set]
    if args.models:
        mod_set = set(args.models.split(","))
        cells = [c for c in cells if c.model in mod_set or (c.cli_model and c.cli_model in mod_set)]

    if not cells:
        print("No cells to run after filtering.")
        return 0

    print(f"Selected {len(cells)} cells across queues:")
    queues = {}
    for c in cells:
        queues.setdefault(c.queue_key, []).append(c)
    for q_key, q_cells in queues.items():
        print(f"  [{q_key}] ({len(q_cells)} cells)")

    # 运行函数，封装 harness 调用与实时落盘
    def run_single_cell(cell: GridCell, rep: int, batch_id: str) -> CallRecord:
        harness = get_harness(cell.harness)
        with tempfile.TemporaryDirectory(prefix="bench-call-") as tmpdir:
            if cell.harness == "kimi":
                # kimi 需要传入 fixture 文本直传 argv
                rec = harness.run(
                    cell=cell,
                    rep=rep,
                    batch_id=batch_id,
                    prompt=prompt_text,
                    fixture_text=fixture_text,
                    cwd=tmpdir,
                    timeout=args.timeout,
                )
            else:
                rec = harness.run(
                    cell=cell,
                    rep=rep,
                    batch_id=batch_id,
                    prompt=prompt_text,
                    fixture_path=fixture_path,
                    cwd=tmpdir,
                    timeout=args.timeout,
                )

        # 实时追加写入 results.jsonl
        append_result_record(out_path, rec)
        return rec

    scheduler = QueueScheduler(runner=run_single_cell)
    records, logs = scheduler.run_all(cells, reps=args.reps)

    success_cnt = sum(1 for r in records if r.status == "success")
    print(f"\nAll queues completed. Total calls: {len(records)}, Success: {success_cnt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
