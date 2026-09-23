from agent_speed.models import GridCell
from agent_speed.harness.mimo import MimoHarness, build_mimo_cmd
from agent_speed.harness import get_harness
from agent_speed.metrics import parse_mimo_metrics


def test_mimo_cmd_builder():
    """AC-001: MimoHarness 组装 mimo run 命令，直传 prompt 与切片，effort 经 --variant 传递"""
    cell = GridCell(
        scenario="200k",
        model="mimo-v2.6-flash",
        effort="high",
        source="mimo-official",
        harness="mimo-code",
        alias="xiaomi/mimo-v2.6-flash",
    )
    prompt = "分析分层架构"
    fixture = "DJANGO_200K_MOCK_CONTENT" * 10
    cmd = build_mimo_cmd(cell, prompt, fixture, bin_name="mimo")

    assert "mimo" in cmd[0]
    assert "run" in cmd
    assert "--dir" in cmd
    assert "--format" in cmd
    f_idx = cmd.index("--format")
    assert cmd[f_idx + 1] == "json"

    assert "-m" in cmd
    m_idx = cmd.index("-m")
    assert cmd[m_idx + 1] == "xiaomi/mimo-v2.6-flash"

    # mimo-code 支持设置思考强度，effort 经 --variant 传递（已实测 xiaomi 接受 high）
    assert "--variant" in cmd
    v_idx = cmd.index("--variant")
    assert cmd[v_idx + 1] == "high"

    full_text = cmd[-1]
    assert prompt in full_text
    assert fixture in full_text


def test_parse_mimo_metrics():
    """AC-002: parse_mimo_metrics 复用 opencode 事件协议，解析 TTFT、生成窗口与 token usage"""
    lines = [
        (0.1, '{"type":"step-start","part":{}}'),
        (1.5, '{"type":"reasoning","part":{"type":"reasoning","text":"先想一下"}}'),
        (2.0, '{"type":"text","part":{"type":"text","text":"架构如下","time":{"start":1500,"end":6500}}}'),
        (6.6, '{"type":"step-finish","part":{"tokens":{"input":200000,"output":850}}}'),
    ]

    ttft, decode_window, source, in_toks, out_toks, used_tools = parse_mimo_metrics(lines)

    assert ttft == 1.5
    assert decode_window == 5.0
    assert source == "mimo:text_part_time"
    assert in_toks == 200000
    assert out_toks == 850
    assert not used_tools


def test_harness_registry_mimo():
    """AC-003: get_harness 支持 mimo-code 与 mimo 别名"""
    h1 = get_harness("mimo-code")
    h2 = get_harness("mimo")

    assert isinstance(h1, MimoHarness)
    assert isinstance(h2, MimoHarness)


def test_config_contains_mimo_code_cells():
    """AC-004: 主配置包含 mimo-code 驱动的 2.6 flash/pro 格子"""
    from agent_speed.config import load_benchmark_config
    cfg = load_benchmark_config()
    mimo_cells = [c for c in cfg.cells if c.harness == "mimo-code"]
    assert len(mimo_cells) == 2

    by_model = {c.model: c for c in mimo_cells}
    assert by_model["mimo-v2.6-flash"].resolved_cli_model == "xiaomi/mimo-v2.6-flash"
    assert by_model["mimo-v2.6-pro"].resolved_cli_model == "xiaomi/mimo-v2.6-pro"

    for c in mimo_cells:
        assert c.queue is not None
        assert c.scenario == "200k"
        assert c.effort == "high"
