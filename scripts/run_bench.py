#!/usr/bin/env python3
"""run_bench.py — 矩阵队列测速驱动程序。

按物理队列 (queue) 双层受控并发调度：
- 默认加载 config/benchmark.json；
- 单队列最多 2 并发，全局受控最大 10 并发；
- 每格 3 次属于同一 batch_id；失败在队列末尾补测 1 次；
- 指标实时写入 data/results.jsonl（追加写入）。
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

from agent_speed.config import load_benchmark_config
from agent_speed.models import GridCell, CallRecord
from agent_speed.harness import get_harness
from agent_speed.scheduler import QueueScheduler
from agent_speed.collector import append_result_record
from agent_speed.report import generate_all_boards
from agent_speed.board_preview import refresh_board_preview
from agent_speed.scenarios import VALID_SCENARIOS, apply_scenario_to_cell, resolve_scenario_inputs


def main(argv: list[str] | None = None) -> int:
    default_config = REPO_ROOT / "config/benchmark.yaml"

    ap = argparse.ArgumentParser(description="按 queue 分队列双层并发基准测速驱动")
    ap.add_argument("--config", default=str(default_config), help="集中配置文件路径")
    ap.add_argument("--prompt", help="任务 prompt 文件（覆盖对应档位的配置输入）")
    ap.add_argument("--fixture", help="代码切片文件（覆盖对应档位的配置输入）")
    ap.add_argument("--out", help="结果输出 results.jsonl 路径（默认从配置读取）")
    ap.add_argument("--sources", help="以逗号分隔的 source 过滤白名单")
    ap.add_argument("--harnesses", help="以逗号分隔的 harness 过滤白名单")
    ap.add_argument("--models", help="以逗号分隔的 model 过滤白名单")
    ap.add_argument("--efforts", help="以逗号分隔的 effort 过滤白名单")
    ap.add_argument("--reps", type=int, help="每格执行次数（默认从配置读取）")
    ap.add_argument("--timeout", type=int, help="单次调用超时（秒，默认从配置读取）")
    ap.add_argument("--scenario", choices=list(VALID_SCENARIOS), help="评测档位：sentence / 10k / 200k（默认 200k）")
    args = ap.parse_args(argv)

    bench_cfg = load_benchmark_config(args.config)
    defaults = bench_cfg.defaults

    scenario = args.scenario or defaults.get("scenario", "200k")
    if scenario not in VALID_SCENARIOS:
        sys.exit(f"Unknown scenario: {scenario!r}, expected one of {VALID_SCENARIOS}")

    scen_prompt, scen_fixture_text, scen_fixture_path, scen_cl100k = resolve_scenario_inputs(
        scenario, REPO_ROOT, bench_cfg.scenarios)

    if args.prompt:
        prompt_text = Path(args.prompt).read_text(encoding="utf-8")
    else:
        prompt_text = scen_prompt

    if args.fixture:
        fixture_path: Path | None = Path(args.fixture)
        fixture_text = fixture_path.read_text(encoding="utf-8")
    else:
        fixture_text = scen_fixture_text
        fixture_path = scen_fixture_path
    out_path = Path(args.out or (REPO_ROOT / defaults.get("results_file", "data/results.jsonl")))
    reps = args.reps or defaults.get("reps", 3)
    timeout_sec = args.timeout or defaults.get("timeout_sec", 300)

    # 筛选待执行 cells（一次运行只产生一个 scenario；格子集合不因档位增删）
    cells = [apply_scenario_to_cell(c, scenario, bench_cfg.scenarios) for c in bench_cfg.cells]
    if args.sources:
        src_set = set(args.sources.split(","))
        cells = [c for c in cells if c.source in src_set]
    if args.harnesses:
        harn_set = set(args.harnesses.split(","))
        cells = [c for c in cells if c.harness in harn_set]
    if args.models:
        mod_set = set(args.models.split(","))
        cells = [c for c in cells if c.model in mod_set or (c.cli_model and c.cli_model in mod_set)]
    if args.efforts:
        eff_set = set(args.efforts.split(","))
        cells = [c for c in cells if str(c.effort) in eff_set]

    if not cells:
        print("No cells to run after filtering.")
        return 0

    print(f"Loaded config: {args.config} (global_max={bench_cfg.global_max_concurrency}, per_queue={bench_cfg.per_queue_concurrency})")
    print(f"Scenario: {scenario} (cl100k_tokens={scen_cl100k})")
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
            rec = harness.run(
                cell=cell,
                rep=rep,
                batch_id=batch_id,
                prompt=prompt_text,
                fixture_path=fixture_path,
                fixture_text=fixture_text,
                cwd=tmpdir,
                timeout=timeout_sec,
            )

        # 实时追加写入 data/results.jsonl
        append_result_record(out_path, rec)
        return rec

    scheduler = QueueScheduler(
        runner=run_single_cell,
        global_max_workers=bench_cfg.global_max_concurrency,
        per_queue_concurrency=bench_cfg.per_queue_concurrency,
    )
    records, logs = scheduler.run_all(cells, reps=reps)

    success_cnt = sum(1 for r in records if r.status == "success")
    print(f"\nAll queues completed. Total calls: {len(records)}, Success: {success_cnt}")

    # 测速完成后自动刷新合一榜单（各档互不混排，不合成总分）
    data_dir = REPO_ROOT / "data"
    boards = generate_all_boards(out_path, data_dir / "latest_200k.json", cells=bench_cfg.cells)
    for scen, rows in boards.items():
        print(f"Auto-generated data/latest_{scen}.json ({len(rows)} rows)")
    latest_path = data_dir / "latest_200k.json"
    preview = refresh_board_preview(latest=latest_path)
    if preview is not None:
        print(f"Updated board preview: {preview}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
