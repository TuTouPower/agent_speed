import json
from pathlib import Path

from agent_speed.report import generate_latest_json


def test_report_pipeline(tmp_path):
    """跨 batch 取最近 2 次有效成功；输入门槛与短输出过滤仍生效。"""
    jsonl_file = tmp_path / "results.jsonl"
    out_file = tmp_path / "latest.json"

    lines = [
        # 格子 1: 3 次成功 → 只用最近 2 次算中位数
        {"scenario": "200k", "model": "model-a", "effort": "high", "source": "src1", "harness": "opencode",
         "rep": 1, "batch_id": "batch_A", "start_time": "2026-09-22T10:00:00+08:00",
         "wall": 10.0, "ttft": 2.0, "decode_window": 8.0, "out_tokens": 1000, "in_tokens": 200000,
         "e2e_tps": 100.0, "gen_tps": 125.0, "decode_window_source": "opencode:text_part_time",
         "cl100k_tokens": 200000, "status": "success", "exclude_reason": None, "error_summary": None},
        {"scenario": "200k", "model": "model-a", "effort": "high", "source": "src1", "harness": "opencode",
         "rep": 2, "batch_id": "batch_A", "start_time": "2026-09-22T10:01:00+08:00",
         "wall": 8.0, "ttft": 1.8, "decode_window": 6.2, "out_tokens": 1200, "in_tokens": 200000,
         "e2e_tps": 150.0, "gen_tps": 193.5, "decode_window_source": "opencode:text_part_time",
         "cl100k_tokens": 200000, "status": "success", "exclude_reason": None, "error_summary": None},
        {"scenario": "200k", "model": "model-a", "effort": "high", "source": "src1", "harness": "opencode",
         "rep": 3, "batch_id": "batch_A", "start_time": "2026-09-22T10:02:00+08:00",
         "wall": 12.0, "ttft": 2.2, "decode_window": 9.8, "out_tokens": 1100, "in_tokens": 200000,
         "e2e_tps": 91.67, "gen_tps": 112.24, "decode_window_source": "opencode:text_part_time",
         "cl100k_tokens": 200000, "status": "success", "exclude_reason": None, "error_summary": None},

        # 格子 2: 旧 batch 2 次成功 + 新 batch 1 次成功 → 跨 batch 最近 2 次应上站
        {"scenario": "200k", "model": "model-b", "effort": "high", "source": "src1", "harness": "opencode",
         "rep": 1, "batch_id": "batch_B_old", "start_time": "2026-09-22T08:00:00+08:00",
         "wall": 10.0, "ttft": 2.0, "decode_window": 8.0, "out_tokens": 1000, "in_tokens": 200000,
         "e2e_tps": 100.0, "gen_tps": 125.0, "decode_window_source": "opencode:text_part_time",
         "cl100k_tokens": 200000, "status": "success", "exclude_reason": None, "error_summary": None},
        {"scenario": "200k", "model": "model-b", "effort": "high", "source": "src1", "harness": "opencode",
         "rep": 2, "batch_id": "batch_B_old", "start_time": "2026-09-22T08:01:00+08:00",
         "wall": 10.0, "ttft": 2.0, "decode_window": 8.0, "out_tokens": 1000, "in_tokens": 200000,
         "e2e_tps": 110.0, "gen_tps": 125.0, "decode_window_source": "opencode:text_part_time",
         "cl100k_tokens": 200000, "status": "success", "exclude_reason": None, "error_summary": None},
        {"scenario": "200k", "model": "model-b", "effort": "high", "source": "src1", "harness": "opencode",
         "rep": 1, "batch_id": "batch_B_new", "start_time": "2026-09-22T11:00:00+08:00",
         "wall": 10.0, "ttft": 2.0, "decode_window": 8.0, "out_tokens": 1000, "in_tokens": 200000,
         "e2e_tps": 120.0, "gen_tps": 125.0, "decode_window_source": "opencode:text_part_time",
         "cl100k_tokens": 200000, "status": "success", "exclude_reason": None, "error_summary": None},
        {"scenario": "200k", "model": "model-b", "effort": "high", "source": "src1", "harness": "opencode",
         "rep": 2, "batch_id": "batch_B_new", "start_time": "2026-09-22T11:01:00+08:00",
         "wall": 1.0, "ttft": None, "decode_window": None, "out_tokens": None, "in_tokens": None,
         "e2e_tps": None, "gen_tps": None, "decode_window_source": None,
         "cl100k_tokens": 200000, "status": "failed", "exclude_reason": None, "error_summary": "crash"},
        {"scenario": "200k", "model": "model-b", "effort": "high", "source": "src1", "harness": "opencode",
         "rep": 3, "batch_id": "batch_B_new", "start_time": "2026-09-22T11:02:00+08:00",
         "wall": 1.0, "ttft": None, "decode_window": None, "out_tokens": None, "in_tokens": None,
         "e2e_tps": None, "gen_tps": None, "decode_window_source": None,
         "cl100k_tokens": 200000, "status": "failed", "exclude_reason": None, "error_summary": "crash"},

        # 格子 3: 短输出丢弃，剩 2 次
        {"scenario": "200k", "model": "model-c", "effort": "high", "source": "src2", "harness": "grok",
         "rep": 1, "batch_id": "batch_C", "start_time": "2026-09-22T12:00:00+08:00",
         "wall": 5.0, "ttft": 1.0, "decode_window": 4.0, "out_tokens": 400, "in_tokens": 200000,
         "e2e_tps": 80.0, "gen_tps": 100.0, "decode_window_source": "grok:last_content_minus_ttft",
         "cl100k_tokens": 200000, "status": "success", "exclude_reason": None, "error_summary": None},
        {"scenario": "200k", "model": "model-c", "effort": "high", "source": "src2", "harness": "grok",
         "rep": 2, "batch_id": "batch_C", "start_time": "2026-09-22T12:01:00+08:00",
         "wall": 10.0, "ttft": 1.5, "decode_window": 8.5, "out_tokens": 800, "in_tokens": 200000,
         "e2e_tps": 80.0, "gen_tps": 94.12, "decode_window_source": "grok:last_content_minus_ttft",
         "cl100k_tokens": 200000, "status": "success", "exclude_reason": None, "error_summary": None},
        {"scenario": "200k", "model": "model-c", "effort": "high", "source": "src2", "harness": "grok",
         "rep": 3, "batch_id": "batch_C", "start_time": "2026-09-22T12:02:00+08:00",
         "wall": 12.0, "ttft": 1.5, "decode_window": 10.5, "out_tokens": 900, "in_tokens": 200000,
         "e2e_tps": 75.0, "gen_tps": 85.71, "decode_window_source": "grok:last_content_minus_ttft",
         "cl100k_tokens": 200000, "status": "success", "exclude_reason": None, "error_summary": None},

        # 格子 4: 账单输入过低不上站
        {"scenario": "200k", "model": "model-d", "effort": "high", "source": "src3", "harness": "opencode",
         "rep": 1, "batch_id": "batch_D", "start_time": "2026-09-22T13:00:00+08:00",
         "wall": 5.0, "ttft": 1.0, "decode_window": 4.0, "out_tokens": 800, "in_tokens": 30000,
         "e2e_tps": 160.0, "gen_tps": 200.0, "decode_window_source": "opencode:text_part_time",
         "cl100k_tokens": 200000, "status": "success", "exclude_reason": None, "error_summary": None},
        {"scenario": "200k", "model": "model-d", "effort": "high", "source": "src3", "harness": "opencode",
         "rep": 2, "batch_id": "batch_D", "start_time": "2026-09-22T13:01:00+08:00",
         "wall": 5.0, "ttft": 1.0, "decode_window": 4.0, "out_tokens": 800, "in_tokens": 30000,
         "e2e_tps": 160.0, "gen_tps": 200.0, "decode_window_source": "opencode:text_part_time",
         "cl100k_tokens": 200000, "status": "success", "exclude_reason": None, "error_summary": None},

        # 格子 5: codex gen_tps None
        {"scenario": "200k", "model": "model-e", "effort": "high", "source": "openai", "harness": "codex",
         "rep": 1, "batch_id": "batch_E", "start_time": "2026-09-22T14:00:00+08:00",
         "wall": 20.0, "ttft": 3.0, "decode_window": None, "out_tokens": 1000, "in_tokens": 205000,
         "e2e_tps": 50.0, "gen_tps": None, "decode_window_source": None,
         "cl100k_tokens": 200000, "status": "success", "exclude_reason": None, "error_summary": None},
        {"scenario": "200k", "model": "model-e", "effort": "high", "source": "openai", "harness": "codex",
         "rep": 2, "batch_id": "batch_E", "start_time": "2026-09-22T14:01:00+08:00",
         "wall": 16.0, "ttft": 2.5, "decode_window": None, "out_tokens": 960, "in_tokens": 205000,
         "e2e_tps": 60.0, "gen_tps": None, "decode_window_source": None,
         "cl100k_tokens": 200000, "status": "success", "exclude_reason": None, "error_summary": None},
    ]

    with open(jsonl_file, "w", encoding="utf-8") as f:
        for item in lines:
            f.write(json.dumps(item) + "\n")

    generate_latest_json(jsonl_file, out_file)
    rows = json.loads(out_file.read_text(encoding="utf-8"))

    # model-a, model-b (跨 batch), model-c, model-e；model-d 排除
    assert len(rows) == 4
    models = [r["model"] for r in rows]
    assert "model-d" not in models
    assert set(models) == {"model-a", "model-b", "model-c", "model-e"}

    e2e_tps_list = [r["e2e_tps"] for r in rows]
    assert e2e_tps_list == sorted(e2e_tps_list, reverse=True)

    by = {r["model"]: r for r in rows}

    # model-a 最近 2 次: 150.0, 91.67 -> 120.835 -> 120.84
    assert by["model-a"]["valid_reps"] == 2
    assert by["model-a"]["e2e_tps"] == 120.84
    assert by["model-a"]["batch_id"] == "batch_A"

    # model-b 最近 2 次成功: old@08:01 (110) + new@11:00 (120) -> 115
    assert by["model-b"]["valid_reps"] == 2
    assert by["model-b"]["e2e_tps"] == 115.0
    assert by["model-b"]["batch_id"] == "batch_B_new"

    # model-c 短输出丢弃后最近 2: 80, 75 -> 77.5
    assert by["model-c"]["valid_reps"] == 2
    assert by["model-c"]["e2e_tps"] == 77.5
    assert by["model-c"]["out_tokens"] == 850.0

    assert by["model-e"]["valid_reps"] == 2
    assert by["model-e"]["gen_tps"] is None
    assert by["model-e"]["e2e_tps"] == 55.0

    # wall medians (seconds, 3 dp) from same last-2 successes
    # model-a last2 walls: 8.0, 12.0 -> 10.0
    assert by["model-a"]["wall"] == 10.0
    # model-b last2: 10.0 (old@08:01), 10.0 (new@11:00) -> 10.0
    assert by["model-b"]["wall"] == 10.0
    # model-c last2 (after short drop): 10.0, 12.0 -> 11.0
    assert by["model-c"]["wall"] == 11.0
    # model-e: 20.0, 16.0 -> 18.0
    assert by["model-e"]["wall"] == 18.0
    assert all("wall" in r for r in rows)


