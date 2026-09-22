# Test Review: t006 调度器双层并发与集中配置重构

reviewed_scope: a216ee1c28e7cf80

## 审查范围与基线

- 审查基线：`b5df8cdd452136d298304d9f12b2296820fbd36c`
- 工作仓库：`/Users/karson/kar/code/agent_speed_t006`
- 涉及改动：
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

## 门禁命令与测试套件可跑性

执行门禁测试命令：
1. 模板契约测试：`pytest .repo_template/tests -q -m contract`
   - 结果：132 passed, 352 deselected（耗时 1.19s）
2. 项目单元测试：`pytest tests -q`
   - 结果：22 passed（耗时 0.49s）

两套测试套件 100% 绿色通过，无失败、无跳过、无警告中断。

## AC 自动化可测性验证 (AC-001 ~ AC-006)

| 验收项 | 契约要求 | 自动化测试/验证方式 | 审查结论 |
|---|---|---|---|
| AC-001 | `config/benchmark.json` 作为集中主配置合法存在，含并发、defaults 与网格 | `tests/test_scheduler.py:test_load_benchmark_config_file`，断言 `global_max_concurrency==10`、`per_queue_concurrency==2`、`len(cells)>=10` | PASS |
| AC-002 | `GridCell` 显式 `queue`、`model`/`cli_model` 解耦、`source` 规范化无裸写 `official` | `tests/test_scheduler.py:test_load_benchmark_config_file` 遍历网格断言 `source != 'official'`、`queue is not None`、`resolved_cli_model is not None` | PASS |
| AC-003 | 双层受控并发：全局 ≤ 10，单队列 ≤ 2（单测 fake runner 断言并发峰值） | `tests/test_scheduler.py:test_scheduler_two_tier_concurrency_limits`，6 队列压力测试断言全局峰值 ≤ 10 且 > 2，单队列峰值 ≤ 2 且 == 2 | PASS |
| AC-004 | Gemini CPA 与 Antigravity 共享 `google-gemini` 队列；DeepSeek 官方与网关独立队列 | `tests/test_scheduler.py:test_gemini_shared_queue_and_deepseek_parallelism` 断言 Gemini 格子 `queue_key == 'google-gemini'` 且 DeepSeek 官方与网关不同队 | PASS |
| AC-005 | `scripts/run_bench.py` 默认加载 `benchmark.json`，支持 `--config`，日志含 `queue` | CLI 参数解析测试 `python scripts/run_bench.py --help`，调度器日志输出断言 `queue={q_key}` | PASS |
| AC-006 | `docs/plan.md`、`docs/specs/collector_scheduler.md` 与蓝图文档同步更新 | `git diff` 核验 4 份文档的并发调度与队列契约修改 | PASS |

## 并发峰值打点测试断言真实性审查

对 `tests/test_scheduler.py:test_scheduler_two_tier_concurrency_limits` 展开深度审查：

1. **瞬时并发采集机制**：
   `ConcurrencyTrackerHarness` 在 `run_cell` 的入口与出口分别通过 `threading.Lock` 保护原子计数器，精确更新全局与各队列的瞬时活跃数及历史峰值（`max_global_active`、`max_queue_active`）。
2. **压力负荷设计**：
   构造 6 个独立队列，每队列 3 个单元，每单元 2 轮调用（总调用数 36，瞬间并发请求上限 12），高于全局并发上限 10。
3. **断言真实有效性**：
   - `tracker.max_global_active <= 10`：断言全局并发不超过上限；实测峰值达到 10，验证全局容量被充分利用且受控截断。
   - `tracker.max_global_active > 2`：断言跨队列并行生效，排除调度器退化为全局单队串行。
   - `tracker.max_queue_active[q_name] <= 2`：断言单队列并发未超限。
   - `tracker.max_queue_active[q_name] == 2`：强断言！确保单队列内确实达到了 2 并发；若调度器退化为单队串行，峰值为 1，测试必失败红灯。
4. **批次与重试机制完整性**：
   `test_scheduler_batch_id_and_retry` 保持验证同一格子 3+1 批次相同，且失败重试第 4 次严格在队尾执行。

## 危险模式扫描

- **恒真断言（Tautological Assertions）**：扫描 `tests/test_scheduler.py` 中 17 处断言，全部绑定动态执行状态与配置真值，无 `assert True`、无无意义断言。
- **删断言（Deleted Assertions）**：旧测试 `test_scheduler_queue_parallelism_and_serialization` 原断言“同队绝对串行”，因业务契约升级为“单队 2 并发”而语义失效。实现侧按 TDD 规则整体重写为双层受控并发测试，保留并强化了批次测试，无弱化或静默抹除有效断言。
- **Mock 生产逻辑（Mocking Production Logic）**：生产调度类 `QueueScheduler`、配置类 `BenchmarkConfig` 及数据模型 `GridCell` 均为全真生产代码执行。测试仅向调度器注入 fake runner 作为依赖回调（用于模拟调用延迟与结果采集），未使用 `unittest.mock.patch` 篡改任何生产模块的内部逻辑或线程控制。

## AC 复验方式

在工作仓库 `/Users/karson/kar/code/agent_speed_t006` 下执行以下命令复验：

1. **复验门禁测试套件（132 契约 + 22 单测）**：
   ```bash
   pytest .repo_template/tests -q -m contract
   pytest tests -q
   ```
   预期输出：
   - 契约测试：`132 passed, 352 deselected`
   - 单测套件：`22 passed`

2. **复验调度器双层并发与配置加载测试**：
   ```bash
   pytest tests/test_scheduler.py -v
   ```
   预期输出：
   - `test_load_benchmark_config_file PASSED`
   - `test_scheduler_two_tier_concurrency_limits PASSED`
   - `test_gemini_shared_queue_and_deepseek_parallelism PASSED`
   - `test_scheduler_batch_id_and_retry PASSED`

3. **复验 CLI 默认配置与参数解析**：
   ```bash
   python scripts/run_bench.py --help
   ```
   预期输出：显示包含 `--config`、`--prompt`、`--fixture`、`--models` 等参数，并标明按 queue 双层并发调度。

4. **复验文档与蓝图同步契约**：
   ```bash
   git diff b5df8cdd452136d298304d9f12b2296820fbd36c -- docs/
   ```
   预期输出：包含 `docs/plan.md`、`docs/specs/collector_scheduler.md`、`docs/blueprint/architecture.md` 及 `docs/blueprint/domain.md` 的双层并发与队列说明。

verdict: PASS