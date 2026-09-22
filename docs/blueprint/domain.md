# 领域模型

## 核心术语

|术语|英文|说明|
|---|---|---|
|比较单位|Comparison Unit|基准比较单位为「`model` × `effort` × `source` × `harness` × 场景」。|
|服务提供方|Source|模型服务提供方，区分官方直连（如 official）或聚合网关（如 opencode-go、cpa 等）。|
|运行框架|Harness|调用驱动框架（opencode、grok、codex、kimi、antigravity）。|
|思考强度|Reasoning Effort / Variant|模型的思考档位（如 low、high、xhigh、max 等）。按 CLI 原文显示，不做别名归一。|
|队列键|Queue Key|以「`source + harness`」为队列键。同队列严格串行，不同队列全并行。|
|批次机制|3+1 Batch|每个格子跑 3 次调用归属同一 `batch_id`；失败调用在队列末尾补测 1 次，同格最多 4 次，无 warmup。|
|端到端耗时|Wall Time|进程启动至退出的完整物理端到端时间（秒）。|
|首字延迟|TTFT (Time To First Token)|首个可见 token（含思考推理或正文）到达时刻（秒）。|
|生成窗口|Decode Window|真实解码阶段时间窗（不含预填与首字前时间）。codex 为空。|
|端到端 TPS|E2E TPS|`输出 token ÷ wall`。主排序指标。|
|生成 TPS|Generation TPS|`输出 token ÷ 生成窗口`。仅展示，生成窗口为空时为 null。|
|语料切片|Corpus Slice|`django/django` tag 6.1.1 的源码与文档有序切片（10K/100K/200K cl100k 计数）。|
|账单输入|Billed Input Tokens|服务商事件流返回的 prompt/input token 数。低于切片一半的格子不上站。|
|上站聚合|Latest Report|每个格子仅取最新 `batch_id`，有效次数 ≥ 2，中位数聚合，按端到端 TPS 降序。|
