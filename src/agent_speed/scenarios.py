from __future__ import annotations

import dataclasses
from pathlib import Path

from agent_speed.models import GridCell

SENTENCE_PROMPT = "请用中文写一篇 800 到 1200 字的短文，说明关系型数据库里的迁移解决什么问题；不要调用工具，不要读写文件，不要输出思考过程。"

SENTENCE_CL100K = 61
TEN_K_CL100K = 10000
TWO_HUNDRED_K_CL100K = 200000

VALID_SCENARIOS = ("sentence", "10k", "200k")

SCENARIO_CL100K: dict[str, int] = {
    "sentence": SENTENCE_CL100K,
    "10k": TEN_K_CL100K,
    "200k": TWO_HUNDRED_K_CL100K,
}


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
) -> tuple[str, str, Path | None, int]:
    """按档位解析 (prompt_text, fixture_text, fixture_path, cl100k_tokens)。"""
    if scenario not in VALID_SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario!r}, expected one of {VALID_SCENARIOS}")
    root = Path(repo_root) if repo_root is not None else _repo_root()
    if scenario == "sentence":
        return SENTENCE_PROMPT, "", None, SENTENCE_CL100K
    if scenario == "10k":
        prompt = (root / "prompts" / "task_200k.md").read_text(encoding="utf-8")
        fixture_path = root / "fixtures" / "django_10k.txt"
        fixture_text = fixture_path.read_text(encoding="utf-8")
        return prompt, fixture_text, fixture_path, TEN_K_CL100K
    prompt = (root / "prompts" / "task_200k.md").read_text(encoding="utf-8")
    fixture_path = root / "fixtures" / "django_200k.txt"
    fixture_text = fixture_path.read_text(encoding="utf-8")
    return prompt, fixture_text, fixture_path, TWO_HUNDRED_K_CL100K


def apply_scenario_to_cell(cell: GridCell, scenario: str) -> GridCell:
    """将选中档位写入格子的 scenario 与 cl100k_tokens，不增删 model/effort/source/harness 集合。"""
    if scenario not in VALID_SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario!r}")
    return dataclasses.replace(
        cell,
        scenario=scenario,
        cl100k_tokens=SCENARIO_CL100K[scenario],
    )
