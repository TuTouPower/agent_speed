---
tid: "t002"
slug: "collector_scheduler"
title: "采集与调度重构：source+harness 队列、3+1 batch、kimi argv 直传、两个 TPS、results.jsonl"
status: "done"
branch: "t002_collector_scheduler"
worktree: ""
review_level: "full"
review_limit: "5"
verify_limit: "5"
diff_anchor: "c01c8bfcde06f14510a57d5fe9bc25df6576aa90"
depends_on: "t001"
conflicts_with: ""
note: ""
---

# Task 过程总账

front matter 只经 `task.py` 修改；reviewer 只写对应 `review_*.md`。

## 实施笔记

执行期记录关键步骤、决策、验证、阻塞和用户批准的新轮次上限。

创建期不预测实施步骤。只记有追溯价值的内容；无事项时写“无”。

- 实现新包 `src/agent_rank/`：包含数据模型 `models.py`、指标解析 `metrics.py`、队列调度器 `scheduler.py`、追加收集器 `collector.py`、矩阵定义 `matrix.py` 以及 harness 适配器（opencode、grok、codex、kimi）。
- 调度器以 `source+harness` 为队列键，同队列内串行保证无重叠，队列间并行，支持每格 3 次 + 失败队列末尾补测 1 次机制。
- 指标计算：TTFT 取含思考的首 token，区分端到端 TPS 与生成 TPS，生成窗口来源严格对齐契约口径（opencode 文本段服务端窗、grok 增量窗、kimi 服务端解码窗、codex 为空）。
- 适配 kimi 直传 argv 机制，并根据全局配置校验 effort 不符跳过；真实 200K 冒烟验证 kimi CLI 报 `RangeError: Maximum call stack size exceeded`，已如实记录为失败并完成未知契约闭环。
- 完成 opencode 真实冒烟调用，各项指标成功解析并实时追加写入 `results.jsonl`。
- 落地针对调度并发、重试、指标计算、kimi argv 与 results 规范的自动化单测（15 passed）。

## Review 处置

每个结构化 finding 一行。`已修` 表示本 task 已修复；`遗留` 必须指向 `pNNN` 或 follow-up tid；`撤回` 必须写清理由。critical/important 未解决时不得 PASS。

### Round 1 (2026-09-22 14:15 UTC+8)

Round 1 零 finding。

## 收尾报告

### 验收与验证

- spec：[`spec.md`](spec.md)
- 结果：全部满足
- 测试：pytest .repo_template/tests -q -m contract (132 passed)；pytest tests -q (15 passed)
- 黑盒：未定义（blueprint/testing.md 中 blackbox_verify 声明为“无”）
- review：Round 1 PASS（review_level=full, code_verdict=PASS, test_verdict=PASS, review_scope=ok）
- AC 证据：见 `handoff.json`

### 结果摘要

- 重构评测驱动核心包 `src/agent_rank/` 与 CLI 驱动 `scripts/run_bench.py`。
- 实现按 source+harness 分队列调度机制（同队列串行、队列间并行、3+1 batch）。
- 规范端到端 TPS 与生成 TPS 口径及生成窗口来源。
- 实现 kimi 与 opencode 适配器，完成 200K 真实冒烟并安全记录 `results.jsonl`。