def test_generate_all_boards_writes_single_latest(tmp_path):
    """唯一输出 latest.json：扁平数组、行内 scenario 自描述、分档块拼接、各档内 e2e 降序。"""
    from agent_speed.report import generate_all_boards

    jsonl = tmp_path / "results.jsonl"
    out = tmp_path / "latest.json"
    rows = []
    for scen, model, e2e in [("200k", "m200", 50.0), ("10k", "m10", 200.0), ("sentence", "msen", 300.0)]:
        cl = {"200k": 200000, "10k": 10000, "sentence": 61}[scen]
        ink = {"200k": 200000, "10k": 10000, "sentence": 61}[scen]
        for rep, start in enumerate(["2026-09-23T10:00:00+08:00", "2026-09-23T10:01:00+08:00"], start=1):
            rows.append({"scenario": scen, "model": model, "effort": "high", "source": "s", "harness": "h",
                         "rep": rep, "batch_id": "b1", "start_time": start, "wall": 10.0, "ttft": 1.0,
                         "decode_window": 8.0, "out_tokens": 1000, "in_tokens": ink, "e2e_tps": e2e,
                         "gen_tps": 100.0, "decode_window_source": "x", "cl100k_tokens": cl,
                         "status": "success", "exclude_reason": None, "error_summary": None})
    jsonl.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    boards = generate_all_boards(jsonl, out)

    combined = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(combined, list)
    assert [r["model"] for r in combined] == ["m200", "m10", "msen"]
    assert [r["scenario"] for r in combined] == ["200k", "10k", "sentence"]
    assert combined == boards["200k"] + boards["10k"] + boards["sentence"]


