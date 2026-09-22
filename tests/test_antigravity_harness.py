import pytest
from pathlib import Path

from agent_speed.models import GridCell
from agent_speed.harness.antigravity import AntigravityHarness, build_antigravity_cmd
from agent_speed.harness import get_harness
from agent_speed.metrics import parse_antigravity_metrics
from agent_speed.matrix import BENCH_MATRIX_200K


def test_antigravity_cmd_builder():
    """AC-001: AntigravityHarness 组装 agy 命令，通过 -p 直传 prompt 与切片"""
    cell = GridCell(
        scenario="200k",
        model="gemini-3.8-flash-high",
        effort="high",
        source="google",
        harness="antigravity",
    )
    prompt = "分析分层架构"
    fixture = "DJANGO_200K_MOCK_CONTENT" * 10
    cmd = build_antigravity_cmd(cell, prompt, fixture, bin_name="agy")

    assert "agy" in cmd[0]
    assert "-p" in cmd
    p_idx = cmd.index("-p")
    full_text = cmd[p_idx + 1]
    assert prompt in full_text
    assert fixture in full_text

    assert "--model" in cmd
    m_idx = cmd.index("--model")
    assert cmd[m_idx + 1] == "gemini-3.8-flash-high"

    assert "--effort" in cmd
    e_idx = cmd.index("--effort")
    assert cmd[e_idx + 1] == "high"

    assert "--output-format" in cmd
    o_idx = cmd.index("--output-format")
    assert cmd[o_idx + 1] == "stream-json"


def test_parse_antigravity_metrics():
    """AC-002: parse_antigravity_metrics 准确解析 stream-json 事件流中的 TTFT、生成窗口与 token usage"""
    lines = [
        (0.2, '{"event":"init","init":{"model":"gemini-3.8-flash-high"}}'),
        (0.5, '{"event":"step_update","step_update":{"step_index":0,"state":"DONE","step_type":"user_input"}}'),
        # 第一个可见 token 到达 (TTFT)
        (1.8, '{"event":"step_update","step_update":{"step_index":1,"state":"ACTIVE","step_type":"agent_response","text_delta":"系统"}}'),
        (3.2, '{"event":"step_update","step_update":{"step_index":1,"state":"ACTIVE","step_type":"agent_response","text_delta":"分层如下"}}'),
        # 最后一个 text_delta
        (7.8, '{"event":"step_update","step_update":{"step_index":1,"state":"DONE","step_type":"agent_response","text_delta":"结束\\n","duration_seconds":6.0,"usage":{"input_tokens":61500,"output_tokens":850,"thinking_tokens":50,"total_tokens":62350}}}'),
        (8.0, '{"event":"result","result":{"status":"SUCCESS","duration_seconds":6.2,"usage":{"input_tokens":61500,"output_tokens":850,"thinking_tokens":50,"total_tokens":62350}}}'),
    ]

    ttft, decode_window, source, in_toks, out_toks = parse_antigravity_metrics(lines)

    assert ttft == 1.8
    assert decode_window == 6.0  # 7.8 - 1.8
    assert source == "antigravity:last_delta_minus_ttft"
    assert in_toks == 61500
    assert out_toks == 850


def test_harness_registry_antigravity():
    """AC-003: get_harness 支持 antigravity 与 agy 别名"""
    h1 = get_harness("antigravity")
    h2 = get_harness("agy")

    assert isinstance(h1, AntigravityHarness)
    assert isinstance(h2, AntigravityHarness)


def test_matrix_contains_antigravity():
    """AC-004: BENCH_MATRIX_200K 包含 antigravity 格子，队列键为 google:antigravity"""
    agy_cells = [c for c in BENCH_MATRIX_200K if c.harness in ("antigravity", "agy")]
    assert len(agy_cells) > 0

    for c in agy_cells:
        assert c.source == "google"
        assert c.queue_key == "google:antigravity"
        assert c.scenario == "200k"
