# Task spec

## 背景

当前测速矩阵写死在 Python 源码中，且调度规则仅支持“单队列绝对串行、队列间无上限并行”；同时 `source` 字段存在裸写 `official` 的语意歧义，缺乏真实模型名（`model`）与命令行入参别名（`cli_model`）的解耦。本 task 引入单一主配置文件 `config/benchmark.json`，重构调度器为“单队列最多 2 并发、全局最多 10 并发”的双层受控并发模型，并全面规范渠道与物理队列映射。

## 契约区

### 范围

- 新建集中式主配置文件 `config/benchmark.json`（定义全局/单队列并发上限、运行默认值、全量网格清单）。
- `src/agent_speed/models.py`：`GridCell` 增加 `queue` 与 `cli_model` 字段；规范 `source` 命名（如 `deepseek-official`、`mimo-official`、`google-antigravity`，彻底去除裸写 `official`）。
- `src/agent_speed/scheduler.py`：重构为双层受控并发（全局 `ThreadPoolExecutor` 控全局 10 并发，每个 `queue` 配备独立的 `Semaphore` 控单队 2 并发）；保持同一网格 3+1 批次与队列末尾补测机制。
- `scripts/run_bench.py`：默认从 `config/benchmark.json` 加载配置与网格，支持 `--config` 覆盖。
- `tests/test_scheduler.py`：编写双层并发压力测试，断言全局最大并发 ≤ 10、单队列最大并发 ≤ 2。
- 同步修订 `docs/specs/collector_scheduler.md`、`docs/plan.md`、`docs/blueprint/architecture.md` 与 `docs/blueprint/domain.md`。

### 非范围

- 不修改切片语料生成逻辑（t001 已完成）。
- 不修改上站中位数聚合与报告输出算法（t003 已完成）。

### 验收标准

<!-- 规范（门禁必留，不得删除） -->

只写可观察、可独立验证的行为；每条使用稳定且不复用的 `AC-NNN`。需真实部署或人工环境验证时在编号前加 `[deploy]`。技术选型不作为行为 AC。

<!-- /规范 -->

- [ ] AC-001：`config/benchmark.json` 作为集中主配置存在且合法，包含 `concurrency`（全局上限 10、单队列上限 2）、`defaults` 及完整网格配置。
- [ ] AC-002：`GridCell` 具备显式 `queue` 标识；支持标准名 `model` 与 CLI 入参别名 `cli_model` 解耦；`source` 均为明确渠道标识（无裸写 `official`）。
- [ ] AC-003：调度器实现双层受控并发：任意时刻全局运行调用数 ≤ 10，同一队列内运行调用数 ≤ 2（单测 fake runner 断言并发峰值）。
- [ ] AC-004：Gemini CPA 来源与 Antigravity 来源共享 `google-gemini` 队列（队列内受 2 并发限制）；DeepSeek 官方与 opencode-go 网关分属独立队列，可跨队列并行。
- [ ] AC-005：`scripts/run_bench.py` 默认加载 `config/benchmark.json` 执行，支持 `--config` 参数，调度日志输出包含 `queue` 标识。
- [ ] AC-006：`docs/plan.md`、`docs/specs/collector_scheduler.md` 及蓝图文档同步更新为双层并发（单队 2 / 全局 10）与独立 `queue` 调度契约。

### 可测试性声明

<!-- 规范（门禁必留，不得删除） -->

逐条说明不可自动测试的 AC 及替代验证；全部可测则写“全部 AC 可自动测试”。

<!-- /规范 -->

- 全部 AC 可自动测试（通过配置解析单测、fake runner 双层并发峰值断言、文档格式与契约校验）。

## 上下文区

- 来源：用户显式指定调度器双层并发、模型别名解耦与集中配置需求（2026-09-22）。

### 有意不测

- 外部真实网络在 10 并发下的极限压力：单元测试使用 fake runner 模拟耗时与并发峰值验证调度算法。

### 测试策略

- pytest：通过高并发注入构造用例，打点采集瞬时并发峰值，验证全局上限与单队列上限。
- 配置校验测试：验证 `config/benchmark.json` 必填项、队列名与渠道名。

### 未知契约清单

<!-- 规范（门禁必留，不得删除） -->

未核实的外部契约标为 `UNVERIFIED-BLOCKING` 或 `UNVERIFIED-SPIKE`；核实后改写为结论和验证方式。无则写“无”。

<!-- /规范 -->

- 无。

### 风险与回退

- 风险：并发信号量争抢导致死锁。
- 回退：严格遵循先获取全局线程、再以 context manager 获取队列信号量、finally 释放模式，避免死锁。

### 依赖与约束

- 依赖 t002/t005 的调度器与 harness 基础。

### Finalization 时更新的 blueprint

- `docs/blueprint/architecture.md`：更新配置文件与双层并发模型说明。
- `docs/blueprint/domain.md`：更新调度队列与模型别名定义。
- `docs/specs/collector_scheduler.md`：更新调度与并发章节。
- `docs/plan.md`：更新调度并发章节。
