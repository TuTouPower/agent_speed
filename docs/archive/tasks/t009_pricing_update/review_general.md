# Task review t009（reviewer_focus: 通用）

- task：`t009_pricing_update`
- spec：`docs/tasks/t009_pricing_update/spec.md`
- diff_anchor：`a5f2475d005d1775b83f63cc62ce0df2636a7005`
- target：`git -C '/workspace/agent_rank_hist_t009' diff a5f2475d005d1775b83f63cc62ce0df2636a7005`
- round：1
- reviewed_at：2026-09-26 08:59 UTC+8

## Findings

Round 1 零 finding。

## 契约核验 (AC-001 ~ AC-007)

1. **AC-001（产物可解析且入库）**: PASS
    - `scripts/update_pricing.py` 写出 `data/pricing_latest.json`（63 行）与 `data/pricing_unmatched.json`（203 行）；`.gitignore` 增加两处 `!/data/...` 例外。
    - 夹具 CLI 测试 `test_cli_writes_outputs`；实网/缓存抓取已跑通。

2. **AC-002（字段与可排序）**: PASS
    - 行含 plan/model/source/billing/price_usd/monthly_tokens/monthly_yi/real_usd_per_mtok/unmetered/promo_until/confidence/citation/notes；`model` 均为模型表 id；按 `real_usd_per_mtok` 升序。
    - `test_pricing_row_fields_and_sortable`。

3. **AC-003（精确对齐）**: PASS
    - 仅 `id` 或 `pricing_aliases` 精确匹配；大小写不同（`Deepseek-v4.1-flash`）与未知模型进 unmatched。
    - `test_align_exact_id_and_alias`。

4. **AC-004（OpenCode DeepSeek 覆盖）**: PASS
    - 夹具与实跑：`deepseek-v4.1-flash` 月费 10 不变，tokens 1552800000→6211200000（×4），real≈0.00161 < 0.00644，notes 含覆盖说明；`source=opencode-go`。
    - `test_opencode_deepseek_override`。

5. **AC-005（Command Code GOAT 覆盖）**: PASS
    - 月费 10.78，额度不变，real 按 10.78 重算，notes 含覆盖说明。
    - `test_command_code_goat_override`；实跑 MiniMax-M3：price 10.78、tokens 655500000、real≈0.01645。

6. **AC-006（指南）**: PASS
    - `docs/guides/pricing_update.md` 含运行方式、覆盖、未对齐补录；`test_guide_and_agents_and_gitignore`。

7. **AC-007（AGENTS 与测速不变）**: PASS
    - AGENTS 声明脚本与两份产物；diff 未触及 `run_bench.py` / `report.py` / results / latest。

## 风险与范围外观察

- 未对齐 203 行属预期（上游远大于本仓模型表）；不强制全对齐。
- 套餐→source 对照保守扩展若干已有测速 source；未知为空字符串。
- CSV 用 utf-8-sig；`--csv` / `AGENT_RANK_ADOPTED_CSV` 支持测试注入。

## 结论

- 前轮 finding 复核：首轮，无前轮 finding。
- 本轮新发现：0 条。
- 未进表的提示：无。
- 总体判断：单脚本路径完整，覆盖数值可核对，同意 PASS。
- 系统性 follow-up：无。

### AC 复验方式

- AC-001：`re_verified`。`pytest tests/test_update_pricing.py::test_cli_writes_outputs -q`；实跑 `python3 scripts/update_pricing.py`。
- AC-002：`re_verified`。`pytest tests/test_update_pricing.py::test_pricing_row_fields_and_sortable -q`
- AC-003：`re_verified`。`pytest tests/test_update_pricing.py::test_align_exact_id_and_alias -q`
- AC-004：`re_verified`。`pytest tests/test_update_pricing.py::test_opencode_deepseek_override -q`
- AC-005：`re_verified`。`pytest tests/test_update_pricing.py::test_command_code_goat_override -q`
- AC-006 / AC-007：`re_verified`。`pytest tests/test_update_pricing.py::test_guide_and_agents_and_gitignore -q`；`git diff --name-only` 无测速流水线文件。

coverage = 7 / 7 = 100%

reviewed_scope: c777de93cfbda1b2

verdict: PASS
