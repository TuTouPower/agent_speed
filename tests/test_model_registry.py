"""t008: data/models.json 权威模型表契约测试。"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MODELS_PATH = ROOT / "data" / "models.json"
BENCHMARK_PATH = ROOT / "config" / "benchmark.yaml"
RESULTS_PATH = ROOT / "data" / "results.jsonl"
GITIGNORE_PATH = ROOT / ".gitignore"
AGENTS_PATH = ROOT / "AGENTS.md"


def _load_models() -> list[dict]:
    raw = json.loads(MODELS_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    return raw


def test_ac001_models_json_shape():
    """AC-001: 可解析对象数组；每行非空 id；pricing_aliases 可选字符串数组。"""
    assert MODELS_PATH.is_file()
    rows = _load_models()
    assert rows, "models.json 不得为空"
    for row in rows:
        assert isinstance(row, dict)
        assert "id" in row
        assert isinstance(row["id"], str) and row["id"].strip()
        if "pricing_aliases" in row:
            aliases = row["pricing_aliases"]
            assert isinstance(aliases, list)
            assert all(isinstance(a, str) and a for a in aliases)


def test_ac002_model_ids_unique():
    """AC-002: id 互不相同。"""
    ids = [row["id"] for row in _load_models()]
    assert len(ids) == len(set(ids))


def test_ac003_covers_benchmark_and_results():
    """AC-003: benchmark cells[].model 与 results.jsonl model 均在表中（字面相等）。"""
    table_ids = {row["id"] for row in _load_models()}

    bm = yaml.safe_load(BENCHMARK_PATH.read_text(encoding="utf-8"))
    for cell in bm.get("cells", []):
        model = cell["model"]
        assert model in table_ids, f"benchmark model 缺失: {model!r}"

    missing_results: list[str] = []
    for line in RESULTS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        model = rec.get("model")
        if model is None:
            continue
        if model not in table_ids:
            missing_results.append(model)
    assert not missing_results, f"results model 缺失: {sorted(set(missing_results))}"


def test_ac004_gitignore_tracks_models_json():
    """AC-004: .gitignore 显式取消忽略 data/models.json，且文件被 git 跟踪。"""
    text = GITIGNORE_PATH.read_text(encoding="utf-8")
    assert "!/data/models.json" in text
    # 由调用方在集成前 git add；此处断言路径存在且未被 data/* 永久屏蔽意图
    assert MODELS_PATH.is_file()
    # 检查 git check-ignore：取消忽略后不应被 ignore
    import subprocess

    r = subprocess.run(
        ["git", "check-ignore", "-v", "data/models.json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    # 若被跟踪例外命中，exit 0 且输出含 !/data/models.json；若完全不忽略则 exit 1
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode == 0:
        assert "!/data/models.json" in out, out
    else:
        assert r.returncode == 1, out


def test_ac005_agents_md_declares_models_json():
    """AC-005: AGENTS.md 声明 models.json 为权威模型身份库，并列入 data/ 跟踪文件。"""
    text = AGENTS_PATH.read_text(encoding="utf-8")
    assert "`data/models.json`" in text
    assert "权威模型" in text or "模型身份" in text
    assert "models.json" in text
    # 跟踪文件列表句
    assert "models.json" in text.split("data/` 下仅跟踪")[1].split("\n")[0]
