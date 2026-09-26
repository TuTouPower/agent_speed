---
tid: "t009"
slug: "pricing_update"
title: "单价数据更新脚本与定价产物"
status: "done"
branch: "t009_pricing_update"
worktree: ""
review_level: "single"
review_limit: "5"
verify_limit: "5"
diff_anchor: "a5f2475d005d1775b83f63cc62ce0df2636a7005"
depends_on: "t008"
conflicts_with: ""
note: "抓取 real-api-pricing 最新采用表，对齐模型表，写出单价与未对齐清单"
---

# Task 过程总账

front matter 只经 `task.py` 修改；reviewer 只写对应 `review_*.md`。

## 实施笔记

执行期记录关键步骤、决策、验证、阻塞和用户批准的新轮次上限。

创建期不预测实施步骤。只记有追溯价值的内容；无事项时写“无”。

- 实现 `scripts/update_pricing.py`：默认 raw GitHub 拉取；`--csv` / `AGENT_RANK_ADOPTED_CSV` 注入夹具。
- 覆盖：OpenCode Go deepseek- 额度 ×4；Command Code GOAT 月费 10.78。
- 实跑：latest 63 / unmatched 203；OpenCode deepseek-v4.1-flash real≈0.00161；GOAT MiniMax-M3 price=10.78。
- 黑盒：`testing.md` blackbox_verify 为「无」。
- attempt=1 execution_id=5570cdfe51d3415dbe9164b6e3dcbf07

## Review 处置

每个结构化 finding 一行。`已修` 表示本 task 已修复；`遗留` 必须指向 `pNNN` 或 follow-up tid；`撤回` 必须写清理由。critical/important 未解决时不得 PASS。

### Round 1 (2026-09-26 08:59 UTC+8)

Round 1 零 finding。

## 收尾报告

### 验收与验证

- spec：[`spec.md`](spec.md)
- 结果：全部满足
- 测试：`pytest tests -q` 68 passed；`pytest .repo_template/tests -q -m contract` 132 passed
- 黑盒：未定义（`docs/blueprint/testing.md` blackbox_verify 章节正文为「无」）
- review：Round 1 PASS（single / review_general.md，零 finding，scope c777de93cfbda1b2）
- AC 证据：见 `handoff.json`

### 结果摘要

- 新增单价更新脚本、指南、定价产物与夹具测试；测速流水线未改。遗留无。
