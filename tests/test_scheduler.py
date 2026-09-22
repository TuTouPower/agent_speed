import time
import pytest
from pathlib import Path
from agent_speed.models import GridCell, CallRecord
from agent_speed.scheduler import QueueScheduler


class FakeHarness:
    def __init__(self, failure_rounds=None):
        # failure_rounds: dict mapping cell id to set of reps that fail
        self.failure_rounds = failure_rounds or {}
        self.calls = []

    def run_cell(self, cell: GridCell, rep: int, batch_id: str) -> CallRecord:
        t_start = time.monotonic()
        time.sleep(0.05)  # 模拟耗时
        t_end = time.monotonic()
        fails = self.failure_rounds.get(cell.cell_id, set())
        is_fail = rep in fails
        record = CallRecord(
            scenario=cell.scenario,
            model=cell.model,
            effort=cell.effort,
            source=cell.source,
            harness=cell.harness,
            rep=rep,
            batch_id=batch_id,
            start_time="2026-09-22T14:00:00+08:00",
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
        self.calls.append({
            "queue_key": cell.queue_key,
            "cell_id": cell.cell_id,
            "rep": rep,
            "batch_id": batch_id,
            "start": t_start,
            "end": t_end,
            "record": record,
        })
        return record


def test_scheduler_queue_parallelism_and_serialization():
    """AC-001: source+harness 队列键，同队列串行无重叠，不同队列并行有重叠"""
    # 2 个队列：
    # Q1: opencode-go:opencode (2 个 cell)
    # Q2: official:opencode (1 个 cell)
    cells = [
        GridCell("200k", "deepseek-v4.1", "high", "opencode-go", "opencode"),
        GridCell("200k", "deepseek-v4.1", "max", "opencode-go", "opencode"),
        GridCell("200k", "deepseek-flash", "high", "official", "opencode"),
    ]

    harness = FakeHarness()
    scheduler = QueueScheduler(runner=harness.run_cell)
    records, logs = scheduler.run_all(cells)

    # 验证调度日志含队列键
    assert any("queue=opencode-go:opencode" in log for log in logs)
    assert any("queue=official:opencode" in log for log in logs)

    # 验证同一队列内无时间重叠
    q1_calls = [c for c in harness.calls if c["queue_key"] == "opencode-go:opencode"]
    for i in range(len(q1_calls) - 1):
        # 串行：前一个结束时间 <= 后一个开始时间 (允许极小时间片漂移)
        assert q1_calls[i]["end"] <= q1_calls[i + 1]["start"] + 0.005, "Same queue calls must be serialized"

    # 验证不同队列间发生并行（存在重叠区间）
    q2_calls = [c for c in harness.calls if c["queue_key"] == "official:opencode"]
    overlap = False
    for c1 in q1_calls:
        for c2 in q2_calls:
            # 判断时间段 [start, end] 是否重叠
            if max(c1["start"], c2["start"]) < min(c1["end"], c2["end"]):
                overlap = True
                break
        if overlap:
            break
    assert overlap, "Different queues must run concurrently"


def test_scheduler_batch_and_retry():
    """AC-002: 每格 3 次同一 batch_id，失败在末尾补测 1 次，无 warmup，最多 4 次"""
    cell = GridCell("200k", "test-model", "high", "test-source", "test-harness")
    # 让 rep=2 失败
    harness = FakeHarness(failure_rounds={cell.cell_id: {2}})
    scheduler = QueueScheduler(runner=harness.run_cell)
    records, logs = scheduler.run_all([cell])

    cell_calls = [c for c in harness.calls if c["cell_id"] == cell.cell_id]
    # 总共 3 + 1 = 4 次
    assert len(cell_calls) == 4
    reps = [c["rep"] for c in cell_calls]
    assert reps == [1, 2, 3, 4]

    # 同一 batch_id
    batch_ids = {c["batch_id"] for c in cell_calls}
    assert len(batch_ids) == 1

    # rep 4 在末尾执行
    assert cell_calls[3]["rep"] == 4
    # 最多 4 次
    assert len(records) == 4
