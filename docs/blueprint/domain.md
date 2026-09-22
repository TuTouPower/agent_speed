# 领域模型

## 核心术语

|术语|英文|说明|
|---|---|---|
|比较单位|Comparison Unit|基准比较单位为「`model` × `effort` × `source` × `harness` × `scenario`」。|
|评测场景|Scenario|评测输入上下文与任务规模。MVP 版本为 200K 的 prompt，后续还会支持一句话、10K、100K prompt。|
|服务提供方|Source|模型服务提供方渠道（如 `deepseek-official`、`opencode-go`、`cpa`、`google-antigravity` 等，非裸写 `official`）。|
|运行框架|Harness|调用驱动框架（opencode、grok、codex、kimi、antigravity）。|
|思考强度|Reasoning Effort / Variant|模型的思考档位（如 low、high、xhigh、max 等）。按 CLI 原文显示，不支持者为 null。|
|队列键|Queue Key|基于物理配额限流域划分的并发队列键（`queue`）。单队列最多 2 并发，全系统设 10 并发上限。|
|批次机制|3+1 Batch|每个格子跑 3 次调用归属同一 `batch_id`；失败调用在队列末尾补测 1 次，同格最多 4 次，无 warmup。|
|端到端耗时|Wall Time|进程启动至退出的完整物理端到端时间（秒）。|
|首字延迟|TTFT (Time To First Token)|首个可见 token（含思考推理或正文）到达时刻（秒）。|
|生成时间窗|Generation Window|模型进入正文生成阶段的真实时间窗口（不含预填与首字前时间）。codex 为空。|
|端到端 TPS|E2E TPS|`输出 token ÷ wall`。全流程平均吞吐。200K 场景下受预填固定耗时摊薄影响与输出 token 量强正相关。|
|生成 TPS|Generation TPS|`输出 token ÷ 生成时间窗`。衡量模型纯流式生成吞吐的核心指标，不受预填耗时稀释。codex 为 null。|
|语料切片|Corpus Slice|`django/django` tag 6.1.1 的源码与文档有序切片（10K/100K/200K cl100k 计数）。|
|账单输入|Billed Input Tokens|服务商事件流返回的 prompt/input token 数。低于切片一半的格子不上站。|
|上站聚合|Latest Report|每个格子仅取最新 `batch_id`，有效次数 ≥ 2，中位数聚合，按端到端 TPS 降序。|
