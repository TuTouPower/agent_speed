import json
import pytest
from pathlib import Path

from agent_speed.report import generate_latest_json


def test_report_pipeline(tmp_path):
    """验证最新 batch、过滤规则、中位数计算与排序（AC-001 ~ AC-007）"""
    jsonl_file = tmp_path / "results.jsonl"
    out_file = tmp_path / "latest.json"

    # 构造数据：
    lines = [
        # 格子 1: 正常合格 (cell_A)
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

        # 格子 2: 旧 batch 合格，但最新 batch 只有 1 次成功 (AC-001 & AC-002: 不补位，不上站)
        {"scenario": "200k", "model": "model-b", "effort": "high", "source": "src1", "harness": "opencode",
         "rep": 1, "batch_id": "batch_B_old", "start_time": "2026-09-22T08:00:00+08:00",
         "wall": 10.0, "ttft": 2.0, "decode_window": 8.0, "out_tokens": 1000, "in_tokens": 200000,
         "e2e_tps": 100.0, "gen_tps": 125.0, "decode_window_source": "opencode:text_part_time",
         "cl100k_tokens": 200000, "status": "success", "exclude_reason": None, "error_summary": None},
        {"scenario": "200k", "model": "model-b", "effort": "high", "source": "src1", "harness": "opencode",
         "rep": 2, "batch_id": "batch_B_old", "start_time": "2026-09-22T08:01:00+08:00",
         "wall": 10.0, "ttft": 2.0, "decode_window": 8.0, "out_tokens": 1000, "in_tokens": 200000,
         "e2e_tps": 100.0, "gen_tps": 125.0, "decode_window_source": "opencode:text_part_time",
         "cl100k_tokens": 200000, "status": "success", "exclude_reason": None, "error_summary": None},
        # 最新 batch_B_new
        {"scenario": "200k", "model": "model-b", "effort": "high", "source": "src1", "harness": "opencode",
         "rep": 1, "batch_id": "batch_B_new", "start_time": "2026-09-22T11:00:00+08:00",
         "wall": 10.0, "ttft": 2.0, "decode_window": 8.0, "out_tokens": 1000, "in_tokens": 200000,
         "e2e_tps": 100.0, "gen_tps": 125.0, "decode_window_source": "opencode:text_part_time",
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

        # 格子 3: 包含一次极短输出 < 500 丢弃，其余 2 次有效 (AC-003 & AC-007)
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

        # 格子 4: 账单输入 < 切片一半 (200k 的一半是 100k)，不上站 (AC-004)
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

        # 格子 5: codex 无生成窗口，照常上站且 gen_tps 为 None (AC-005)
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

    assert out_file.exists()
    rows = json.loads(out_file.read_text(encoding="utf-8"))

    # 上站的格子应该是：model-a, model-c, model-e（共 3 个）
    # model-b 最新 batch 只有 1 次有效 -> 排除
    # model-d in_tokens 30000 < 100000 -> 排除
    assert len(rows) == 3

    models = [r["model"] for r in rows]
    assert models == ["model-a", "model-c", "model-e"]

    # 按 e2e_tps 降序排列 (AC-006)
    e2e_tps_list = [r["e2e_tps"] for r in rows]
    assert e2e_tps_list == sorted(e2e_tps_list, reverse=True)

    # 验证 model-a 中位数: [100.0, 150.0, 91.67] -> 100.0
    row_a = rows[0]
    assert row_a["valid_reps"] == 3
    assert row_a["e2e_tps"] == 100.0
    assert row_a["batch_id"] == "batch_A"

    # 验证 model-c: rep=1 被过滤，剩余 2 次 [80.0, 75.0] -> 77.5
    row_c = rows[1]
    assert row_c["valid_reps"] == 2
    assert row_c["e2e_tps"] == 77.5
    assert row_c["out_tokens"] == 850.0  # 中位数 (800 + 900) / 2

    # 验证 model-e (codex): gen_tps 为 None
    row_e = rows[2]
    assert row_e["valid_reps"] == 2
    assert row_e["gen_tps"] is None
    assert row_e["e2e_tps"] == 55.0  # (50 + 60) / 2
