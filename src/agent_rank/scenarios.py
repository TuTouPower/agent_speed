from __future__ import annotations

import dataclasses
from pathlib import Path

from agent_rank.models import GridCell

VALID_SCENARIOS = ("sentence", "10k", "200k")


def build_user_message(prompt: str, fixture_text: str | None) -> str:
    """组装送入模型的用户内容。fixture 为空时只返回 prompt，不附加分隔标记。"""
    if not fixture_text:
        return prompt
    return f"{prompt}\n\n===== CODE FIXTURE =====\n{fixture_text}"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_scenario_inputs(
    scenario: str,
    repo_root: Path | None = None,
    scenarios_cfg: dict | None = None,
) -> tuple[str, str, Path | None, int]:
    """按档位解析 (prompt_text, fixture_text, fixture_path, cl100k_tokens)。

    输入映射唯一真相为配置 `scenarios:` 节（config.py 加载时已校验结构）；
    scenarios_cfg 缺失或缺档时显式报错，不设代码内置回退。
    """
    if scenario not in VALID_SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario!r}, expected one of {VALID_SCENARIOS}")
    if not isinstance(scenarios_cfg, dict) or scenario not in scenarios_cfg:
        raise ValueError(f"scenarios_cfg 缺 `{scenario}` 档输入映射")
    entry = scenarios_cfg[scenario]
    root = Path(repo_root) if repo_root is not None else _repo_root()
    if entry.get("prompt_file"):
        prompt_text = (root / entry["prompt_file"]).read_text(encoding="utf-8")
    else:
        prompt_text = entry.get("prompt_text") or ""
    fixture_file = entry.get("fixture_file")
    if fixture_file:
        fixture_path = root / fixture_file
        fixture_text = fixture_path.read_text(encoding="utf-8")
    else:
        fixture_path, fixture_text = None, ""
    return prompt_text, fixture_text, fixture_path, entry["cl100k_tokens"]


def apply_scenario_to_cell(cell: GridCell, scenario: str, scenarios_cfg: dict | None = None) -> GridCell:
    """将选中档位写入格子的 scenario 与 cl100k_tokens，不增删 model/effort/source/harness 集合。"""
    if scenario not in VALID_SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario!r}")
    if not isinstance(scenarios_cfg, dict) or scenario not in scenarios_cfg:
        raise ValueError(f"scenarios_cfg 缺 `{scenario}` 档输入映射")
    return dataclasses.replace(
        cell,
        scenario=scenario,
        cl100k_tokens=scenarios_cfg[scenario]["cl100k_tokens"],
    )
