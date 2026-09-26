import pytest
from pathlib import Path
from agent_rank.models import GridCell
from agent_rank.harness.kimi import build_kimi_cmd, get_kimi_global_effort


def test_kimi_argv_direct_and_no_tools():
    """AC-005: kimi 经 -p argv 直传完整任务+切片，不使用读文件工具"""
    cell = GridCell("200k", "kimi-code/k3", "high", "moonshot", "kimi")
    prompt = "说明分层与职责"
    fixture_content = "SAMPLE_DJANGO_200K_CONTENT" * 10

    cmd = build_kimi_cmd(cell, prompt, fixture_content)

    # 包含 -p
    assert "-p" in cmd
    p_idx = cmd.index("-p")
    full_arg = cmd[p_idx + 1]

    # 直传了 prompt 与 fixture 内容
    assert prompt in full_arg
    assert fixture_content in full_arg
    # 明确禁止工具
    assert "--output-format" in cmd
    assert "stream-json" in cmd


def test_kimi_effort_mismatch(monkeypatch, tmp_path):
    """AC-005: effort 与全局配置不符时跳过并记录原因"""
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[thinking]\neffort = "high"\n', encoding="utf-8")

    monkeypatch.setattr("agent_rank.harness.kimi.get_kimi_config_path", lambda: cfg_file)

    assert get_kimi_global_effort() == "high"

    # 请求 max，但全局是 high
    cell = GridCell("200k", "kimi-code/k3", "max", "moonshot", "kimi")
    from agent_rank.harness.kimi import KimiHarness
    harness = KimiHarness()
    record = harness.run(cell, rep=1, batch_id="b1", prompt="test", fixture_text="fake", cwd=tmp_path)

    assert record.status == "skipped"
    assert record.exclude_reason == "effort mismatch: requested 'max' != global 'high'"
