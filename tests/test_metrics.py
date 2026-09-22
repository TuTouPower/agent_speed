import pytest
from agent_speed.metrics import (
    calculate_tps,
    parse_opencode_metrics,
    parse_grok_metrics,
    parse_kimi_metrics,
    parse_codex_metrics,
)


def test_tps_calculation():
    """AC-004: 端到端 TPS=输出 token ÷ wall；生成 TPS=输出 token ÷ 生成窗口（空则空）"""
    # 正常情况
    e2e, gen = calculate_tps(wall=10.0, decode_window=5.0, out_tokens=200)
    assert e2e == 20.0
    assert gen == 40.0

    # 生成窗口为空（codex 场景）
    e2e, gen = calculate_tps(wall=10.0, decode_window=None, out_tokens=200)
    assert e2e == 20.0
    assert gen is None

    # 输出为 0 或 None
    e2e, gen = calculate_tps(wall=10.0, decode_window=5.0, out_tokens=None)
    assert e2e is None
    assert gen is None

    # wall 为 0 或负数
    e2e, gen = calculate_tps(wall=0, decode_window=5.0, out_tokens=200)
    assert e2e is None


def test_opencode_metrics_server_window():
    """AC-003 & AC-004: opencode 文本段服务端窗口，TTFT 取首个可见 token（含思考）"""
    lines = [
        (0.5, '{"type": "init"}'),
        (1.2, '{"type": "reasoning", "part": {"text": "Thinking..."}}'),
        (2.0, '{"type": "text", "part": {"text": "Hello", "time": {"start": 1700000000000, "end": 1700000005500}}}'),
        (3.0, '{"type": "step-finish", "part": {"tokens": {"input": 210000, "output": 850}}}'),
    ]
    ttft, decode_window, source, in_toks, out_toks, used_tools = parse_opencode_metrics(lines)
    assert ttft == 1.2  # 包含思考首 token
    assert decode_window == 5.5  # (1700000005500 - 1700000000000) / 1000
    assert source == "opencode:text_part_time"
    assert in_toks == 210000
    assert out_toks == 850
    assert not used_tools


def test_grok_metrics_last_content_minus_ttft():
    """AC-003 & AC-004: grok 末内容增量 - TTFT，不用 duration_api_ms"""
    lines = [
        (0.8, '{"type": "start"}'),
        (1.5, '{"type": "content", "delta": "First token"}'),
        (3.5, '{"type": "content", "delta": "Middle"}'),
        (6.0, '{"type": "content", "delta": "Final chunk"}'),
        (6.2, '{"type": "result", "duration_api_ms": 999999, "usage": {"prompt_tokens": 205000, "completion_tokens": 600}}'),
    ]
    ttft, decode_window, source, in_toks, out_toks, used_tools = parse_grok_metrics(lines)
    assert ttft == 1.5
    assert decode_window == 4.5  # 6.0 - 1.5
    assert source == "grok:last_content_minus_ttft"
    assert in_toks == 205000
    assert out_toks == 600
    assert not used_tools


def test_kimi_metrics_decode_ms():
    """AC-003 & AC-004: kimi llmServerDecodeMs"""
    lines = [
        (0.6, '{"type": "init"}'),
        (1.8, '{"type": "text", "content": "Start of response"}'),
    ]
    wire_info = {
        "llmServerDecodeMs": 3200,
        "in_tokens": 201000,
        "out_tokens": 1200,
    }
    ttft, decode_window, source, in_toks, out_toks, used_tools = parse_kimi_metrics(lines, wire_info)
    assert ttft == 1.8
    assert decode_window == 3.2
    assert source == "kimi:llm_server_decode_ms"
    assert in_toks == 201000
    assert out_toks == 1200
    assert not used_tools


def test_codex_metrics_empty_window():
    """AC-003: codex 无生成窗口"""
    lines = [
        (0.5, '{"type": "turn.started"}'),
        (2.1, '{"type": "item.completed", "item": {"text": "Answer..."}}'),
        (4.0, '{"type": "usage", "input_tokens": 204000, "output_tokens": 700}'),
    ]
    ttft, decode_window, source, in_toks, out_toks, used_tools = parse_codex_metrics(lines)
    assert ttft == 2.1
    assert decode_window is None
    assert source is None
    assert in_toks == 204000
    assert out_toks == 700
    assert not used_tools
    assert source is None
    assert in_toks == 204000
    assert out_toks == 700
