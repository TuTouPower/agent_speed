"""tests/test_coverage.py — 缺数据检测纯逻辑测试（触达生产逻辑）。"""

from agent_speed.coverage import compute_coverage
from agent_speed.models import GridCell


def _cell(model="m", effort=None, source="s", harness="h"):
    return GridCell(scenario="200k", model=model, effort=effort, source=source, harness=harness)


def _rec(model="m", effort=None, source="s", harness="h", scenario="200k",
         status="success", out=3000, wall=60.0, in_toks=220000, cl100k=200000,
         start="2026-09-23T00:00:00+08:00"):
    return {
        "scenario": scenario, "model": model, "effort": effort,
        "source": source, "harness": harness, "status": status,
        "out_tokens": out, "wall": wall, "in_tokens": in_toks,
        "cl100k_tokens": cl100k, "start_time": start,
    }


def test_missing_cell_no_records():
    statuses, stale = compute_coverage([_cell()], [], scenario="200k", board_rows=[])
    assert len(statuses) == 1
    s = statuses[0]
    assert s.status == "missing"
    assert s.total == 0 and s.valid == 0


def test_thin_cell_one_valid():
    statuses, _ = compute_coverage([_cell()], [_rec()], scenario="200k", board_rows=[])
    assert statuses[0].status == "thin"
    assert statuses[0].valid == 1


def test_onboard_cell_two_valid_pass_gate():
    recs = [_rec(start="2026-09-23T00:00:00+08:00"), _rec(start="2026-09-23T01:00:00+08:00")]
    statuses, _ = compute_coverage([_cell()], recs, scenario="200k", board_rows=[])
    s = statuses[0]
    assert s.status == "onboard"
    assert s.valid == 2


def test_gate_blocked_low_input_tokens():
    recs = [_rec(in_toks=40000, start="2026-09-23T00:00:00+08:00"),
            _rec(in_toks=41000, start="2026-09-23T01:00:00+08:00")]
    statuses, _ = compute_coverage([_cell()], recs, scenario="200k", board_rows=[])
    assert statuses[0].status == "gate-blocked"


def test_failed_and_short_output_do_not_count():
    recs = [
        _rec(status="failed", start="2026-09-23T00:00:00+08:00"),
        _rec(out=100, start="2026-09-23T01:00:00+08:00"),
        _rec(start="2026-09-23T02:00:00+08:00"),
    ]
    statuses, _ = compute_coverage([_cell()], recs, scenario="200k", board_rows=[])
    assert statuses[0].status == "thin"
    assert statuses[0].total == 3


def test_stale_board_row_not_in_matrix():
    statuses, stale = compute_coverage(
        [_cell(model="m")],
        [_rec(model="m"), _rec(model="m", start="2026-09-23T01:00:00+08:00")],
        scenario="200k",
        board_rows=[{"model": "gone", "effort": None, "source": "s", "harness": "h"}],
    )
    assert statuses[0].status == "onboard"
    assert stale == [("200k", "gone", None, "s", "h")]


def test_latest_two_valid_used_for_gate():
    recs = [
        _rec(in_toks=1000, start="2026-09-23T00:00:00+08:00"),
        _rec(start="2026-09-23T01:00:00+08:00"),
        _rec(start="2026-09-23T02:00:00+08:00"),
    ]
    statuses, _ = compute_coverage([_cell()], recs, scenario="200k", board_rows=[])
    assert statuses[0].status == "onboard"
