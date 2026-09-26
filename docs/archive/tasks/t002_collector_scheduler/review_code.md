# Code Review: t002 采集与调度重构

reviewed_scope: 23bc7cd3a2f84d85

## 审查范围

- 比较基线：`c01c8bfcde06f14510a57d5fe9bc25df6576aa90`
- 审查文件：
  - `src/agent_rank/models.py`
  - `src/agent_rank/collector.py`
  - `src/agent_rank/scheduler.py`
  - `src/agent_rank/metrics.py`
  - `src/agent_rank/matrix.py`
  - `src/agent_rank/harness/base.py`
  - `src/agent_rank/harness/opencode.py`
  - `src/agent_rank/harness/grok.py`
  - `src/agent_rank/harness/codex.py`
  - `src/agent_rank/harness/kimi.py`
  - `src/agent_rank/harness/__init__.py`
  - `scripts/run_bench.py`
  - `tests/test_scheduler.py`
  - `tests/test_metrics.py`
  - `tests/test_results_schema.py`
  - `tests/test_kimi_harness.py`
  - `tests/conftest.py`
  - `results.jsonl`
  - `docs/blueprint/architecture.md`
  - `docs/tasks/t002_collector_scheduler/spec.md`
  - `docs/tasks/t002_collector_scheduler/task.md`

## 契约核验 (AC-001 ~ AC-007)

1. **AC-001 (队列调度与并发隔离)**: PASS
   - `GridCell.queue_key` 严格基于 `source:harness` 生成。
   - `QueueScheduler` 同队列内循环同步阻塞执行，无时间重叠；队列间通过 `ThreadPoolExecutor` 独立并行调度。
   - 调度日志包含 `queue={queue_key}`。
   - 单测 `tests/test_scheduler.py:test_scheduler_queue_parallelism_and_serialization` 验证通过。

2. **AC-002 (3+1 Batch 与队列末尾补测)**: PASS
   - 同格常规 3 次调用共享唯一 `batch_id`（12 位十六进制 uuid）。
   - 失败调用暂存 `retry_list`，在整条队列正常轮次完成后统一在末尾补测 1 次（`rep=4`），复用相同 `batch_id`。
   - 无独立 warmup 记录，同格最多 4 次调用。
   - 单测 `tests/test_scheduler.py:test_scheduler_batch_and_retry` 验证通过。

3. **AC-003 (生成窗口来源符合契约)**: PASS
   - `opencode`: 提取 text part 的 `time.start` 到 `time.end` 毫秒差计算秒数，来源标为 `opencode:text_part_time`。
   - `grok`: 提取最后一条 content 增量时刻减去 TTFT，来源标为 `grok:last_content_minus_ttft`，明确未使用 `duration_api_ms`。
   - `kimi`: 提取 wire 记录的 `llmServerDecodeMs`，来源标为 `kimi:llm_server_decode_ms`。
   - `codex`: 生成窗口与来源字段均返回 `None`。
   - 单测 `tests/test_metrics.py` 覆盖 4 个 harness 的解析用例。

4. **AC-004 (TTFT 与双 TPS 口径)**: PASS
   - TTFT 解析覆盖思考事件（`reasoning`/`thought`/`thinking`）与首可见文本 token。
   - `calculate_tps` 严格实现 `e2e_tps = out_tokens / wall`，`gen_tps = out_tokens / decode_window`（窗口为空时为 None）。
   - 单测 `tests/test_metrics.py:test_tps_calculation` 验证通过。

5. **AC-005 (kimi argv 直传与工具隔离)**: PASS
   - `build_kimi_cmd` 通过 `-p` argv 直传完整 prompt 与切片代码，不借助任何文件读取工具。
   - `find_latest_kimi_wire` 实时校验 wire 事件流，出现 `tool_call` 即标记失败。
   - `get_kimi_global_effort` 读取 `~/.kimi-code/config.toml`，不匹配时状态标记为 `skipped` 并写入排除原因。
   - 单测 `tests/test_kimi_harness.py` 验证通过。

6. **AC-006 (results.jsonl Schema 与安全性)**: PASS
   - `append_result_record` 追加写单行 JSON，包含契约 §7.1 规定的 20 个字段。
   - `CallRecord.to_dict()` 确保不包含模型输出正文、原始事件流；自动脱敏用户主目录路径。
   - 单测 `tests/test_results_schema.py:test_results_jsonl_schema_and_append` 验证通过。

7. **AC-007 (真实 200K 冒烟)**: PASS
   - `results.jsonl` 已包含 `opencode`（`gemini-3.8-flash`）真实调用成功记录，各项指标字段非空。
   - 已包含 `kimi` 真实调用记录，如实捕获 Node 栈限制（`RangeError: Maximum call stack size exceeded`）与跳过记录，契约与回退策略相符。

## 架构与工程规范审查

- **架构解耦**: Harness 统一继承 `BaseHarness`，解析器（`metrics.py`）、调度器（`scheduler.py`）、落盘器（`collector.py`）职责边界清晰。
- **并发与隔离**: 独立调用在临时目录（`tempfile.TemporaryDirectory`）执行，避免工作区污染。
- **安全与防泄漏**: 字段白名单过滤，无 API key、无本机绝对路径、无大段回答入库。
- **未阻断观察项 (Non-blocking)**:
  1. `CallRecord.to_dict` 中的路径脱敏正则主要针对 `/Users/`（macOS），跨平台至 Linux 时可补充 `/home/` 规则。
  2. `scheduler.py` 中 `status == "skipped"` 当前也会进入末尾 `rep=4` 补测，虽无害且符合至多 4 次原则，但可于后续优化跳过补测。

## AC 复验方式

在工作仓库 `/Users/karson/kar/code/agent_rank_t002` 下执行以下命令复验：

1. **单元测试集复验（覆盖 AC-001 ~ AC-006）**:
   ```bash
   pytest tests -q
   ```
   预期输出：15 passed。

2. **Schema 结构与字段校验**:
   ```bash
   pytest tests/test_results_schema.py -v
   ```
   预期输出：`test_results_jsonl_schema_and_append` PASSED。

3. **调度器并发与串行时序验证**:
   ```bash
   pytest tests/test_scheduler.py -v
   ```
   预期输出：`test_scheduler_queue_parallelism_and_serialization` 与 `test_scheduler_batch_and_retry` PASSED。

4. **真实冒烟产物核验（AC-007）**:
   ```bash
   python3 -c '
   import json
   from pathlib import Path
   lines = [json.loads(l) for l in Path("results.jsonl").read_text().strip().splitlines()]
   assert any(r["harness"] == "opencode" and r["status"] == "success" and r["e2e_tps"] is not None for r in lines)
   assert any(r["harness"] == "kimi" for r in lines)
   print("AC-007 verified: results.jsonl contains valid opencode run and kimi run.")
   '
   ```

verdict: PASS
