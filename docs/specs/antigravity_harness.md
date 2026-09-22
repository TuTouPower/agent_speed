# Antigravity (agy) 评测框架适配规范 (Antigravity Harness Spec)

## 1. 概述与目标

定义 Google Antigravity CLI（`agy`）作为测速框架的适配规范，支持在 200K 长上下文场景下通过命令行直传切片、流式事件打点解析、两类 TPS 指标采集并接入并发队列调度系统。

## 2. 调度与比较单位

- **队列键（Queue Key）**：固定为 `google:antigravity`。
- **并发约束**：同队列内调用严格串行，与其他框架队列并行并发，无全局并发上限。
- **批次规则**：遵循 3+1 Batch 机制，每格 3 次常规调用 + 失败末尾补测 1 次，归属同一 `batch_id`，无独立 warmup。

## 3. 命令行参数与数据直传契约

- **命令结构**：
    `agy -p "<prompt>\n\n===== CODE FIXTURE =====\n<fixture>" --output-format stream-json`
- **参数透传**：
    - `--model`：传入待测模型标识（如 `gemini-3.8-flash-high`、`gemini-3.8-flash-low`）。
    - `--effort`：传入思考强度档位（如 `high`、`low`）。
- **长文本传输**：
    任务 Prompt 与 200K Django 切片文本合并后经 `-p` 参数（argv）一次性直传。实测 `agy` 原生支持 ~973KB argv 输入，无工具调用借道开销。

## 4. 事件流解析与指标提取

采用 `--output-format stream-json` 输出，逐行捕获 NDJSON 事件流与到达时间戳：

- **首字延迟（TTFT）**：
    首个包含 `text_delta` 且 `step_type == "agent_response"` 的 `step_update` 事件到达时刻（秒）。
- **解码生成窗口（Decode Window）**：
    最后一个包含有效 `text_delta` 的事件到达时刻减去 TTFT：
    `decode_window = round(last_delta_t - ttft, 3)`
    来源标识严格记录为 `antigravity:last_delta_minus_ttft`。
- **账单与输出 Token**：
    从 `step_update.usage` 或 `result.usage` 中提取 `input_tokens` 与 `output_tokens`。
- **双 TPS 计算**：
    - 端到端 TPS：`output_tokens ÷ wall`
    - 生成 TPS：`output_tokens ÷ decode_window`

## 5. 持久化与上站规则

- **持久化记录**：每次调用单行追加写入 `results.jsonl`，包含全部 19 个规定字段，不得包含模型输出全文与开发者本机绝对路径。
- **上站判定**：最新批次内有效次数 ≥ 2、账单输入 token ≥ 100,000 的格子参与中位数聚合，按端到端 TPS 降序收录进 `latest.json`。
