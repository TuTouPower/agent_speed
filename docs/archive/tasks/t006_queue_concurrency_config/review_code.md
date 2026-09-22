# Code Review: t006 调度器双层并发与集中配置重构

reviewed_scope: a216ee1c28e7cf80

## 审查范围

- 比较基线：`b5df8cdd452136d298304d9f12b2296820fbd36c`
- 审查文件：
  - `config/benchmark.json`
  - `src/agent_speed/config.py`
  - `src/agent_speed/models.py`
  - `src/agent_speed/scheduler.py`
  - `scripts/run_bench.py`
  - `tests/test_scheduler.py`
  - `docs/specs/collector_scheduler.md`
  - `docs/plan.md`
  - `docs/blueprint/architecture.md`
  - `docs/blueprint/domain.md`
  - `docs/tasks/t006_queue_concurrency_config/task.md`

## 契约核验 (AC-001 ~ AC-006)

1. **AC-001（`config/benchmark.json` 主配置合法性与字段完整性）**: PASS
   - 新增 `config/benchmark.json`，包含 `concurrency`（`global_max: 10`, `per_queue: 2`）、`defaults`（场景、重复次数、重试次数、超时、素材路径及结果文件）以及 12 个完整评测网格。
   - 新增 `src/agent_speed/config.py`，实现 `load_benchmark_config` 安全解析配置并挂载至 `BenchmarkConfig` 对象。
   - 单测 `tests/test_scheduler.py:test_load_benchmark_config_file` 验证配置读取完整无误。

2. **AC-002（`GridCell` 显式 `queue`、`model`/`cli_model` 解耦、`source` 规范化）**: PASS
   - `GridCell` 增加 `queue` 与 `cli_model` 字段；`resolved_cli_model` 属性实现优雅降级（优先 `cli_model`，缺省回退 `model`）。
   - `queue_key` 优先采用显式 `queue` 标识，未指定时降级为 `{source}:{harness}`。
   - `source` 规范化为明确渠道名（如 `deepseek-official`、`mimo-official`、`google-antigravity` 等），无裸写 `official`。
   - `from_dict` 方法支持字典结构与默认 scenario 装载。

3. **AC-003（双层受控并发架构与无死锁保证）**: PASS
   - 全局并发：外层 `ThreadPoolExecutor(max_workers=global_max_workers)` 严格控制全局正在调度的并发线程数 ≤ 10。
   - 队列并发：各队列独立实例化 `threading.Semaphore(per_queue_concurrency)`，受控执行 ≤ 2。
   - 协调模型：各队列通过独立的轻量级管理线程提交与等待 batch，避免占用全局 worker 线程槽；调用执行在 `with sem:` 内同步执行 runner 并释放信号量，不存在锁反向依赖或嵌套死锁。
   - 结果收集：`records_lock` 与 `logs_lock` 确保线程安全落盘追加。
   - 单测 `tests/test_scheduler.py:test_scheduler_two_tier_concurrency_limits` 构造 6 队 18 个网格高并发压力测试，断言瞬时全局峰值 ≤ 10 且 > 2，各队列峰值 ≤ 2 且达到 2。

4. **AC-004（Gemini CPA 与 Antigravity 共享队列，DeepSeek 官方与网关隔离）**: PASS
   - `config/benchmark.json` 中 `cpa/gemini-3.8-flash` 与两档 antigravity（`gemini-3.8-flash-high`、`gemini-3.8-flash-low`）均显式指定 `queue: "google-gemini"`，受队列级 2 并发保护。
   - DeepSeek 官方分配为 `queue: "deepseek-official"`，opencode-go 网关分配为 `queue: "opencode-go"`，队列键不同，支持完全并行执行。
   - 单测 `tests/test_scheduler.py:test_gemini_shared_queue_and_deepseek_parallelism` 校验通过。

5. **AC-005（`scripts/run_bench.py` 默认加载集中配置与日志包含 `queue`）**: PASS
   - `scripts/run_bench.py` 默认读取 `config/benchmark.json`，提供 `--config` 命令行参数覆盖。
   - 支持从配置继承 defaults，同时保留 `--prompt`、`--fixture`、`--reps` 等 CLI 覆盖优先级。
   - 调度日志格式显式打印 `queue={q_key}` 字段（`start queue=...` / `done queue=...`）。

6. **AC-006（`docs/plan.md`、`docs/specs/collector_scheduler.md` 及蓝图同步更新）**: PASS
   - `docs/specs/collector_scheduler.md` 更新调度与并发模型章节，增加物理队列、双层受控并发规则与模型别名定义。
   - `docs/plan.md` 更新调度章节说明单队 2 并发、全局 10 并发与配额池隔离规则。
   - `docs/blueprint/architecture.md` 与 `docs/blueprint/domain.md` 同步架构与领域模型定义。

## 架构与工程规范审查

- **并发协调与死锁防护**：各物理队列管理循环通过主执行器外独立的 Python 线程调度，任务通过 `pool.submit` 提交至全局线程池，在池内工作线程获取队列 Semaphore。此拓扑保证了只要 runner 能正常返回，Semaphore 必按序释放，不会造成全局线程槽耗尽导致的自锁现象。
- **向后兼容性**：`GridCell` 的 `queue_key` 与 `resolved_cli_model` 保持优雅降级，存量单测与测试桩不受破坏。
- **非阻断观察项（Non-blocking）**：
  - `src/agent_speed/matrix.py` 中留存的 `BENCH_MATRIX_200K` 仍包含历史测试用的 `source="official"` 条目，仅在 `tests/test_antigravity_harness.py` 冒烟测试中引用；建议后续 task 将其统一迁至 `config/benchmark.json` 或更新常量定义。

## AC 复验方式

在工作仓库 `/Users/karson/kar/code/agent_speed_t006` 下执行以下命令复验：

1. **单元测试与双层并发断言（覆盖 AC-001 ~ AC-004）**：
   ```bash
   pytest tests/test_scheduler.py -v
   ```
   预期输出：
   - `test_load_benchmark_config_file PASSED`
   - `test_scheduler_two_tier_concurrency_limits PASSED`
   - `test_gemini_shared_queue_and_deepseek_parallelism PASSED`
   - `test_scheduler_batch_id_and_retry PASSED`

2. **全量测试套件回归**：
   ```bash
   pytest tests/ -q
   ```
   预期输出：`22 passed`。

3. **驱动入口默认配置与参数解析冒烟（AC-005）**：
   ```bash
   python scripts/run_bench.py --help
   ```
   预期输出：包含 `--config` 参数选项及配置说明。

4. **文档与蓝图一致性核验（AC-006）**：
   ```bash
   git diff b5df8cdd452136d298304d9f12b2296820fbd36c -- docs/
   ```
   预期输出：包含 `docs/plan.md`、`docs/specs/collector_scheduler.md`、`docs/blueprint/architecture.md` 及 `docs/blueprint/domain.md` 的双层并发与队列说明更新。

verdict: PASS
