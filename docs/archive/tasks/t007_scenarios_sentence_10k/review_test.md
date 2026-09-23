# Task review t007（reviewer_focus: 测试）

- task：`t007_scenarios_sentence_10k`
- spec：`docs/tasks/t007_scenarios_sentence_10k/spec.md`
- diff_anchor：`b78cdd1ef4424a2778821e0775444328bb0dea41`
- target：`git -C '/Users/karson/kar/code/agent_speed_t007' diff b78cdd1ef4424a2778821e0775444328bb0dea41`
- round：1
- reviewed_at：2026-09-23 09:33 UTC+8

## Findings

无。本轮零 finding（clean review，不凑数）。

## 结论

- 落点仓库校验：`git rev-parse --show-toplevel` 为 `/Users/karson/kar/code/agent_speed_t007`。
- 测试范围：新 `tests/test_scenarios_sentence_10k.py`（10 用例）+ 存量 `tests/test_report.py`、`tests/test_scheduler.py` 等未被弱化（diff 显示旧测试零改动）。
- 可测性核对：spec 声明全部 AC 可自动测试；上下文区有意不测（实网、字数判定、100k/1k、站点、预览图、Kimi 200K 截断）均未要求新增测试，符合。
- 反假绿检查：
    - 未 mock 被测逻辑：新测试直接调用 `resolve_scenario_inputs`、`build_user_message`、`apply_scenario_to_cell`、`build_kimi_cmd`、`build_antigravity_cmd`、`generate_latest_json` 等生产函数；harness 守卫用 `inspect.getsource` 辅查但核心行为由输入输出断言覆盖。
    - 未弱化断言：sentence 原句逐字相等、tiktoken 61、10k 字节前缀、`cl100k_tokens` 精确值、 billing 边界（5000 上站/4999 不上、499 不上、缺字段分档处理）、排序 `fast` 在 `slow` 前、空档 `[]`、results.jsonl 内容不变，均为强断言。
    - 未只改预期：旧 `test_report.py` 预期原样保留且仍通过（默认 `scenario="200k"` 下全 200k 数据行为不变）。
    - 无 `.skip`/恒真/注释断言/`type: ignore`。
- 覆盖映射：AC-001→test_ac001；AC-002→test_ac002；AC-003→test_ac003；AC-004→test_ac004；AC-005→test_ac005 双用例；AC-006→双用例（含排序与空档）；AC-007→边界全覆盖；AC-008→README 断言。每条 AC 至少一独立用例。
- 七视角（测试轴）：真实性、断言强度、覆盖完整、边界（等于一半/低于一半/缺字段/499/4999/5000）、隔离性（tmp_path，不碰 `data/results.jsonl`）、可重复性（`uv run pytest` 稳定 32 passed）、文档一致（测试名与 AC 对应）均已扫过。
- 未进表的提示：无。测试文件 266 行，未达 600/1200 阈值；`test_ac005_sentence_no_fixture_marker_all_harness` 内 `or` 写法略绕但语义正确（首分支即精确相等），不构成弱化，仅作可读性提示，不进表。
- 系统性 follow-up：无。

### AC 复验方式

- re_verified 全部 AC：独立重跑 `uv run pytest tests/test_scenarios_sentence_10k.py -q`（9/10 通过后补 README 得 10/10，现全量 `uv run pytest tests -q` 为 32 passed）与 `uv run pytest .repo_template/tests -q -m contract`（132 passed）；抽查 `test_ac006` 的 `results.jsonl` 不变断言与 `test_ac007` 的等于/低于一半边界。
- trust_prior：无。未依赖部署或人工证据。

coverage = 8 / 8

verdict: PASS

reviewed_scope: 07b020202c22033b

## Round 2 (2026-09-23 09:55 UTC+8)

- 被审对象：worktree `/Users/karson/kar/code/agent_speed_t007` 在执行 commit `f4a695e` 的完整交付；本轮以相对 `b78cdd1ef4424a2778821e0775444328bb0dea41` 的全量 diff 为准直接读文件；worktree 干净；本轮采用门禁已验证值见结尾两行。

### 前轮复核

- 首轮为零发现 clean review，本轮逐项以 diff 与代码为准复核，结论为全部维持成立，无复活项，无修不彻底，无换形式弱化。
- 首轮记载的新测试 10 用例与旧测试零改动依然成立：`--name-only -- tests/` 仅列出 `tests/test_scenarios_sentence_10k.py` 一个新增文件；存量测试文件无新增、无修改、无删除。
- 首轮记载的覆盖映射依然成立：AC-001→`test_ac001_sentence_inputs`、AC-002→`test_ac002_10k_inputs`、AC-003→`test_ac003_default_200k`、AC-004→`test_ac004_single_scenario_per_run`、AC-005→`test_ac005_no_truncation_for_short` 与 `test_ac005_sentence_no_fixture_marker_all_harness`、AC-006→`test_ac006_three_boards_split` 与 `test_ac006_sort_desc_within_board`、AC-007→`test_ac007_billing_thresholds`、AC-008→`test_ac008_readme_docs`。
- 首轮记载的独立重跑结论本轮复现：worktree 内只读执行 `uv run pytest tests/test_scenarios_sentence_10k.py -q` 为 10 passed，`uv run pytest tests -q` 为 32 passed。

