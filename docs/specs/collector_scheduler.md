# 评测调度与指标采集规范 (Collector & Scheduler Spec)

## 1. 概述与目标

定义评测网格模型、基于服务来源与框架的队列并发调度器、3+1 批次容错机制、多框架适配器以及两类 TPS 等核心指标的采集口径。

## 2. 评测网格与比较单位

- **基准比较单位**：
    基准比较单位为五元组：「`model` × `effort` × `source` × `harness` × `scenario`」。
    - `scenario`：评测场景（MVP 阶段固定为 `200k`）。
    - `source`：模型服务提供方渠道（如 `deepseek-official`、`mimo-official`、`google-antigravity`、`cpa`、`opencode-go`、`openai`、`xai`、`moonshot`），严禁裸写 `official`。
    - `harness`：评测运行驱动框架（如 `opencode`、`grok`、`codex`、`kimi`、`antigravity`）。
    - `model`：客观标准模型标识（如 `deepseek-v4.1-flash`、`gemini-3.8-flash`）。
    - `cli_model`：CLI 客户端入参别名（如 `ds-off/deepseek-flash`、`cpa/gemini-3.8-flash`）。
    - `effort`：模型思考强度或变体档位（如 `high`、`max`，不支持者为 `null`）。
- **网格键（Grid Key）**：
    每个评测单元的唯一标识符格式为 `{scenario}:{source}:{harness}:{model}:{effort}`。

## 3. 队列调度与并发模型

- **物理队列划分（Queue Key）**：
    每个网格在配置中显式绑定物理限流域 `queue`（如 `deepseek-official`、`opencode-go`、`google-gemini`、`mimo-official`）。
- **双层受控并发规则**：
    - **单队列并发上限**：每个队列内部最多允许 **2 并发** 运行，避免单一底层服务商账号或本地实例产生排队抖动。
    - **全局并发上限**：全系统设置 **10 并发** 上限，防止进程过多消耗本机物理资源或触发网关总控限流。
- **配额池隔离**：
    - Gemini CPA 渠道与 Antigravity 渠道共享 `google-gemini` 队列，受单队列 2 并发限制。
    - 官方直连（如 `deepseek-official`、`mimo-official`）与聚合代理（`opencode-go`）分属不同队列，完全并行执行。
- **3+1 Batch 机制**：
    - 每个网格单元计划执行 3 次基准调用，全部分配并标记同一个唯一的 `batch_id`。
    - 不设置独立的 warmup 预热轮次。
    - 若某次调用失败，在该单元所属队列末尾自动追加 1 次补测。
    - 同一个网格单元在同个批次内最多执行 4 次调用（3 次正常 + 1 次补测）。

## 4. 指标测量与计算口径

- **端到端耗时（Wall Time）**：
    子进程从启动至完全退出的高精度物理耗时（秒）。
- **首字延迟（TTFT, Time To First Token）**：
    首个可见 token 到达的相对耗时（秒）。
    - **重要约束**：TTFT 必须包含模型思考与推理过程；若模型先输出 reasoning token，首个 reasoning token 到达时刻即为 TTFT。
- **解码生成窗口（Decode Window）**：
    模型处于真实正文解码阶段的时间窗口（秒）。来源按各 harness 特性严格划分：
    - `opencode`：提取服务端报告的文本段解码时间窗（`text_part_time`）。
    - `grok`：取最后一个内容 chunk 到达时间减去 TTFT 的增量时间窗。
    - `kimi`：取服务端返回指标中的 `llmServerDecodeMs`。
    - `codex`：CLI 未暴露解码时间戳，统一置为 `null`。
    - `antigravity`：取最后一个内容增量（`text_delta`）到达时间减去 TTFT 的增量时间窗（`last_delta_minus_ttft`）。
- **端到端 TPS（E2E TPS）**：
    - 公式：`输出 token 数 ÷ Wall Time`。
    - 作为公开基准排序的主指标。
- **生成 TPS（Generation TPS）**：
    - 公式：`输出 token 数 ÷ Decode Window`。
    - 当解码生成窗口为空（如 codex）时，生成 TPS 严格记录为 `null`。

## 5. Harness 适配规则

各 harness 统一以 `prompts/task_200k.md` 为任务说明，以 `fixtures/django_200k.txt` 为评测输入切片。

- **`opencode`**：
    - 参数：`opencode run --format json --dir <cwd> --variant <effort> -m <model> <prompt> -f <fixture>`。
    - 输入：切片文件通过 `-f` 命令行参数挂载。
    - 指标：解析 `text` part 的服务端时间戳（`text_part_time`）。
- **`grok`**：
    - 参数：`grok --output-format streaming-messages-json --include-partial-messages -m <model> --effort <effort> --always-approve --cwd <cwd> --prompt-file <prompt_file>`。
    - 输入：任务文本与切片合并写入工作区临时 `grok_prompt.md` 文件传入。
    - 指标：取最后一个内容增量 chunk 到达时刻减去 TTFT 作为生成窗口（`last_content_minus_ttft`），不用 `duration_api_ms`。
- **`codex`**：
    - 参数：`codex exec --json --skip-git-repo-check --sandbox read-only -C <cwd> -c model_reasoning_effort="<effort>" -m <model> -`。
    - 输入：任务文本与切片合并后通过 stdin 标准输入传入。
    - 指标：事件流无解码时间戳，生成窗口置为 `null`。
- **`kimi`**：
    - 参数：`kimi -m <model> -p "<prompt>\n\n<fixture>" --output-format stream-json`。
    - 输入：任务文本与切片经 `-p` 命令行参数直传，禁止工具读写文件。
    - 约束：自动读取 `~/.kimi-code/config.toml` 中的全局 `[thinking] effort`，与待测网格不符时标记为 `skipped`；Node.js argv 栈溢出捕获为 `failed`。
    - 指标：从 session 落盘记录提取 `llmServerDecodeMs`。
- **`antigravity` (`agy`)**：
    - 参数：`agy -p "<prompt>\n\n<fixture>" --model <model> --effort <effort> --output-format stream-json`。
    - 输入：任务文本与切片经 `-p` 命令行参数直传。
    - 指标：首个可见 token（含 thinking 或 `text_delta`）计算 TTFT；末尾有效 `text_delta` 到达时刻减去 TTFT 计算生成窗口（`last_delta_minus_ttft`）；从 `usage` 提取输入与输出 token。

## 6. 结果持久化（`results.jsonl`）

- **写入语义**：单次调用对应一行 JSON，以线程安全的原子追加模式写入 `results.jsonl`。
- **字段规范（Schema）**：
    必须完整包含以下 19 个字段：
    `scenario`, `model`, `effort`, `source`, `harness`, `rep`, `batch_id`, `start_time`, `wall`, `ttft`, `decode_window`, `out_tokens`, `in_tokens`, `e2e_tps`, `gen_tps`, `decode_window_source`, `cl100k_tokens`, `status`, `exclude_reason`, `error_summary`。
- **敏感信息治理**：
    严禁将模型生成的完整文本、中间调试事件流、API 密钥以及开发者本机绝对路径落入 `results.jsonl`。
