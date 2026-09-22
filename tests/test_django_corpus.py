import json
from pathlib import Path
import tiktoken

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"
PROMPTS_DIR = REPO_ROOT / "prompts"


def test_django_manifest_exclusion_rules():
    """AC-001: 纳入的文件只含源码(django/)与文档(docs/)，清单中无 tests/、migrations/、locale/、生成文件"""
    for tier in ["10k", "100k", "200k"]:
        manifest_path = FIXTURES_DIR / f"django_{tier}_manifest.json"
        assert manifest_path.exists(), f"Missing manifest for {tier}"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "files" in data
        assert len(data["files"]) > 0

        for f in data["files"]:
            p = f["path"]
            assert p.startswith("django/") or p.startswith("docs/"), f"Unexpected file root: {p}"
            assert "/tests/" not in p and not p.startswith("tests/") and "/js_tests/" not in p, f"Tests not excluded: {p}"
            assert Path(p).name != "tests.py" and not Path(p).name.startswith("test_"), f"Test file not excluded: {p}"
            assert "/migrations/" not in p and not p.startswith("migrations/"), f"Migrations not excluded: {p}"
            assert "/locale/" not in p and not p.startswith("locale/"), f"Locale not excluded: {p}"
            ext = Path(p).suffix.lower()
            assert ext not in [".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".mo", ".po", ".pyc"], f"Binary/asset not excluded: {p}"
            assert Path(p).name not in ["Makefile", "make.bat", "spelling_wordlist", "conf.py", "lint.py"], f"Build artifact not excluded: {p}"


def test_django_slice_token_counts():
    """AC-002: 产出 10K/100K/200K 三档切片；各档 cl100k token 计数与档位一致，最后一文件允许截断"""
    enc = tiktoken.get_encoding("cl100k_base")
    expected = {
        "10k": 10000,
        "100k": 100000,
        "200k": 200000,
    }
    for tier, target in expected.items():
        slice_path = FIXTURES_DIR / f"django_{tier}.txt"
        manifest_path = FIXTURES_DIR / f"django_{tier}_manifest.json"
        assert slice_path.exists(), f"Missing slice for {tier}"
        assert manifest_path.exists(), f"Missing manifest for {tier}"

        text = slice_path.read_text(encoding="utf-8")
        tokens = len(enc.encode(text))
        assert tokens == target, f"{tier} expected {target} tokens, got {tokens}"

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["target_tokens"] == target
        assert manifest["actual_tokens"] == target
        assert manifest["encoding"] == "cl100k_base"

        # 最后一文件 truncated 可以为 True，其余为 False
        files = manifest["files"]
        for item in files[:-1]:
            assert not item["truncated"], f"Intermediate file {item['path']} should not be truncated"
        assert files[-1]["truncated"] is True


def test_django_slice_byte_prefix_nesting():
    """AC-003: 10K 切片是 100K 切片的字节前缀，100K 切片是 200K 切片的字节前缀"""
    b10 = (FIXTURES_DIR / "django_10k.txt").read_bytes()
    b100 = (FIXTURES_DIR / "django_100k.txt").read_bytes()
    b200 = (FIXTURES_DIR / "django_200k.txt").read_bytes()

    assert b100.startswith(b10), "10k slice is not byte prefix of 100k slice"
    assert b200.startswith(b100), "100k slice is not byte prefix of 200k slice"


def test_task_prompt_ac005():
    """AC-005: 任务文本为单一公开文件：中文、自然长度，要求分层/模块职责/数据流/技术选型，禁止工具与读写文件"""
    prompt_file = PROMPTS_DIR / "task_200k.md"
    assert prompt_file.exists(), "task_200k.md does not exist in prompts/"
    text = prompt_file.read_text(encoding="utf-8")

    # 包含中文
    assert any("\u4e00" <= c <= "\u9fff" for c in text), "Prompt must be in Chinese"

    # 四大内容要素
    assert "分层" in text, "Prompt must require system layering"
    assert "模块职责" in text or "职责" in text, "Prompt must require module responsibilities"
    assert "数据流" in text, "Prompt must require data flow"
    assert "技术选型" in text or "选型" in text, "Prompt must require tech choice analysis"

    # 约束
    assert "工具" in text and ("禁止" in text or "严禁" in text or "不要" in text), "Prompt must forbid tools"
    assert "读写" in text and ("禁止" in text or "严禁" in text or "不要" in text), "Prompt must forbid file IO"


def test_ac004_tracked_and_clean():
    """AC-004: 切片正文、manifest、任务文本必须存在且无私有语料"""
    for tier in ["10k", "100k", "200k"]:
        txt = FIXTURES_DIR / f"django_{tier}.txt"
        man = FIXTURES_DIR / f"django_{tier}_manifest.json"
        assert txt.exists() and txt.stat().st_size > 0
        assert man.exists() and man.stat().st_size > 0

    assert (PROMPTS_DIR / "task_200k.md").exists()
    assert (FIXTURES_DIR / "task_200k.md").exists()