def test_board_excludes_removed_matrix_cells(tmp_path):
    """矩阵已删的格子不上榜（results 明细保留，只过滤榜单）；cells=None 时不过滤。"""
    from agent_speed.models import GridCell
    from agent_speed.report import generate_all_boards, generate_latest_json

    jsonl = tmp_path / "results.jsonl"
    rows = []
    for model in ("mkeep", "mgone"):
        for rep, start in enumerate(["2026-09-23T10:00:00+08:00", "2026-09-23T10:01:00+08:00"], start=1):
            rows.append({"scenario": "200k", "model": model, "effort": "high", "source": "s", "harness": "h",
                         "rep": rep, "batch_id": "b1", "start_time": start, "wall": 10.0, "ttft": 1.0,
                         "decode_window": 8.0, "out_tokens": 1000, "in_tokens": 200000, "e2e_tps": 50.0,
                         "gen_tps": 100.0, "decode_window_source": "x", "cl100k_tokens": 200000,
                         "status": "success", "exclude_reason": None, "error_summary": None})
    jsonl.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    keep = GridCell(scenario="200k", model="mkeep", effort="high", source="s", harness="h")

    out1 = tmp_path / "filtered.json"
    boards = generate_all_boards(jsonl, out1, cells=[keep])
    got = json.loads(out1.read_text(encoding="utf-8"))
    assert [r["model"] for r in got] == ["mkeep"]
    assert boards["10k"] == [] and boards["sentence"] == []

    out2 = tmp_path / "unfiltered.json"
    generate_latest_json(jsonl, out2, scenario="200k")
    assert sorted(r["model"] for r in json.loads(out2.read_text(encoding="utf-8"))) == ["mgone", "mkeep"]
