# Task review t005（reviewer_focus: 通用）

- task：`t005_antigravity_harness`
- spec：`docs/tasks/t005_antigravity_harness/spec.md`
- diff_anchor：`912db344fc55e1906ab388010038466bd3a8dc99`
- target：`git -C '/Users/karson/kar/code/agent_rank_t005' diff 912db344fc55e1906ab388010038466bd3a8dc99`
- round：1
- reviewed_at：2026-09-22 17:40 UTC+8

## Findings 概览

无（Clean review，0 条 blocking finding）。

## 契约核验 (AC-001 ~ AC-005)

1. **AC-001（命令组装与直传切片）**: PASS

    - `src/agent_rank/harness/antigravity.py` 中 `build_antigravity_cmd` 组装 `[bin_name, "-p", full_prompt, "--output-format", "stream-json"]`，并通过 `full_prompt` 拼接任务提示词与代码切片文本。
    - 正确传递 `--model`（基于 `cell.resolved_cli_model`）与 `--effort`（基于 `cell.effort`）。
    - `scripts/run_bench.py` 已扩展分支，允许 `antigravity` 与 `agy` 通过 argv 直传切片文本与 prompt。
    - 单测 `test_antigravity_cmd_builder` 验证通过。

2. **AC-002（stream-json 指标解析与窗口计算）**: PASS

    - `src/agent_rank/metrics.py` 中实现 `parse_antigravity_metrics`，容错解析逐行 JSON 事件流。
    - TTFT 精确捕获首个 `step_update.text_delta` 到达时刻；持续追踪末次 `text_delta` 到达时刻 `last_delta_t`；生成窗口正确计算为 `round(last_delta_t - ttft, 3)`，标记来源为 `antigravity:last_delta_minus_ttft`。
    - 提取 `step_update.usage` 或 `result.usage` 中的 `input_tokens` 与 `output_tokens`；结合 `calculate_tps` 计算出端到端 TPS 与生成 TPS。
    - 单测 `test_parse_antigravity_metrics` 验证通过。

3. **AC-003（harness 注册与别名）**: PASS

    - `src/agent_rank/harness/__init__.py` 的 `get_harness` 工厂字典已同时注册 `"antigravity": AntigravityHarness` 与 `"agy": AntigravityHarness`。
    - 单测 `test_harness_registry_antigravity` 验证通过。

4. **AC-004（200K 评测矩阵条目与队列键）**: PASS

    - `src/agent_rank/matrix.py` 中 `BENCH_MATRIX_200K` 增加了 `gemini-3.8-flash-high` 与 `gemini-3.8-flash-low` 两个条目，配置 `source="google"`, `harness="antigravity"`。
    - `queue_key` 准确计算为 `google:antigravity`，场景为 `200k`。
    - 单测 `test_matrix_contains_antigravity` 验证通过。

5. **AC-005（真实 200K 冒烟与结果写入）**: PASS

    - `results.jsonl` 中已成功追加真实冒烟测试记录（`batch_id: 93f66eadd173`, `rep: 1`, `status: success`）。
    - 关键性能与账单指标全部非空：`wall: 23.56`, `ttft: 10.437`, `decode_window: 11.44`, `out_tokens: 3131`, `in_tokens: 61603`, `e2e_tps: 132.89`, `gen_tps: 273.69`, `decode_window_source: "antigravity:last_delta_minus_ttft"`。
    - 记录格式完全符合 §7.1 规范且不包含敏感信息或本机绝对路径。

## 结论

- 前轮 finding 复核：首轮审查，无前轮 finding。
- 本轮新发现：0 条（clean review，无 blocking finding）。
- 未进表的提示：无。
- 总体判断：各模块修改精准规范，单测覆盖完整，真实冒烟指标完整合规，同意 PASS。
- 系统性 follow-up：无。

### AC 复验方式

- AC-001：`re_verified`。执行 `pytest tests/test_antigravity_harness.py::test_antigravity_cmd_builder -q`，断言命令列表包含 `-p`、拼接切片内容、`--model`、`--effort` 及 `--output-format stream-json`。
- AC-002：`re_verified`。执行 `pytest tests/test_antigravity_harness.py::test_parse_antigravity_metrics -q`，传入含 init、step_update、result 的 mock 事件流，验证 TTFT、生成窗口（7.8 - 1.8 = 6.0s）、来源标识及 input/output token 提取准确无误。
- AC-003：`re_verified`。执行 `pytest tests/test_antigravity_harness.py::test_harness_registry_antigravity -q`，验证 `get_harness("antigravity")` 与 `get_harness("agy")` 均返回 `AntigravityHarness` 实例。
- AC-004：`re_verified`。执行 `pytest tests/test_antigravity_harness.py::test_matrix_contains_antigravity -q`，过滤 `BENCH_MATRIX_200K` 并断言包含 `source="google"`、`harness="antigravity"` 且 `queue_key == "google:antigravity"` 的评测单元。
- AC-005：`re_verified`。读取 `results.jsonl` 末行记录，解析 JSON 并断言 `harness == "antigravity"`，`status == "success"`，且 `wall`, `ttft`, `decode_window`, `out_tokens`, `in_tokens`, `e2e_tps`, `gen_tps` 均大于 0 且非空。

coverage = 5 / 5 = 100%

reviewed_scope: 091afc661d13657a

verdict: PASS