### 改测方向复核

- 无。diff 中不存在修改既有测试之处（旧测试零改动）；新增文件不存在“把旧预期改成新实现输出”的情形；`tests/test_report.py` 等存量预期原样保留且全量 32 passed 仍通过。

### 本轮新发现

- 无。本轮零 finding（clean review，不凑数）。
- 反假绿重点复查（以代码与重跑为准，非采信实施自述）：
  - mock 被测逻辑：无。10 用例直接调用生产函数 `resolve_scenario_inputs`、`build_user_message`、`apply_scenario_to_cell`、`build_kimi_cmd`、`build_antigravity_cmd`、`generate_latest_json`；`tmp_path` 隔离聚合测试，不碰 `data/results.jsonl`；关键字扫描 `mock/Mock/skip/only/assert True/type ignore/eslint-disable/ts-ignore/.value =` 无命中。
  - 弱化断言：无阻断级弱化。两处 `or` 写法已逐一调查：`tests/test_scenarios_sentence_10k.py:39` 的 `or True` 使该单行恒真，但同函数第 37 行已有 `assert msg == SENTENCE` 精确相等强断言覆盖 AC-001 无 fixture 要求，该行不掩盖任何失败；`tests/test_scenarios_sentence_10k.py:134` 为“精确命令形状或 AC 最低要求（无 CODE FIXTURE 标记）”，第二分支即 AC-005 本体，未把断言弱化到 AC 之下。其余均为强断言：逐字原句、tiktoken 61、10k 字节前缀相等、`cl100k_tokens` 精确值、账单边界（5000 上站/4999 不上/499 不上/缺字段分档）、`fast` 排 `slow` 前、空档 `[]`、`results.jsonl` 内容不变。
  - 只改预期：无。无既有测试被就地改预期；`inspect.getsource` 两处（`tests/test_scenarios_sentence_10k.py:116-122`）仅为截断分支 scoping 辅查，核心行为另有字节数与 `cl != 173218` 断言覆盖，且 spec 有意不测“200K 上 Kimi 超长截断”本体，只锁定 10k/sentence 不进入该分支，符合测试策略，不构成“平行实现冒充覆盖”。
  - 其余危险模式：无 `.skip`/`.only`、无删测试、无删/反转/注释断言、无静默错误、无阈值掩盖、无条件跳过弱化断言、无程序赋值替代真实交互（本 task 无 UI 交互要求）。

### 未进表的提示

- 无阻断提示之外的两条可读性提示（延续首轮，不进表）：`tests/test_scenarios_sentence_10k.py:39` 的 `or True` 为冗余恒真行，建议后续顺手删掉该行尾分支；`tests/test_scenarios_sentence_10k.py:134` 的 `or` 可拆成精确形状断言与无标记断言两行。可读性问题，不影响本轮判断。
- 新测试文件 266 行，无规模阈值问题；上下文区有意不测项（实网、800 到 1200 字判定、100k/1k、站点、预览图、Kimi 200K 截断本体）均未要求新增测试，未据此出 finding。

### AC 复验方式

- AC-001 re_verified：抽查 `test_ac001_sentence_inputs` 逐字相等与 tiktoken 61 断言，重跑 10 passed 含该用例。
- AC-002 re_verified：抽查 `test_ac002_10k_inputs` 的 fixture 字节相等与前缀断言。
- AC-003 re_verified：抽查 `test_ac003_default_200k` 的 200k 切片相等与 `cl100k == 200000` 断言。
- AC-004 re_verified：抽查 `test_ac004_single_scenario_per_run` 单 scenario 集合与格子集合不变断言。
- AC-005 re_verified：抽查 `test_ac005_*` 双用例的字节上限、`cl != 173218` 与无标记断言。
- AC-006 re_verified：抽查 `test_ac006_*` 双用例的分榜 scenario 集合、排序、空档 `[]` 与输入文件内容不变断言。
- AC-007 re_verified：抽查 `test_ac007_billing_thresholds` 的等于一半/低于一半/缺字段分档/499 不上/`gen_tps is None` 照常上站断言。
- AC-008 re_verified：抽查 `test_ac008_readme_docs` 的三档齐备、不合成总分、100k/1k 非已上线断言。
- trust_prior：无。全部 AC 可自动测试，无需依赖部署或人工证据。

coverage = 8 / 8

### 总体判断

- 本轮无新增阻断项，前轮零发现经复核维持成立，测试可信与 AC 覆盖均满足契约区要求。

### 系统性 follow-up

- 无。

verdict: PASS
reviewed_scope: 8e0bddeb1df704aa
