import threading
import time
import pytest
from pathlib import Path

from agent_speed.models import GridCell, CallRecord
from agent_speed.scheduler import QueueScheduler
from agent_speed.config import load_benchmark_config


class ConcurrencyTrackerHarness:
    """监测任意时刻并发调用数的 Fake Harness。"""

    def __init__(self, failure_map=None, sleep_sec=0.08):
        self.failure_map = failure_map or {}
        self.sleep_sec = sleep_sec
        self.lock = threading.Lock()

        self.current_global_active = 0
        self.max_global_active = 0

        self.current_queue_active = {}
        self.max_queue_active = {}

        self.calls = []

    def run_cell(self, cell: GridCell, rep: int, batch_id: str) -> CallRecord:
        q_key = cell.queue_key

        with self.lock:
            self.current_global_active += 1
            if self.current_global_active > self.max_global_active:
                self.max_global_active = self.current_global_active

            cur_q = self.current_queue_active.get(q_key, 0) + 1
            self.current_queue_active[q_key] = cur_q
            if cur_q > self.max_queue_active.get(q_key, 0):
                self.max_queue_active[q_key] = cur_q

        t_start = time.monotonic()
        time.sleep(self.sleep_sec)
        t_end = time.monotonic()

        with self.lock:
            self.current_global_active -= 1
            self.current_queue_active[q_key] -= 1

        is_fail = rep in self.failure_map.get(cell.cell_id, set())

        record = CallRecord(
            scenario=cell.scenario,
            model=cell.model,
            effort=cell.effort,
            source=cell.source,
            harness=cell.harness,
            rep=rep,
            batch_id=batch_id,
            start_time="2026-09-22T18:00:00+08:00",
            wall=round(t_end - t_start, 3),
            ttft=0.01,
            decode_window=0.04,
            out_tokens=600 if not is_fail else 10,
            in_tokens=200000,
            e2e_tps=50.0 if not is_fail else None,
            gen_tps=60.0 if not is_fail else None,
            decode_window_source="fake",
            cl100k_tokens=200000,
            status="success" if not is_fail else "failed",
            error_summary=None if not is_fail else "simulated failure",
        )

        with self.lock:
            self.calls.append({
                "queue_key": q_key,
                "cell_id": cell.cell_id,
                "rep": rep,
                "batch_id": batch_id,
                "start": t_start,
                "end": t_end,
                "record": record,
            })
        return record


def test_load_benchmark_config_file():
    """AC-001: 校验 config/benchmark.yaml 主配置加载与字段完整性"""
    cfg = load_benchmark_config()
    assert cfg.global_max_concurrency == 10
    assert cfg.per_queue_concurrency == 2
    assert len(cfg.cells) == 16

    # 验证模型名解耦与渠道正名 (AC-002)
    for c in cfg.cells:
        assert c.source != "official", f"Forbidden raw 'official' source: {c.model}"
        assert c.queue is not None, f"Missing explicit queue for {c.model}"
        assert c.resolved_cli_model is not None

    # 验证别名映射仅在必要时存在
    ds_off = next(c for c in cfg.cells if c.source == "deepseek-official")
    assert ds_off.alias == "deepseek-flash"
    assert ds_off.resolved_cli_model == "deepseek-flash"

    # 验证 MiMo 特殊处理：effort 为 None
    mimo_cells = [c for c in cfg.cells if "mimo" in c.model]
    assert len(mimo_cells) == 2
    for m in mimo_cells:
        assert m.effort is None


def test_scheduler_two_tier_concurrency_limits():
    """AC-003: 双层并发受控——全局 <= 10，单队列 <= 2，且达到单队列并发"""
    # 构造 6 个独立队列，每队列 3 个 cell，每 cell 跑 3 次（共 54 个任务）
    cells = []
    for q_idx in range(6):
        q_name = f"queue_{q_idx}"
        for c_idx in range(3):
            cells.append(
                GridCell(
                    scenario="200k",
                    model=f"model_{q_idx}_{c_idx}",
                    effort="high",
                    source=f"source_{q_idx}",
                    harness="opencode",
                    queue=q_name,
                )
            )

    tracker = ConcurrencyTrackerHarness(sleep_sec=0.04)
    scheduler = QueueScheduler(
        runner=tracker.run_cell,
        global_max_workers=10,
        per_queue_concurrency=2,
    )
    records, logs = scheduler.run_all(cells, reps=2)

    # 1. 验证全局并发峰值不超过 10
    assert tracker.max_global_active <= 10, f"Global concurrency exceeded 10: {tracker.max_global_active}"
    assert tracker.max_global_active > 2, "Global concurrency should be higher than single queue"

    # 2. 验证任意单队列并发峰值不超过 2
    for q_name, max_q in tracker.max_queue_active.items():
        assert max_q <= 2, f"Queue {q_name} exceeded 2 concurrency: {max_q}"
        assert max_q == 2, f"Queue {q_name} should reach 2 concurrency: {max_q}"


def test_gemini_shared_queue_and_deepseek_parallelism():
    """AC-004: Gemini CPA 与 Antigravity 共享 antigravity 队列（<=2并发）；DeepSeek 官方与网关不同队"""
    cfg = load_benchmark_config()

    gemini_cells = [c for c in cfg.cells if "gemini" in c.model]
    assert len(gemini_cells) >= 2
    for c in gemini_cells:
        assert c.queue_key == "antigravity", f"Gemini cell {c.cli_model} should be in antigravity queue"

    ds_off = next(c for c in cfg.cells if c.source == "deepseek-official")
    ds_gw = next(c for c in cfg.cells if c.source == "opencode-go" and "deepseek" in c.model)
    assert ds_off.queue_key != ds_gw.queue_key, "DeepSeek official and gateway must have different queues"


def test_scheduler_batch_id_and_retry():
    """验证同一网格 3+1 batch 与补测依然正常工作"""
    cell = GridCell("200k", "test-model", "high", "src", "opencode", queue="q1")
    tracker = ConcurrencyTrackerHarness(failure_map={cell.cell_id: {2}}, sleep_sec=0.01)
    scheduler = QueueScheduler(runner=tracker.run_cell, global_max_workers=10, per_queue_concurrency=2)
    records, logs = scheduler.run_all([cell], reps=3)

    cell_calls = [c for c in tracker.calls if c["cell_id"] == cell.cell_id]
    assert len(cell_calls) == 4
    assert sorted([c["rep"] for c in cell_calls]) == [1, 2, 3, 4]
    assert len({c["batch_id"] for c in cell_calls}) == 1
    # 补测必须发生在末尾
    assert cell_calls[3]["rep"] == 4
