# Task review t008（reviewer_focus: 通用）

- task：`t008_model_registry`
- spec：`docs/tasks/t008_model_registry/spec.md`
- diff_anchor：`6944aea3cb5767e5984935859a748d7cbda39273`
- target：`git -C '/workspace/agent_speed_hist_t008' diff 6944aea3cb5767e5984935859a748d7cbda39273`
- round：1
- reviewed_at：2026-09-26 08:56 UTC+8

## Findings

Round 1 零 finding。

## 契约核验 (AC-001 ~ AC-005)

1. **AC-001（models.json 可解析形状）**: PASS
    - `data/models.json` 为对象数组；每行含非空 `id`；仅 `MiniMax-M3` 带 `pricing_aliases: ["minimax-m3"]`（与定价仓 `served_model` 大小写不同），其余行省略别名。
    - 单测 `test_ac001_models_json_shape` 覆盖。

2. **AC-002（id 唯一）**: PASS
    - 17 个 id 互不相同；`test_ac002_model_ids_unique` 断言。

3. **AC-003（benchmark ∩ results 覆盖）**: PASS
    - 表含 benchmark `cells[].model` 与 `results.jsonl` 全部 `model` 并集（含仅历史出现的 `gemini-3.8-flash-low` / `gpt-5.6-luna` / `kimi-code/k3`）。
    - `test_ac003_covers_benchmark_and_results` 字面匹配，无大小写折叠。

4. **AC-004（gitignore 跟踪）**: PASS
    - `.gitignore` 增加 `!/data/models.json`；`test_ac004_gitignore_tracks_models_json` 用 `git check-ignore -v` 验证例外命中。

5. **AC-005（AGENTS.md 声明）**: PASS
    - 目录表新增 `data/models.json` 行；artifacts 句已含 `models.json` 跟踪列表；`test_ac005_agents_md_declares_models_json` 断言。

## 风险与范围外观察

- 未猜测未知别名（如 `grok-4.7-fast`、`k3-256k`）；留给 t009 未对齐清单驱动补录，符合契约「不猜测」。
- blueprint `architecture.md` / `domain.md` 已补模型表与别名术语，幅度最小。
- 未改测速流水线 / results / latest。

## 结论

- 前轮 finding 复核：首轮，无前轮 finding。
- 本轮新发现：0 条。
- 未进表的提示：无。
- 总体判断：交付对准 AC，测试触达真实文件与覆盖规则，同意 PASS。
- 系统性 follow-up：无。

### AC 复验方式

- AC-001：`re_verified`。`pytest tests/test_model_registry.py::test_ac001_models_json_shape -q`
- AC-002：`re_verified`。`pytest tests/test_model_registry.py::test_ac002_model_ids_unique -q`
- AC-003：`re_verified`。`pytest tests/test_model_registry.py::test_ac003_covers_benchmark_and_results -q`
- AC-004：`re_verified`。`pytest tests/test_model_registry.py::test_ac004_gitignore_tracks_models_json -q`
- AC-005：`re_verified`。`pytest tests/test_model_registry.py::test_ac005_agents_md_declares_models_json -q`

coverage = 5 / 5 = 100%

reviewed_scope: de99157a4992d7e3

verdict: PASS
