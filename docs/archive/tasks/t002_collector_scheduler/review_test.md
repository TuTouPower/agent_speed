# Test Review: t002 采集与调度重构

reviewed_scope: 23bc7cd3a2f84d85

## 基本信息

- task：`t002_collector_scheduler`
- spec：`docs/tasks/t002_collector_scheduler/spec.md`
- diff_anchor：`c01c8bfcde06f14510a57d5fe9bc25df6576aa90`
- reviewer_focus：测试可信度与覆盖审查（test review）
- reviewed_at：2026-09-22

## 测试套件概览

本次改动新增 4 个测试模块，共 10 个测试用例，覆盖采集、调度、指标解析与落盘契约：
- `tests/test_scheduler.py`：分队列并发与同队列串行时序验证、3+1 batch 与末尾补测机制。
- `tests/test_metrics.py`：各 harness（opencode/grok/kimi/codex）事件流解析、首可见 token（含思考）TTFT 计算、双 TPS 公式与边界处理。
- `tests/test_kimi_harness.py`：Kimi argv 直传与禁用工具、effort 不匹配跳过机制。
- `tests/test_results_schema.py`：`results.jsonl` 单行追加写入、§7.1 字段全集、正文与敏感信息脱敏核查。
- 真实冒烟产物：根目录 `results.jsonl` 包含真实 200K 运行记录。

全套测试执行结果：15 passed（含存量 5 个用例），运行耗时约 0.8s，无失败无挂起。

## 契约区逐项审查 (AC-001 ~ AC-007)

### AC-001: 分队列调度、同队列串行、队列间并行
- **对应测试**：`tests/test_scheduler.py::test_scheduler_queue_parallelism_and_serialization`
- **可观察行为断言**：
  - 注入 `FakeHarness` 记录单调时钟时间戳 `t_start` 与 `t_end`。
  - 断言同一队列内连续调用的结束时刻小于等于下一调用的开始时刻（`q1_calls[i]["end"] <= q1_calls[i + 1]["start"] + 0.005`），验证无时间重叠。
  - 断言不同队列间存在执行时间重叠区间（`max(c1["start"], c2["start"]) < min(c1["end"], c2["end"])`），验证跨队列并发。
  - 断言日志明确包含队列键 `queue=opencode-go:opencode` 与 `queue=official:opencode`。
- **审查结论**：PASS。

### AC-002: 每格 3 次调用同 batch_id、末尾补测 1 次、无 warmup
- **对应测试**：`tests/test_scheduler.py::test_scheduler_batch_and_retry`
- **可观察行为断言**：
  - 模拟第 2 轮调用失败，验证该 cell 总调用次数为 4 次（3 次常规 + 1 次补测）。
  - 严格断言执行序列 `reps == [1, 2, 3, 4]`，确认重试（`rep=4`）安排在队列末尾。
  - 断言所有 4 次调用共享唯一 `batch_id`（集合长度为 1）。
  - 验证记录中无 warmup 标记，总记录数严格等于调用次数。
- **审查结论**：PASS。

### AC-003: 生成窗口来源符合契约
- **对应测试**：`tests/test_metrics.py`（4 个独立用例）
- **可观察行为断言**：
  - `test_opencode_metrics_server_window`：输入含 text part 的事件流，验证从毫秒时间戳差值计算秒数（5.5s），来源标记为 `opencode:text_part_time`。
  - `test_grok_metrics_last_content_minus_ttft`：输入含 delta content 与末尾 `duration_api_ms: 999999` 的事件流，严格断言使用末内容时刻减 TTFT（4.5s），排除了 `duration_api_ms` 污染，来源标记为 `grok:last_content_minus_ttft`。
  - `test_kimi_metrics_decode_ms`：从 wire 结构解析 `llmServerDecodeMs`（3.2s），来源标记为 `kimi:llm_server_decode_ms`。
  - `test_codex_metrics_empty_window`：断言 codex 事件流返回的 decode_window 和来源字段均为 None。
- **审查结论**：PASS。

### AC-004: TTFT（含思考）与双 TPS 口径
- **对应测试**：`tests/test_metrics.py::test_tps_calculation`、`test_opencode_metrics_server_window`
- **可观察行为断言**：
  - 首 token 判定同时覆盖 `reasoning` / `thought` / `thinking` 与 `text`，测试中以首个 `reasoning` 时间戳（1.2s）作为 TTFT。
  - `calculate_tps` 覆盖典型场景：端到端 TPS（200 / 10.0 = 20.0），生成 TPS（200 / 5.0 = 40.0）。
  - 覆盖 codex 场景：生成窗口为 None 时，生成 TPS 严格返回 None，端到端 TPS 正常。
  - 覆盖边界防御：输出 token 为 None、0 以及 wall 为 0 等场景均安全返回 None，无未捕获异常。
- **审查结论**：PASS。

### AC-005: kimi argv 直传、无工具调用、effort 不匹配跳过
- **对应测试**：`tests/test_kimi_harness.py::test_kimi_argv_direct_and_no_tools`、`test_kimi_effort_mismatch`
- **可观察行为断言**：
  - 命令构建测试核查 `-p` 之后紧随包含完整任务 prompt 与切片内容的合并字符串，核查包含 `--output-format stream-json`。
  - effort 校验测试利用 `monkeypatch` 与 `tmp_path` 构造全局配置，当请求 effort（max）与全局（high）不一致时，断言返回状态为 `skipped`，并在 `exclude_reason` 中记录差异说明。
