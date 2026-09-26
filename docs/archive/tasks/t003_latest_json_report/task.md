---
tid: "t003"
slug: "latest_json_report"
title: "latest.json 报告：最新 batch、上站规则、中位数"
status: "done"
branch: "t003_latest_json_report"
worktree: ""
review_level: "single"
review_limit: "5"
verify_limit: "5"
diff_anchor: "122f59268ad6e13cbe90fb1ea52858039b14a66e"
depends_on: "t002"
conflicts_with: ""
note: ""
---

# Task 过程总账

front matter 只经 `task.py` 修改；reviewer 只写对应 `review_*.md`。

## 实施笔记

执行期记录关键步骤、决策、验证、阻塞和用户批准的新轮次上限。

创建期不预测实施步骤。只记有追溯价值的内容；无事项时写“无”。

- 实现报告生成核心模块 `src/agent_rank/report.py` 与入口脚本 `report.py`。
- 实现最新 batch 锁定与历史 batch 隔离机制（更早 batch 不补位）。
- 落地完整上站门槛过滤：有效调用筛选（排除失败与 out_tokens < 500）、有效次数 >= 2 门槛、对方账单输入 token >= cl100k / 2 门槛。
- codex 无生成窗口格子正常上站且 `gen_tps` 输出为 null。
- 所有中位数聚合指标严格仅由有效调用计算。
- 覆盖写入 `latest.json` 并按端到端 TPS 降序排列。
- 编写包含多种格子边界用例的单测 `tests/test_report.py`，全量测试 16 passed。

## Review 处置

每个结构化 finding 一行。`已修` 表示本 task 已修复；`遗留` 必须指向 `pNNN` 或 follow-up tid；`撤回` 必须写清理由。critical/important 未解决时不得 PASS。

### Round 1 (2026-09-22 14:25 UTC+8)

Round 1 零 finding。

## 收尾报告

### 验收与验证

- spec：[`spec.md`](spec.md)
- 结果：全部满足
- 测试：pytest .repo_template/tests -q -m contract (132 passed)；pytest tests -q (16 passed)
- 黑盒：未定义（blueprint/testing.md 中 blackbox_verify 声明为“无”）
- review：Round 1 PASS（review_level=single, general_verdict=PASS, review_scope=ok）
- AC 证据：见 `handoff.json`

### 结果摘要

- 实现 `src/agent_rank/report.py` 与 `report.py`。
- 完整实现最新 batch 隔离、有效样本过滤、输入 token 半数门槛、codex 生成 TPS 空值兼容与中位数计算。
- 按端到端 TPS 降序覆盖输出 `latest.json`。
