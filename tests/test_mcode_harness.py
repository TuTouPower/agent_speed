from agent_speed.models import GridCell
from agent_speed.harness.mcode import McodeHarness, build_mcode_cmd
from agent_speed.harness import get_harness
from agent_speed.metrics import parse_mcode_metrics


def _cell(effort=None):
    return GridCell(
        scenario="200k",
        model="MiniMax-M3",
        effort=effort,
        source="minimax-official",
        harness="minimax-code",
        alias="minimax/MiniMax-M3",
    )


def test_mcode_cmd_builder():
    """AC-001: mcode exec 经 stdin 传整包（避 argv 上限），effort 为空时不传 --effort"""
    cell = _cell()
    cmd, stdin_text = build_mcode_cmd(cell, "PROMPT", "FIXTURE" * 10, cwd="/tmp/w", bin_name="mcode")

    assert cmd[0] == "mcode"
    assert cmd[1] == "exec"
    assert "--input" in cmd and "-" in cmd
    assert "--input-format" in cmd and "text" in cmd
    assert "--output-format" in cmd and "stream-json" in cmd
    assert "--permission" in cmd and "off" in cmd
    assert "--timeout" in cmd
    assert "--model" in cmd
    m_idx = cmd.index("--model")
    assert cmd[m_idx + 1] == "minimax/MiniMax-M3"
    # effort 为空：不得出现 --effort（MiniMax-M3 不支持思考强度选择）
    assert "--effort" not in cmd
    # 整包走 stdin，不进 argv
    assert stdin_text == "PROMPT\n\n===== CODE FIXTURE =====\n" + "FIXTURE" * 10
    assert all("FIXTURE" * 10 not in a for a in cmd)


def test_mcode_cmd_effort_passthrough():
    """AC-002: effort 非空时原样透传 --effort"""
    cmd, _ = build_mcode_cmd(_cell(effort="high"), "PROMPT", "", cwd="/tmp/w", bin_name="mcode")
    assert "--effort" in cmd
    assert cmd[cmd.index("--effort") + 1] == "high"


def test_parse_mcode_metrics():
    """AC-003: 解析 TTFT（含 thinking）、正文窗口、usage；工具调用检出"""
    lines = [
        (0.0, '{"type":"exec.started"}'),
        (1.2, '{"type":"item.started","item":{"type":"reasoning","contentDelta":"think"}}'),
        (2.0, '{"type":"item.started","item":{"type":"agent_message","contentDelta":"Hi"}}'),
        (3.0, '{"type":"item.updated","item":{"type":"agent_message","contentDelta":" there"}}'),
        (4.0, '{"type":"item.completed","item":{"type":"agent_message","content":"Hi there"}}'),
        (4.1, '{"type":"turn.completed","usage":{"inputTokens":215260,"outputTokens":6967}}'),
    ]

    ttft, decode_window, source, in_toks, out_toks, used_tools = parse_mcode_metrics(lines)

    assert ttft == 1.2
    assert decode_window == 1.0
    assert source == "mcode:message_window"
    assert in_toks == 215260
    assert out_toks == 6967
    assert not used_tools


def test_parse_mcode_metrics_tool_call():
    """AC-004: tool 类型 item 判为 used_tools"""
    lines = [
        (1.0, '{"type":"item.started","item":{"type":"agent_message","contentDelta":"ok"}}'),
        (2.0, '{"type":"item.started","item":{"type":"tool_call","contentDelta":""}}'),
    ]
    _, _, _, _, _, used_tools = parse_mcode_metrics(lines)
    assert used_tools


def test_harness_registry_mcode():
    """AC-005: get_harness 支持 minimax-code 与 mcode 别名"""
    assert isinstance(get_harness("minimax-code"), McodeHarness)
    assert isinstance(get_harness("mcode"), McodeHarness)


def test_config_contains_minimax_code_cell():
    """AC-006: 主配置含 minimax-code 驱动的 MiniMax-M3 格子（effort 为空）"""
    from agent_speed.config import load_benchmark_config
    cfg = load_benchmark_config()
    cells = [c for c in cfg.cells if c.harness == "minimax-code"]
    assert len(cells) == 1
    c = cells[0]
    assert c.model == "MiniMax-M3"
    assert c.resolved_cli_model == "minimax/MiniMax-M3"
    assert c.effort is None
    assert c.queue == "minimax-official"
