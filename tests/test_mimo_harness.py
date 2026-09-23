import shutil

from agent_speed.models import GridCell
from agent_speed.harness.mimo import (
    MIMO_ARGV_MAX_BYTES,
    MimoHarness,
    build_mimo_cmd,
)
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


def _big_cell():
    return GridCell(
        scenario="200k",
        model="mimo-v2.6-flash",
        effort="high",
        source="mimo-official",
        harness="mimo-code",
        alias="xiaomi/mimo-v2.6-flash",
    )


def _node_script(tmp_path, name="mimo"):
    p = tmp_path / name
    p.write_text("#!/opt/homebrew/opt/node/bin/node\n// fake mimo cli\n", encoding="utf-8")
    return str(p)


def _patch_which(monkeypatch, mapping):
    real_which = shutil.which

    def fake(name, *args, **kwargs):
        if name in mapping:
            return mapping[name]
        return real_which(name, *args, **kwargs)

    monkeypatch.setattr(shutil, "which", fake)


def test_big_message_wraps_node_stack(tmp_path, monkeypatch):
    """AC-005: 超 850KB 的整包消息改经 node --stack-size 拉起，切片不截断"""
    cell = _big_cell()
    fixture = "x" * (MIMO_ARGV_MAX_BYTES + 1)
    mimo_path = _node_script(tmp_path)
    _patch_which(monkeypatch, {"node": "/usr/bin/node"})
    monkeypatch.delenv("MIMO_NODE_STACK", raising=False)

    cmd = build_mimo_cmd(cell, "prompt", fixture, bin_name=mimo_path)

    assert cmd[0] == "/usr/bin/node"
    assert cmd[1] == "--stack-size=8192"
    assert cmd[2] == mimo_path
    assert cmd[3] == "run"
    assert "--variant" in cmd and "high" in cmd
    assert cmd[-1].endswith(fixture) and "prompt" in cmd[-1]


def test_big_message_no_node_falls_back(tmp_path, monkeypatch):
    """AC-006: 无 node 可用时回退直调（失败如实透出，不静默截断）"""
    cell = _big_cell()
    fixture = "x" * (MIMO_ARGV_MAX_BYTES + 1)
    mimo_path = _node_script(tmp_path)
    _patch_which(monkeypatch, {"node": None})

    cmd = build_mimo_cmd(cell, "prompt", fixture, bin_name=mimo_path)

    assert cmd[0] == mimo_path
    assert cmd[1] == "run"
    assert cmd[-1].endswith(fixture)


def test_at_limit_stays_direct(tmp_path, monkeypatch):
    """AC-007: 恰为上限字节数时仍直调"""
    cell = _big_cell()
    fixture = "x" * (MIMO_ARGV_MAX_BYTES - len("prompt\n\n===== CODE FIXTURE =====\n"))
    mimo_path = _node_script(tmp_path)
    _patch_which(monkeypatch, {"node": "/usr/bin/node"})

    cmd = build_mimo_cmd(cell, "prompt", fixture, bin_name=mimo_path)

    assert cmd[0] == mimo_path


def test_parse_mimo_metrics_cache_read_counts_as_input():
    """AC-008: mimo step-finish 的 input 只含非缓存增量，cache.read 须计入账单输入"""
    lines = [
        (113.6, '{"type":"step-finish","part":{"tokens":{"total":249138,"input":50,'
                 '"output":11117,"reasoning":83,"cache":{"write":0,"read":237888}}}}'),
    ]

    _, _, _, in_toks, out_toks, _ = parse_mimo_metrics(lines)

    assert in_toks == 237938
    assert out_toks == 11117


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
