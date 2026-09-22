---
tid: "t006"
slug: "queue_concurrency_config"
title: "调度器重构：双层并发（单队2/全局10）、单一配置benchmark.json与模型别名解耦"
status: "done"
branch: "t006_queue_concurrency_config"
worktree: ""
review_level: "full"
review_limit: "5"
verify_limit: "5"
diff_anchor: "b5df8cdd452136d298304d9f12b2296820fbd36c"
depends_on: ""
conflicts_with: ""
note: ""
---

# Task 过程总账

front matter 只经 `task.py` 修改；reviewer 只写对应 `review_*.md`。

## 实施笔记

执行期记录关键步骤、决策、验证、阻塞和用户批准的新轮次上限。

创建期不预测实施步骤。只记有追溯价值的内容；无事项时写“无”。

- 创建主配置文件 `config/benchmark.json`，集中管理全局/单队列并发上限、运行默认值与 12 个 200K 网格声明。
- 重构 `GridCell` 数据类，增加 `queue` 与 `cli_model` 字段，彻底去除裸写 `official` 歧义。
- 升级 `QueueScheduler`，采用“全局线程池（10）+ 队列级信号量（2）”的双层受控并发架构，无死锁、无排队饿死。
- 改造 `scripts/run_bench.py` 默认加载 `config/benchmark.json`，支持 CLI 参数覆盖。
- 编写双层并发压力测试 `test_scheduler_two_tier_concurrency_limits`，验证全局活跃任务 ≤ 10 且单队列峰值严格等于 2。
- 全量同步更新 `docs/plan.md`、`docs/specs/collector_scheduler.md`、`architecture.md` 及 `domain.md`。

## Review 处置

每个结构化 finding 一行。`已修` 表示本 task 已修复；`遗留` 必须指向 `pNNN` 或 follow-up tid；`撤回` 必须写清理由。critical/important 未解决时不得 PASS。

### Round 1 (2026-09-22 18:20 UTC+8)

Round 1 零 finding。

## 收尾报告

### 验收与验证

- spec：[`spec.md`](spec.md)
- 结果：全部满足
- 测试：pytest .repo_template/tests -q -m contract (132 passed)；pytest tests -v (22 passed)
- 黑盒：未定义（blueprint/testing.md 中 blackbox_verify 声明为“无”）
- review：Round 1 PASS（review_level=full, code_verdict=PASS, test_verdict=PASS, review_scope=ok）
- AC 证据：见 `handoff.json`

### 结果摘要

- 集中落地 `config/benchmark.json`，实现参数与矩阵的声明式单一配置管理。
- 调度器升级为双层受控并发模型（单队 2 并发、全局 10 并发）。
- 模型名与客户端别名解耦，渠道命名正名化，Gemini 跨 harness 共享队列与 DeepSeek 跨通道并发得到有效验证。
