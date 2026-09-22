# 模型速度基准复现提示词（全文粘贴给目标机器上的 Agent，对方看不到本仓库代码）

你要从零复现一套模型速度基准测试。被测对象：本机已安装的 Agent CLI（opencode / grok / codex 三类，缺哪个就测哪两个，并在报告声明）。

## 1. 原理：三个数

- wall：一条 prompt 从发起到输出结束的端到端秒数（单调时钟 `monotonic`，`t_end - t_start`）。
- TTFT：从发起到首个正文内容到达的秒数。注意 opencode 是服务端整块回包，TTFT≈wall 属正常，不是 bug；grok 才有真流式增量。
- tps（生成吞吐）：`out_tokens / 有效窗口`。窗口分三档，报告必须标注：srv（服务端窗口，最准）、stream（本地增量窗口）、e2e（整段 wall 兜底，含等待，标 `e2e*`）。

## 2. 三档测试 prompt（固定文本，保证 tok/s 可比）

每档核心要求只有一句，必须原样追加：`直接输出答案正文，不要调用任何工具，不要读写文件，不要执行命令。不要输出思考过程，只要最终答案。`

- short：问答，300～500 字。例：`用中文回答以下问题，正文 300～500 字。问题：Python 的 GIL 是什么？它对多线程 CPU 密集型任务有什么影响？给出 20 行以内的示例代码说明。`
- medium：代码生成，150～250 行。例：`写一个 Python 模块，实现线程安全的 LRU 缓存，要求支持 get/put/容量上限与 LRU 淘汰/按 key TTL 过期/线程安全，总长 150～250 行（含注释与用法示例）。`
- long：推理设计，2000～3000 字。例：`设计一个目标 10 万 QPS 的短链服务，按总体架构/发号器与存储选型/缓存与热点/跳转核心代码 50～100 行/压测与容量估算五节作答，全文 2000～3000 字。`

## 3. 三类 Agent 具体怎么调（逐行打点是关键）

共同纪律：每个任务建一个空目录当 cwd、只读运行、timeout 600s；stdout 必须 pipe 逐行读，每行记 `(monotonic - t0, 原文)`，wall 取进程退出时刻；stderr 重定向到文件只留尾 500 字。

- opencode：
  `opencode run --format json --dir <cwd> --variant <effort> -m <model> "<prompt>"`
  stdout 是 JSONL。TTFT = 首个 `{"type":"text"}` 行到达时刻。正文 = 所有 `type=text` 的 `part.text` 拼接。token = `type=step-finish` 的 `part.tokens.{input,output,reasoning}` + `part.cost`。srv 窗口 = 同类 text 事件 `part.time.end - part.time.start`（毫秒转秒），tps_srv = `output / srv窗口`。
- grok：先把 prompt 写文件 `prompt.md`，然后
  `grok --output-format streaming-messages-json --include-partial-messages -m <model> --effort <effort> --always-approve --cwd <cwd> --prompt-file prompt.md`
  TTFT = 首个 `stream_event/content_block_delta/text_delta` 到达时刻，尾时刻 = 末个 text_delta。正文 = 全量 `result` 字段（无则拼 deltas）。token = `message_delta.usage.{output_tokens,input_tokens}`（终值以 `result.usage` 为准）。tps_stream = `output / (尾-首)`，tps_srv = `output / (result.duration_api_ms/1000)`。
- codex：prompt 走 stdin 管道：
  `codex exec --json --skip-git-repo-check --sandbox read-only -C <cwd> -c 'model_reasoning_effort="<effort>"' -m <model> -`
  TTFT = 首个 `item.completed`（带 text）到达时刻。正文 = 该 text。token = `turn.completed.usage.{output_tokens,input_tokens,reasoning_output_tokens}`。无服务端窗口，tps 只能 `output / wall`，记 `e2e*`。

token 通用兜底（事件字段缺失时）：对每行原文正则 `"output_tokens|completion_tokens":(\d+)`、`"input_tokens|prompt_tokens":(\d+)`、`"reasoning_tokens":(\d+)`，最后一次命中为准。chars/s 恒可算（`len(正文)/wall`）。

## 4. 执行纪律（否则数据不可比）

- 每组（模型 x 强度，如 `deepseek-flash/high`）x 三档 x 3 次 = 27 次/组；3 次中第 1 次作 warmup 丢弃，取后 2 次中位数。
- 脏样本剔除：成功且输出字符数在守卫内才算 clean（short 200–4000 / medium 2000–30000 / long 5000–60000），中位数只用 clean；overall = 三档 median 均值，越小越快。
- 顺序随机打乱（seed=42）；全并发跑测的是争抢下吞吐，`--workers 1` 串行（间隔 5s）测纯净速度，两次分开报、不合并。
- 429/timeout/长度越界记失败（`ok=false`），计入 `n_clean/n_total`，不参与排名。

## 5. 交付

一张表：`| group | tier | wall中位 | ttft中位 | out中位 | tps(窗口种类) | n_clean/n_total |` + 失败行 `error` 原文 + 并发声明。先每组 1 次最小 prompt（只回 `OK`）验收连通，`ok=true` 才进全量。
