"""t009: scripts/update_pricing.py 对齐 / 覆盖 / 产物契约测试。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "update_pricing.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pricing"
GITIGNORE_PATH = ROOT / ".gitignore"
AGENTS_PATH = ROOT / "AGENTS.md"
GUIDE_PATH = ROOT / "docs" / "guides" / "pricing_update.md"

# 保证可 import 脚本内函数
sys.path.insert(0, str(ROOT / "scripts"))
import update_pricing as up  # noqa: E402


REQUIRED_FIELDS = {
    "plan",
    "model",
    "source",
    "billing",
    "price_usd",
    "monthly_tokens",
    "monthly_yi",
    "real_usd_per_mtok",
    "unmetered",
    "promo_until",
    "confidence",
    "citation",
    "notes",
}


@pytest.fixture()
def fixture_models() -> list[dict]:
    return json.loads((FIXTURES / "models.json").read_text(encoding="utf-8"))


@pytest.fixture()
def fixture_adopted() -> list[dict]:
    with (FIXTURES / "adopted.csv").open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_align_exact_id_and_alias(fixture_models, fixture_adopted):
    """AC-003：id 与 pricing_aliases 精确命中进 latest；大小写不同进 unmatched。"""
    latest, unmatched = up.build_pricing(fixture_models, fixture_adopted)
    models = {r["model"] for r in latest}
    assert "deepseek-v4.1-flash" in models
    assert "MiniMax-M3" in models  # via alias minimax-m3
    assert "gpt-6-sol" in models

    unmatched_served = {u["served_model"] for u in unmatched}
    assert "UNKNOWN-MODEL" in unmatched_served
    assert "Deepseek-v4.1-flash" in unmatched_served  # case mismatch
    assert all(u["served_model"] not in {r.get("served_model") for r in latest} for u in unmatched)
    # latest 不含未对齐 served
    for u in unmatched:
        assert not any(
            r["model"] == "Deepseek-v4.1-flash" for r in latest
        )


def test_pricing_row_fields_and_sortable(fixture_models, fixture_adopted):
    """AC-002：字段齐全；model 属于模型表；可按 real_usd_per_mtok 排序。"""
    latest, _ = up.build_pricing(fixture_models, fixture_adopted)
    table_ids = {m["id"] for m in fixture_models}
    assert latest
    for row in latest:
        assert REQUIRED_FIELDS <= set(row.keys())
        assert row["model"] in table_ids
    reals = [r["real_usd_per_mtok"] for r in latest if r["real_usd_per_mtok"] is not None]
    assert reals == sorted(reals)


def test_opencode_deepseek_override(fixture_models, fixture_adopted):
    """AC-004：OpenCode Go × deepseek- 额度 ×4，月费不变，真实单价变小，notes 含覆盖说明。"""
    latest, _ = up.build_pricing(fixture_models, fixture_adopted)
    row = next(r for r in latest if r["plan"] == "OpenCode Go" and r["model"] == "deepseek-v4.1-flash")
    assert row["price_usd"] == 10.0
    assert row["monthly_tokens"] == 1552800000 * 4
    assert row["monthly_yi"] == pytest.approx(15.528 * 4)
    expected_real = 10.0 / (row["monthly_tokens"] / 1e6)
    assert row["real_usd_per_mtok"] == pytest.approx(expected_real)
    assert row["real_usd_per_mtok"] < 0.0064399794
    assert row["notes"] and "本仓覆盖" in row["notes"] and "15" in row["notes"] and "60" in row["notes"]
    assert row["source"] == "opencode-go"


def test_command_code_goat_override(fixture_models, fixture_adopted):
    """AC-005：Command Code GOAT 月费 10.78，额度不变，真实单价按 10.78 重算。"""
    latest, _ = up.build_pricing(fixture_models, fixture_adopted)
    row = next(r for r in latest if r["plan"] == "Command Code GOAT" and r["model"] == "gpt-6-sol")
    assert row["price_usd"] == 10.78
    assert row["monthly_tokens"] == 92100000
    assert row["monthly_yi"] == pytest.approx(0.921)
    assert row["real_usd_per_mtok"] == pytest.approx(10.78 / (92100000 / 1e6))
    assert row["notes"] and "本仓覆盖" in row["notes"] and "10.78" in row["notes"]


def test_cli_writes_outputs(tmp_path, fixture_models):
    """AC-001：脚本写入可解析的 pricing_latest / pricing_unmatched。"""
    models_path = tmp_path / "models.json"
    models_path.write_text(json.dumps(fixture_models, ensure_ascii=False), encoding="utf-8")
    out_latest = tmp_path / "pricing_latest.json"
    out_unmatched = tmp_path / "pricing_unmatched.json"
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--csv",
            str(FIXTURES / "adopted.csv"),
            "--models",
            str(models_path),
            "--out-latest",
            str(out_latest),
            "--out-unmatched",
            str(out_unmatched),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    latest = json.loads(out_latest.read_text(encoding="utf-8"))
    unmatched = json.loads(out_unmatched.read_text(encoding="utf-8"))
    assert isinstance(latest, list) and latest
    assert isinstance(unmatched, list) and unmatched


def test_guide_and_agents_and_gitignore():
    """AC-006 / AC-007：指南存在；AGENTS/gitignore 声明两份定价产物与脚本。"""
    assert GUIDE_PATH.is_file()
    guide = GUIDE_PATH.read_text(encoding="utf-8")
    assert "update_pricing.py" in guide
    assert "覆盖" in guide
    assert "未对齐" in guide

    agents = AGENTS_PATH.read_text(encoding="utf-8")
    assert "`scripts/update_pricing.py`" in agents or "update_pricing.py" in agents
    assert "pricing_latest.json" in agents
    assert "pricing_unmatched.json" in agents

    gi = GITIGNORE_PATH.read_text(encoding="utf-8")
    assert "!/data/pricing_latest.json" in gi
    assert "!/data/pricing_unmatched.json" in gi
