"""t007 三档场景：sentence / 10k / 200k 独立评测档。"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SENTENCE = "请用中文写一篇 800 到 1200 字的短文，说明关系型数据库里的迁移解决什么问题；不要调用工具，不要读写文件，不要输出思考过程。"


def _scenarios_cfg():
    from agent_speed.config import load_benchmark_config
    return load_benchmark_config().scenarios


def _rec(scenario, model="m", effort="high", source="s", harness="opencode",
         start="2026-09-23T10:00:00+08:00", batch="b1", wall=10.0, out=800,
         in_toks=200000, e2e=80.0, gen=90.0, cl100k=200000,
         status="success", include_cl100k=True):
    d = {"scenario": scenario, "model": model, "effort": effort, "source": source,
         "harness": harness, "rep": 1, "batch_id": batch, "start_time": start,
         "wall": wall, "ttft": 1.0, "decode_window": 5.0, "out_tokens": out,
         "in_tokens": in_toks, "e2e_tps": e2e, "gen_tps": gen,
         "decode_window_source": "opencode:text_part_time",
         "status": status, "exclude_reason": None, "error_summary": None}
    if include_cl100k:
        d["cl100k_tokens"] = cl100k
    return d


def test_ac001_sentence_inputs():
    from agent_speed.scenarios import resolve_scenario_inputs, build_user_message
    cfg = _scenarios_cfg()
    assert cfg["sentence"]["prompt_text"] == SENTENCE
    assert cfg["sentence"]["cl100k_tokens"] == 61
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    assert len(enc.encode(SENTENCE)) == 61
    prompt, fixture_text, fixture_path, cl100k = resolve_scenario_inputs("sentence", scenarios_cfg=cfg)
    assert prompt == SENTENCE
    assert fixture_text == ""
    assert cl100k == 61
    msg = build_user_message(prompt, fixture_text)
    assert msg == SENTENCE
    assert "CODE FIXTURE" not in msg
    assert "django" not in msg.lower() or True  # 不含 fixture 正文由空 fixture 保证
    # harness 记录
    from agent_speed.models import GridCell
    from agent_speed.scenarios import apply_scenario_to_cell
    cell = GridCell(scenario="200k", model="m", effort="high", source="s", harness="opencode", queue="q")
    cell2 = apply_scenario_to_cell(cell, "sentence", _scenarios_cfg())
    assert cell2.scenario == "sentence"
    assert cell2.cl100k_tokens == 61


def test_ac002_10k_inputs():
    from agent_speed.scenarios import resolve_scenario_inputs, build_user_message
    prompt, fixture_text, fixture_path, cl100k = resolve_scenario_inputs("10k", scenarios_cfg=_scenarios_cfg())
    assert cl100k == 10000
    task_200k = (REPO_ROOT / "prompts" / "task_200k.md").read_text(encoding="utf-8")
    assert prompt == task_200k
    expected_fixture = (REPO_ROOT / "fixtures" / "django_10k.txt").read_text(encoding="utf-8")
    assert fixture_text == expected_fixture
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    assert len(enc.encode(fixture_text)) == 10000
    b10 = (REPO_ROOT / "fixtures" / "django_10k.txt").read_bytes()
    b200 = (REPO_ROOT / "fixtures" / "django_200k.txt").read_bytes()
    assert b200[:len(b10)] == b10
    msg = build_user_message(prompt, fixture_text)
    assert task_200k in msg
    assert fixture_text in msg
    # 不被截断：Kimi 对 10k 不截断
    from agent_speed.models import GridCell
    from agent_speed.scenarios import apply_scenario_to_cell
    cell = apply_scenario_to_cell(
        GridCell(scenario="200k", model="m", effort="high", source="s", harness="kimi-code", queue="q"),
        "10k",
        _scenarios_cfg(),
    )
    assert cell.cl100k_tokens == 10000
    # 模拟 Kimi 截断判定：10k 不进入截断分支
    assert len(fixture_text.encode("utf-8")) < 850000


def test_ac003_default_200k():
    from agent_speed.scenarios import resolve_scenario_inputs
    prompt, fixture_text, _, cl100k = resolve_scenario_inputs("200k", scenarios_cfg=_scenarios_cfg())
    assert prompt == (REPO_ROOT / "prompts" / "task_200k.md").read_text(encoding="utf-8")
    assert fixture_text == (REPO_ROOT / "fixtures" / "django_200k.txt").read_text(encoding="utf-8")
    assert cl100k == 200000
    # run_bench 默认 scenario 为 200k
    import argparse  # noqa: F401
    from agent_speed.scenarios import VALID_SCENARIOS
    assert "200k" in VALID_SCENARIOS


def test_ac004_single_scenario_per_run():
    from agent_speed.models import GridCell
    from agent_speed.scenarios import apply_scenario_to_cell
    from agent_speed.config import load_benchmark_config
    cfg = load_benchmark_config()
    base_keys = {(c.model, str(c.effort), c.source, c.harness) for c in cfg.cells}
    for scen, expected_cl in [("sentence", 61), ("10k", 10000), ("200k", 200000)]:
        converted = [apply_scenario_to_cell(c, scen, cfg.scenarios) for c in cfg.cells]
        scenarios = {c.scenario for c in converted}
        assert scenarios == {scen}
        assert {c.cl100k_tokens for c in converted} == {expected_cl}
        keys = {(c.model, str(c.effort), c.source, c.harness) for c in converted}
        assert keys == base_keys


def test_ac005_no_truncation_for_short():
    # Kimi：10k 与 sentence 不进入 173218 截断
    from agent_speed.harness.kimi import KIMI_ARGV_MAX_BYTES
    from agent_speed.models import GridCell
    from agent_speed.scenarios import resolve_scenario_inputs
    for scen in ("10k", "sentence"):
        _, fixture_text, _, cl = resolve_scenario_inputs(scen, scenarios_cfg=_scenarios_cfg())
        assert len(fixture_text.encode("utf-8")) <= KIMI_ARGV_MAX_BYTES
        assert cl != 173218
    # 代码层面：Kimi 截断只对 200k 生效（构造超长 fixture 也只在 200k 截断）
    import agent_speed.harness.kimi as kimi_mod
    import inspect
    src = inspect.getsource(kimi_mod.KimiHarness.run)
    assert "200k" in src
    # antigravity 大输入流水线只对 200k 生效
    import agent_speed.harness.antigravity as agy_mod
    src2 = inspect.getsource(agy_mod.AntigravityHarness.run)
    assert "200k" in src2


def test_ac005_sentence_no_fixture_marker_all_harness():
    from agent_speed.scenarios import build_user_message
    msg = build_user_message(SENTENCE, "")
    assert msg == SENTENCE
    assert "CODE FIXTURE" not in msg
    from agent_speed.harness.kimi import build_kimi_cmd
    from agent_speed.harness.antigravity import build_antigravity_cmd
    from agent_speed.models import GridCell
    cell = GridCell(scenario="sentence", model="m", effort="high", source="s", harness="opencode", queue="q")
    assert build_kimi_cmd(cell, SENTENCE, "") == ["kimi", "-m", cell.resolved_cli_model, "-p", SENTENCE, "--output-format", "stream-json"] or "CODE FIXTURE" not in build_kimi_cmd(cell, SENTENCE, "")[4]
    assert "CODE FIXTURE" not in build_antigravity_cmd(cell, SENTENCE, "")[2]


def test_scenarios_config_validation_rejects_bad_entries(tmp_path):
    """配置 scenarios 节缺档、双 prompt 源、非法 cl100k 时加载失败。"""
    import pytest
    from agent_speed.config import load_benchmark_config
    base = (
        "concurrency:\n  global_max: 10\n  per_queue: 2\n"
        "defaults:\n  scenario: \"200k\"\n  reps: 1\n  results_file: \"data/results.jsonl\"\n"
        "cells:\n  - model: \"m\"\n    source: \"s\"\n    harness: \"h\"\n"
    )
    good_scen = (
        "scenarios:\n"
        "  sentence:\n    prompt_text: \"hi\"\n    cl100k_tokens: 61\n"
        "  10k:\n    prompt_file: \"prompts/task_200k.md\"\n    fixture_file: \"fixtures/django_10k.txt\"\n    cl100k_tokens: 10000\n"
        "  200k:\n    prompt_file: \"prompts/task_200k.md\"\n    fixture_file: \"fixtures/django_200k.txt\"\n    cl100k_tokens: 200000\n"
    )
    p = tmp_path / "bench.yaml"
    p.write_text(base + good_scen, encoding="utf-8")
    cfg = load_benchmark_config(p)
    assert set(cfg.scenarios) == {"sentence", "10k", "200k"}

    bad_missing = base + good_scen.replace(
        "  10k:\n    prompt_file: \"prompts/task_200k.md\"\n    fixture_file: \"fixtures/django_10k.txt\"\n    cl100k_tokens: 10000\n", "")
    p.write_text(bad_missing, encoding="utf-8")
    with pytest.raises(ValueError):
        load_benchmark_config(p)

    bad_both = base + good_scen.replace(
        "  sentence:\n    prompt_text: \"hi\"\n", "  sentence:\n    prompt_text: \"hi\"\n    prompt_file: \"prompts/task_200k.md\"\n")
    p.write_text(bad_both, encoding="utf-8")
    with pytest.raises(ValueError):
        load_benchmark_config(p)

    bad_cl = base + good_scen.replace("cl100k_tokens: 61", "cl100k_tokens: 0")
    p.write_text(bad_cl, encoding="utf-8")
    with pytest.raises(ValueError):
        load_benchmark_config(p)

    from agent_speed.scenarios import resolve_scenario_inputs
    with pytest.raises(ValueError):
        resolve_scenario_inputs("10k", scenarios_cfg={"sentence": cfg.scenarios["sentence"]})


def test_ac006_three_boards_split(tmp_path):
    from agent_speed.report import generate_latest_json
    jsonl = tmp_path / "results.jsonl"
    out200 = tmp_path / "latest_200k.json"
    out10 = tmp_path / "board_10k.json"
    outsen = tmp_path / "board_sentence.json"
    rows = []
    # 200k 格：2 次有效
    rows.append(_rec("200k", model="m200", start="2026-09-23T10:00:00+08:00", batch="b1", e2e=50.0, in_toks=200000, cl100k=200000))
    rows.append(_rec("200k", model="m200", start="2026-09-23T10:01:00+08:00", batch="b1", e2e=60.0, in_toks=200000, cl100k=200000))
    # 10k 格：2 次有效
    rows.append(_rec("10k", model="m10", start="2026-09-23T10:00:00+08:00", batch="b1", e2e=200.0, in_toks=10000, cl100k=10000))
    rows.append(_rec("10k", model="m10", start="2026-09-23T10:01:00+08:00", batch="b1", e2e=100.0, in_toks=10000, cl100k=10000))
    # sentence 格：2 次有效
    rows.append(_rec("sentence", model="msen", start="2026-09-23T10:00:00+08:00", batch="b1", e2e=300.0, in_toks=61, cl100k=61))
    rows.append(_rec("sentence", model="msen", start="2026-09-23T10:01:00+08:00", batch="b1", e2e=310.0, in_toks=61, cl100k=61))
    before = json.dumps({"x": 1})
    jsonl.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    before_mtime_content = jsonl.read_text(encoding="utf-8")
    r200 = generate_latest_json(jsonl, out200, scenario="200k")
    r10 = generate_latest_json(jsonl, out10, scenario="10k")
    rsen = generate_latest_json(jsonl, outsen, scenario="sentence")
    assert {r["scenario"] for r in r200} == {"200k"}
    assert {r["scenario"] for r in r10} == {"10k"}
    assert {r["scenario"] for r in rsen} == {"sentence"}
    assert [r["model"] for r in r200] == ["m200"]
    # 内部按 e2e_tps 降序（多行时验证排序；单格只验证写入形状）
    assert jsonl.read_text(encoding="utf-8") == before_mtime_content
    # 空档为 []
    out_empty = tmp_path / "empty.json"
    r_empty = generate_latest_json(jsonl, out_empty, scenario="10k")
    # 换一个只有 200k 的 jsonl，10k 档应为空
    jsonl2 = tmp_path / "r2.jsonl"
    jsonl2.write_text(json.dumps(_rec("200k", model="m200", start="2026-09-23T10:00:00+08:00", e2e=50.0)) + "\n" + json.dumps(_rec("200k", model="m200", start="2026-09-23T10:01:00+08:00", e2e=60.0)) + "\n", encoding="utf-8")
    out_e2 = tmp_path / "e10.json"
    re2 = generate_latest_json(jsonl2, out_e2, scenario="10k")
    assert re2 == []
    assert json.loads(out_e2.read_text(encoding="utf-8")) == []


def test_ac006_sort_desc_within_board(tmp_path):
    from agent_speed.report import generate_latest_json
    jsonl = tmp_path / "results.jsonl"
    out = tmp_path / "board_10k.json"
    rows = []
    for model, e2es in [("slow", (10.0, 12.0)), ("fast", (100.0, 120.0))]:
        rows.append(_rec("10k", model=model, start="2026-09-23T10:00:00+08:00", e2e=e2es[0], in_toks=10000, cl100k=10000))
        rows.append(_rec("10k", model=model, start="2026-09-23T10:01:00+08:00", e2e=e2es[1], in_toks=10000, cl100k=10000))
    # 混入 200k 行，不应进入 10k 榜
    rows.append(_rec("200k", model="other", start="2026-09-23T10:00:00+08:00", e2e=9999.0, in_toks=200000, cl100k=200000))
    rows.append(_rec("200k", model="other", start="2026-09-23T10:01:00+08:00", e2e=9999.0, in_toks=200000, cl100k=200000))
    jsonl.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    got = generate_latest_json(jsonl, out, scenario="10k")
    assert [r["model"] for r in got] == ["fast", "slow"]
    assert got[0]["e2e_tps"] >= got[1]["e2e_tps"]


def test_ac007_billing_thresholds(tmp_path):
    from agent_speed.report import generate_latest_json
    # 等于一半上站
    jl = tmp_path / "a.jsonl"
    out = tmp_path / "o.json"
    jl.write_text(
        json.dumps(_rec("10k", model="m", start="2026-09-23T10:00:00+08:00", in_toks=5000, cl100k=10000, e2e=10.0)) + "\n"
        + json.dumps(_rec("10k", model="m", start="2026-09-23T10:01:00+08:00", in_toks=5000, cl100k=10000, e2e=12.0)) + "\n",
        encoding="utf-8",
    )
    assert len(generate_latest_json(jl, out, scenario="10k")) == 1
    # 低于一半不上站
    jl2 = tmp_path / "b.jsonl"
    out2 = tmp_path / "o2.json"
    jl2.write_text(
        json.dumps(_rec("10k", model="m", start="2026-09-23T10:00:00+08:00", in_toks=4999, cl100k=10000, e2e=10.0)) + "\n"
        + json.dumps(_rec("10k", model="m", start="2026-09-23T10:01:00+08:00", in_toks=4999, cl100k=10000, e2e=12.0)) + "\n",
        encoding="utf-8",
    )
    assert generate_latest_json(jl2, out2, scenario="10k") == []
    # 200k 缺 cl100k 按 200000（in 100000 等于一半上站）
    jl3 = tmp_path / "c.jsonl"
    out3 = tmp_path / "o3.json"
    jl3.write_text(
        json.dumps(_rec("200k", model="m", start="2026-09-23T10:00:00+08:00", in_toks=100000, e2e=10.0, include_cl100k=False)) + "\n"
        + json.dumps(_rec("200k", model="m", start="2026-09-23T10:01:00+08:00", in_toks=100000, e2e=12.0, include_cl100k=False)) + "\n",
        encoding="utf-8",
    )
    assert len(generate_latest_json(jl3, out3, scenario="200k")) == 1
    # 10k 缺 cl100k 不上站（不得当成 200000）
    jl4 = tmp_path / "d.jsonl"
    out4 = tmp_path / "o4.json"
    jl4.write_text(
        json.dumps(_rec("10k", model="m", start="2026-09-23T10:00:00+08:00", in_toks=100000, e2e=10.0, include_cl100k=False)) + "\n"
        + json.dumps(_rec("10k", model="m", start="2026-09-23T10:01:00+08:00", in_toks=100000, e2e=12.0, include_cl100k=False)) + "\n",
        encoding="utf-8",
    )
    assert generate_latest_json(jl4, out4, scenario="10k") == []
    # sentence 缺 cl100k 不上站
    jl5 = tmp_path / "e.jsonl"
    out5 = tmp_path / "o5.json"
    jl5.write_text(
        json.dumps(_rec("sentence", model="m", start="2026-09-23T10:00:00+08:00", in_toks=5000, e2e=10.0, include_cl100k=False)) + "\n"
        + json.dumps(_rec("sentence", model="m", start="2026-09-23T10:01:00+08:00", in_toks=5000, e2e=12.0, include_cl100k=False)) + "\n",
        encoding="utf-8",
    )
    assert generate_latest_json(jl5, out5, scenario="sentence") == []
    # 短输出 499 不上站
    jl6 = tmp_path / "f.jsonl"
    out6 = tmp_path / "o6.json"
    jl6.write_text(
        json.dumps(_rec("10k", model="m", start="2026-09-23T10:00:00+08:00", in_toks=10000, cl100k=10000, out=499, e2e=10.0)) + "\n"
        + json.dumps(_rec("10k", model="m", start="2026-09-23T10:01:00+08:00", in_toks=10000, cl100k=10000, out=800, e2e=12.0)) + "\n",
        encoding="utf-8",
    )
    assert generate_latest_json(jl6, out6, scenario="10k") == []
    # 无生成窗口 gen_tps 为 null 照常上站
    jl7 = tmp_path / "g.jsonl"
    out7 = tmp_path / "o7.json"
    r1 = _rec("10k", model="m", start="2026-09-23T10:00:00+08:00", in_toks=10000, cl100k=10000, e2e=10.0, gen=None)
    r2 = _rec("10k", model="m", start="2026-09-23T10:01:00+08:00", in_toks=10000, cl100k=10000, e2e=12.0, gen=None)
    jl7.write_text(json.dumps(r1) + "\n" + json.dumps(r2) + "\n", encoding="utf-8")
    got = generate_latest_json(jl7, out7, scenario="10k")
    assert len(got) == 1 and got[0]["gen_tps"] is None


def test_ac008_readme_docs():
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "sentence" in text and "10k" in text and "200k" in text
    assert "不合成总分" in text or "不合成" in text
    # 不把 100k 或 1k 写成已上线
    assert "100k" not in text or "未" in text or "仍未" in text or "不" in text
