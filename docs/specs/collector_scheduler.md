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
- **生成时间窗（Generation Window）**：
    模型进入正文生成阶段的真实时间窗口（秒，不含预填时间）。来源按各 harness 特性严格划分：
    - `opencode`：提取服务端报告的文本段生成时间窗（`text_part_time`）。
    - `grok`：取最后一个内容 chunk 到达时间减去 TTFT 的增量时间窗（`last_content_minus_ttft`）。
    - `kimi`：取服务端返回指标中的 `llmServerDecodeMs`。
    - `codex`：CLI 未暴露生成时间戳，统一置为 `null`。
    - `antigravity`：取最后一个内容增量（`text_delta`）到达时间减去 TTFT 的增量时间窗（`last_delta_minus_ttft`）。
- **端到端 TPS（E2E TPS）**：
    - 公式：`输出 token 数 ÷ Wall Time`。
    - 作为公开基准排序的主指标。
- **生成 TPS（Generation TPS）**：
    - 公式：`输出 token 数 ÷ Generation Window`。
    - 当生成时间窗为空（如 codex）时，生成 TPS 严格记录为 `null`。
- **超长上下文（200K）下的指标物理机制（关键发现 d001）**：
    - **预填摊薄效应**：在 200K 超长输入下，模型对数十万 Token 的前置预填时间（TTFT，通常在 10s~35s）是一笔固定的沉没成本。端到端 TPS（`输出 token ÷ Wall Time`）受阿姆达尔定律影响，与模型**输出 Token 的绝对数量呈强正相关**（输出内容越多，固定的预填时间在总时长中被摊薄得越薄，计算出的端到端 TPS 显得越高；实测同一模型 3.8K 输出为 114 TPS，10.5K 输出直接飙升至 196 TPS）。
    - **生成 TPS 的核心度量地位**：生成 TPS 剔除了固定的前置预填延迟，直接度量模型在进入纯吐字阶段后的物理流式速率（实测同一模型长短输出下的生成 TPS 高度恒定在 255~273 tok/s）。在 200K 场景下，生成 TPS 才是反映底层真实物理生成速度的硬核指标。

## 5. Harness 适配规则

各 harness 统一以 `prompts/task_200k.md` 为任务说明，以 `fixtures/django_200k.txt` 为评测输入切片。

- **`opencode`**：
    - 参数：`opencode run --format json --dir <cwd> --variant <effort> -m <model> <full_message>`。
    - 输入：切片与任务说明合并为单一完整 message 传入，避免单文件附件的 50KB 软截断。
    - 指标：解析 `text` part 的服务端时间戳（`text_part_time`）。
- **`grok-build`**：
    - 参数：`grok --output-format streaming-messages-json --include-partial-messages -m <model> --effort <effort> --always-approve --cwd <cwd> --prompt-file <prompt_file>`。
    - 输入：任务文本与切片合并写入工作区临时 `grok_prompt.md` 文件传入。
    - 指标：取最后一个内容增量 chunk 到达时刻减去 TTFT 作为生成窗口（`last_content_minus_ttft`），不用 `duration_api_ms`。
- **`codex`**：
    - 参数：`codex exec --json --skip-git-repo-check --sandbox read-only -C <cwd> -c model_reasoning_effort="<effort>" -m <model> -`。
    - 输入：任务文本与切片合并后通过 stdin 标准输入传入。
    - 指标：事件流无生成时间戳，生成窗口置为 `null`。
- **`kimi-code`**：
    - 参数：`kimi -m <model> -p "<prompt>\n\n<fixture>" --output-format stream-json`。
    - 输入：任务文本与切片经 `-p` 命令行参数直传，禁止工具读写文件。
    - 物理上限与安全切片（见 d002）：Node.js 默认栈深度限制下单次 argv 上限为 895KB，故 Kimi 采用 850KB（约 173,218 tokens）安全切片输入，避免 `RangeError: Maximum call stack size exceeded`。
    - 约束：自动读取 `~/.kimi-code/config.toml` 中的全局 `[thinking] effort`，与待测网格不符时标记为 `skipped`；事件流中严禁出现工具调用（`used_tools: false`）。
    - 指标：从 session 落盘记录提取 `llmServerDecodeMs`。
- **`antigravity` (`agy`)**：
    - 200K 多轮流水线注入：针对 `agy` 客户端单消息 150KB 硬截断限制，采用 4 轮会话分块累积机制（Turn 1~3 极速灌入切片仅回复 OK，Turn 4 灌入剩余切片并正式测速）。
    - 测速基准：严格以第 4 轮的端到端耗时作为 Wall Time，账单输入累计吃满 34 万 Tokens，零工具调用。
    - 指标：首个可见 token（含 thinking 或 `text_delta`）计算 TTFT；优先提取服务端上报的 `step_update.duration_seconds` 作为生成时间窗（`antigravity:step_duration_seconds`）；从 `result.usage` 提取最终输入与输出 token。

## 6. 结果持久化（`data/results.jsonl`）

- **写入语义**：单次调用对应一行 JSON，以线程安全的原子追加模式写入 `data/results.jsonl`。
- **字段规范（Schema）**：
    必须完整包含以下 20 个字段：
    `scenario`, `model`, `effort`, `source`, `harness`, `rep`, `batch_id`, `start_time`, `wall`, `ttft`, `decode_window`, `out_tokens`, `in_tokens`, `e2e_tps`, `gen_tps`, `decode_window_source`, `cl100k_tokens`, `status`, `used_tools`, `exclude_reason`, `error_summary`。
- **敏感信息治理**：
    严禁将模型生成的完整文本、中间调试事件流、API 密钥以及开发者本机绝对路径落入 `data/results.jsonl`。