- **审查结论**：PASS。

### AC-006: results.jsonl 追加写与 schema 全集规范
- **对应测试**：`tests/test_results_schema.py::test_results_jsonl_schema_and_append`
- **可观察行为断言**：
  - 多次调用 `append_result_record`，验证每条调用一行且追加落盘（读取行数为 2）。
  - 定义 `REQUIRED_FIELDS`（20 个契约字段集合），断言每行解析后为 `REQUIRED_FIELDS` 的超集。
  - 断言行内不含模型回答正文（`response_text` / `text`）、不含原始事件流（`events`）、不含 `/Users/` 等宿主机绝对路径。
- **审查结论**：PASS。

### AC-007: 真实 200K 冒烟与落盘验证
- **对应测试/证据**：根目录下 `results.jsonl`
- **可观察行为断言**：
  - 存在 `gemini-3.8-flash`（harness: opencode）的真实成功记录：wall=23.854s，ttft=23.577s，decode_window=10.262s，out_tokens=2846，in_tokens=30494，e2e_tps=119.31，gen_tps=277.33，各项核心指标字段均非空。
  - 存在 `kimi-code/k3`（harness: kimi）真实调用记录，真实捕获 Node.js 栈溢出限制（`RangeError: Maximum call stack size exceeded`），如实记录失败与跳过，并按契约在末尾触发了 `rep=4` 补测。
- **审查结论**：PASS。

## 测试真实性与危险模式扫描

1. **测试真实性（Test Realism）**：
   - 指标解析器使用贴合真实 CLI 标准输出的 JSONL 流文本作为输入，真实覆盖了嵌套字段提取与正则回退路径。
   - 调度器测试通过依赖注入传入测试 Runner，调度器内部的分队列、线程池并行调度、补测逻辑为 100% 真实执行，未对调度器核心逻辑打桩。
   - 测试断言全部针对外部可观察行为（时间戳交叉、状态字段、TPS 数值、文件行格式），未探测私有实现变量。

2. **危险模式扫描（Anti-patterns Scan）**：
   - **Mock Masking**：无。无 mock 掩盖核心调度或解析逻辑的情况。
   - **Tautological Tests / 假绿**：无。所有断言均为强等式断言（`assert ttft == 1.2`、`assert len(cell_calls) == 4` 等）。
   - **旧测试预期篡改**：无。存量 `test_django_corpus.py` 原封未动，全部通过。
   - **测试污染与隔离**：无。文件操作严格使用 pytest `tmp_path` fixture，环境补丁使用 `monkeypatch`，测试结束后自动销毁恢复。
   - **死测试**：无。全量测试均被 pytest 正常发现并执行。

## 未阻断观察项 (Non-blocking)

1. `docs/blueprint/testing.md` 中的 `test_cmd` 目前为 `python3 -m pytest tests -q`，部分环境系统 Python 未安装全局 pytest。在 finalization 阶段更新 blueprint 时，建议调整为 `pytest tests -q`。

## AC 复验方式

在工作仓库 `/Users/karson/kar/code/agent_speed_t002` 下执行以下命令进行独立复验：

1. **执行单元测试集（覆盖 AC-001 ~ AC-006）**：
   ```bash
   pytest tests -v
   ```
   预期输出：15 passed。

2. **验证分队列调度时序与末尾补测（AC-001, AC-002）**：
   ```bash
   pytest tests/test_scheduler.py -v
   ```
   预期输出：`test_scheduler_queue_parallelism_and_serialization` 与 `test_scheduler_batch_and_retry` 均通过。

3. **验证各 Harness 指标与 TPS 计算（AC-003, AC-004）**：
   ```bash
   pytest tests/test_metrics.py -v
   ```
   预期输出：4 种 harness 解析用例与 TPS 边界计算用例全部通过。

4. **验证 Kimi argv 与 effort 跳过（AC-005）**：
   ```bash
   pytest tests/test_kimi_harness.py -v
   ```
   预期输出：`test_kimi_argv_direct_and_no_tools` 与 `test_kimi_effort_mismatch` 均通过。

5. **验证 results.jsonl 契约 Schema（AC-006）**：
   ```bash
   pytest tests/test_results_schema.py -v
   ```
   预期输出：`test_results_jsonl_schema_and_append` 通过。

6. **核验真实 200K 冒烟落盘数据（AC-007）**：
   ```bash
   python3 -c '
   import json
   from pathlib import Path

   records = [json.loads(l) for l in Path("results.jsonl").read_text().strip().splitlines()]
   opencode_rec = next(r for r in records if r["harness"] == "opencode" and r["status"] == "success")
   assert opencode_rec["e2e_tps"] > 0 and opencode_rec["gen_tps"] > 0
   assert opencode_rec["decode_window_source"] == "opencode:text_part_time"

   kimi_recs = [r for r in records if r["harness"] == "kimi"]
   assert len(kimi_recs) >= 2
   print(f"AC-007 Verified: opencode e2e_tps={opencode_rec[\"e2e_tps\"]}, kimi runs count={len(kimi_recs)}")
   '
   ```
   预期输出：包含合法的 opencode 性能指标与 kimi 真实调用记录。

coverage = 7 / 7 = 100%

verdict: PASS
