---
tid: "t005"
slug: "antigravity_harness"
title: "新增 antigravity (agy) harness 适配与 200K 评测支持"
status: "done"
branch: "t005_antigravity_harness"
worktree: ""
review_level: "single"
review_limit: "5"
verify_limit: "5"
diff_anchor: "912db344fc55e1906ab388010038466bd3a8dc99"
depends_on: ""
conflicts_with: ""
note: ""
---

# Task 过程总账

front matter 只经 `task.py` 修改；reviewer 只写对应 `review_*.md`。

## 实施笔记

执行期记录关键步骤、决策、验证、阻塞和用户批准的新轮次上限。

创建期不预测实施步骤。只记有追溯价值的内容；无事项时写“无”。

- 参考 `call_agents/scripts` 的参数传递规范，实现 `src/agent_speed/harness/antigravity.py`，支持调用 `agy` 传入 `-p <prompt>`、`--model`、`--effort` 与 `--output-format stream-json`。
- 在 `src/agent_speed/metrics.py` 新增 `parse_antigravity_metrics`，提取首个 `text_delta` 到达时刻为 TTFT，最后一个 `text_delta` 减 TTFT 作为解码窗口，从 `usage` 提取 input/output tokens。
- 在 `src/agent_speed/harness/__init__.py` 注册 `antigravity` 与 `agy` 别名。
- 在 `src/agent_speed/matrix.py` 补充 `gemini-3.8-flash-high` 和 `gemini-3.8-flash-low` 的 `google:antigravity` 评测格子。
- 落地单元测试 `tests/test_antigravity_harness.py`（4 passed），并完成真实 200K 冒烟调用（写入 `results.jsonl`，指标字段解析完整非空）。

## Review 处置

每个结构化 finding 一行。`已修` 表示本 task 已修复；`遗留` 必须指向 `pNNN` 或 follow-up tid；`撤回` 必须写清理由。critical/important 未解决时不得 PASS。

### Round 1 (2026-09-22 17:40 UTC+8)

Round 1 零 finding。

## 收尾报告

### 验收与验证

- spec：[`spec.md`](spec.md)
- 结果：全部满足
- 测试：pytest .repo_template/tests -q -m contract (132 passed)；pytest tests -v (20 passed)
- 黑盒：未定义（blueprint/testing.md 中 blackbox_verify 声明为“无”）
- review：Round 1 PASS（review_level=single, general_verdict=PASS, review_scope=ok）
- AC 证据：见 `handoff.json`

### 结果摘要

- 新增 `antigravity` (agy) 评测框架适配器与 stream-json 指标解析。
- 注册 `antigravity` / `agy` 并纳入 200K 矩阵与调度队列（`google:antigravity`）。
- 成功完成真实 200K 切片调用冒烟与单测验证。
