import json
import pytest
from pathlib import Path
from agent_speed.models import CallRecord
from agent_speed.collector import append_result_record

REQUIRED_FIELDS = {
    "scenario", "model", "effort", "source", "harness", "rep", "batch_id",
    "start_time", "wall", "ttft", "decode_window", "out_tokens", "in_tokens",
    "e2e_tps", "gen_tps", "decode_window_source", "cl100k_tokens",
    "status", "used_tools", "exclude_reason", "error_summary",
}


def test_results_jsonl_schema_and_append(tmp_path):
    """AC-006: results.jsonl 每次调用一行、只追加；字段全集符合 §7.1；不含模型正文、密钥、本机绝对路径"""
    out_file = tmp_path / "results.jsonl"

    rec1 = CallRecord(
        scenario="200k",
        model="deepseek-v4.1",
        effort="high",
        source="opencode-go",
        harness="opencode",
        rep=1,
        batch_id="batch-001",
        start_time="2026-09-22T14:30:00+08:00",
        wall=12.5,
        ttft=2.1,
        decode_window=10.0,
        out_tokens=800,
        in_tokens=205000,
        e2e_tps=64.0,
        gen_tps=80.0,
        decode_window_source="opencode:text_part_time",
        cl100k_tokens=200000,
        status="success",
    )

    rec2 = CallRecord(
        scenario="200k",
        model="gpt-5.6-luna",
        effort="high",
        source="openai",
        harness="codex",
        rep=1,
        batch_id="batch-002",
        start_time="2026-09-22T14:31:00+08:00",
        wall=15.0,
        ttft=3.0,
        decode_window=None,
        out_tokens=750,
        in_tokens=204000,
        e2e_tps=50.0,
        gen_tps=None,
        decode_window_source=None,
        cl100k_tokens=200000,
        status="success",
    )

    append_result_record(out_file, rec1)
    append_result_record(out_file, rec2)

    lines = out_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    for line in lines:
        data = json.loads(line)
        # 必须拥有所有必填字段
        assert REQUIRED_FIELDS.issubset(data.keys())

        # 不含模型正文、密钥、本机绝对路径
        assert "response_text" not in data
        assert "text" not in data or data.get("text") is None
        assert "events" not in data
        assert "/Users/" not in line
        assert "key" not in line.lower() or data.get("decode_window_source") is not None
