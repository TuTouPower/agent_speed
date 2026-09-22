# 领域模型

## 核心术语

|术语|英文|说明|
|---|---|---|
|基准评测|Benchmark|对各模型/通道在固定负载下的性能评测。|
|通道|Provider / Channel|调用的接入入口（如 opencode、codex 直调、grok 直调、官方直连等）。|
|思考强度|Reasoning Effort / Variant|模型的思考档位（如 low、medium、high、xhigh、max 等）。|
|吞吐量|TPS (Tokens Per Second)|纯净解码阶段每秒输出的 token 数。|
|首字延迟|TTFT (Time To First Token)|从发起请求到收到首个流式 token 的耗时。|
|端到端耗时|Wall Time|一次完整请求的总物理耗时（秒）。|
|样本轮次|Repetition (Rep)|重复调用的次数；默认第 1 次作 warmup，后续轮次取中位数。|
|长上下文|Context Benchmark|超长输入场景（如 300K tokens），侧重考察 TTFT 与大上下文解码性能。|
|夹具|Fixtures|预先打包切片的长文本素材。|
