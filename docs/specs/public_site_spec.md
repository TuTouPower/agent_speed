# agent_speed 公开站契约

决策状态：Accepted（2026-09-22，用户确认）。
实现状态：未实现。
验证状态：未验证。

本文件是公开基准与展示站的契约全文。它描述目标，不是当前目录已经在做的事。当前可运行行为以 `README.md` 和代码为准。二者冲突时：代码是现状，本文件是目标。实现不得把本文件改写成已完成。

里程碑：MVP 只做 200K 场景。一句话、10K、100K 只定边界，不在 MVP 实现。

## 1. 与当前目录的差异

|项|当前|目标|
|---|---|---|
|位置|本地私有目录|公开仓库 `TuTouPower/agent_speed`|
|语料|内部私有项目快照|`django/django` 的固定 commit 切片|
|已有结果|私有语料跑分产物|不上公开站|
|存储|各次 `runs/`、markdown、图片|`results.jsonl` + `latest.json`。不出图|
|吞吐|口径混在一个 `tps` 里，codex 用输出 token / wall|两个 TPS：端到端 TPS = 输出 token ÷ wall；生成 TPS = 输出 token ÷ 生成窗口。codex 无生成窗口，该列为空|
|并发|多次跑分默认并发|按「source + harness」分队列|
|展示|本地 markdown / png|Cloudflare Pages 上的静态页|

内部私有项目的切片正文、文件清单、任务原文、模型回答和已有跑分都不进入公开仓库，也不进入页面。

## 2. 产品

读者是正在选择 coding agent 或 API 来源的人。比较单位是「`model` × `effort` × `source` × `harness` × 场景」。`source` 是模型服务提供方（官方直连或聚合网关），`harness` 是运行框架。`harness` 名和 `effort` 按 CLI 原文显示，不做别名归一。

这是速度，不是能力排名。页面写明这一点。不评答案质量。

仓库名 `agent_speed`。许可证 AGPL。Django 切片自带的 BSD 声明保留在切片旁，不换成 AGPL。

两个产物：

- 公开仓库：跑分代码、切片、`results.jsonl`、`latest.json`、生成 `latest.json` 的脚本。
- 网站：内部站点仓库的 `web/`。静态页。不接登录、数据库、计费，不引用该仓库的 auth、db、billing。网站不实现中位数和过滤，只渲染已经算好的 `latest.json`。

## 3. 场景与语料

场景四级：一句话、10K、100K、200K。

10K 是 100K 的前缀，100K 是 200K 的前缀。沿用按 cl100k 计数、路径有序、最后一文件可被截断的打包方式。一句话不是这份代码的前缀，它是另一条短输入场景。MVP 不跑一句话、10K、100K。不同场景的 TPS 不排进同一张表。

语料：

- 仓库 `django/django`，pin tag `6.1.1`（commit `249b13d6e93ee3164dee8ed1775395622a50c337`）。
- 只收源码和文档。排除测试、迁移、locale、生成文件。
- 打包脚本、文件清单、切片正文进公开仓库。
- 页面写明：这是该 commit 的有序切片，不是整个 Django。

任务对所有 harness 是同一份中文、同一份字节，全文公开。内容：根据切片说明分层、模块职责、数据流、技术选型。自然长度。禁止工具，禁止读写文件。做不到这一点的 harness 没有成绩，不为它改协议。

## 4. 调度

队列键是「source + harness」。

- 同一队列内，不同模型、不同 effort、不同 rep 都串行。
- 队列之间并行。不另设全局并发上限。
- DeepSeek 官方（官方直连）与 opencode-go 的 DeepSeek 不是同一条队列，可以同时跑。
- opencode 上 source 不同的模型可以同时跑：Muse、Gemini（`cpa/`）、MiMo、Step、opencode-go 的 DeepSeek 各一条。
- Codex 上的 GPT 模型一条。Grok 模型一条。Kimi 模型一条。

Kimi 没有命令行 effort 档位，effort 取全局 `~/.kimi-code/config.toml` 的实际值；请求的档与全局不符时跳过该组，不伪造标注。Kimi 的 200K 切片经 `-p` argv 直传，不借工具读文件。

每个格子（场景 × `source` × `harness` × 模型 × `effort`）跑 3 次，不单独做 warmup。失败的调用在该队列末尾补测 1 次，再失败则该次缺失。这几次构成该格子的最新 batch。补测不占用其他队列。

同一队列里的顺序不保证缓存是热的。不把第一次另记为 warmup。

## 5. 指标

一次调用从 harness 事件流里取数。对方账单上的输入 token 是事件流字段 `input_tokens` 或 `prompt_tokens`，不是本地 cl100k 计数。各家分词器不同，系统提示词也算在里面，所以它通常不等于切片的 200000。高于 200000 只说明对方数得更多，不说明吃进了额外正文，也不因此判为截断。

记录三个时间量：

- wall：进程启动到退出的端到端时间。
- TTFT：首个可见 token 的到达时间，含思考，不是网络延迟。不从 TTFT 里拆预填，现有事件流拆不开。
- 生成窗口：解码阶段的时间窗，不含首字之前的时间，也不含预填。
    - opencode：文本段的服务端时间窗（`text` part 的 `time.start` 到 `time.end`）。
    - grok：最后一条内容增量的到达时刻减去 TTFT。不用 `duration_api_ms`。
    - kimi：session 落盘的 `llmServerDecodeMs`。
    - codex：事件流没有生成窗口，字段为空。

两个 TPS：

- 端到端 TPS = 输出 token / wall。
- 生成 TPS = 输出 token / 生成窗口。生成窗口为空时该值也为空。

页面按端到端 TPS 从高到低排列，生成 TPS 只做展示列。

TTFT 含思考这一点，页面如果写出 TTFT，必须同时写明含思考。

不增加「秒/千 token」列，也不按它排序。

## 6. 上站规则

`latest.json` 每个格子只看最新一个 batch。更早的合格 batch 不补位。

一次调用无效，不进入中位数：

- 输出 token 低于 500。这只丢掉极短废样本，不规定作文长度。
- 调用失败，且补测后仍失败。

整个格子不上站，原始行仍留在 `results.jsonl`：

- 最新 batch 里有效次数不足 2。
- 对方账单输入 token 低于切片 cl100k token 数的一半。这表示正文明显没送进模型，或被对方窗口裁掉。不是我们去砍输入。分词器不会把同一份代码数到一半以下。只吃进更短题目的行，解码会显得更快，不能和吃满的行排在一起。

没有生成窗口的格子照常上站（codex），生成 TPS 列留空，不因此整格排除。

上站格子取有效次数的中位数。页面按端到端 TPS 从高到低排列。

页面列：`model`、`effort`、`source`、`harness`、端到端 TPS、生成 TPS、TTFT、输出 token、对方账单输入 token。标明场景是 200K。TTFT 写明含思考。写上「速度不是能力排名」，并链接到 `TuTouPower/agent_speed`。没有够格格子时是空表，不用旧数据填充。

对方账单输入 token 在不合格行里也要保存。页面只给上了站的行展示这一列。

## 7. 数据文件

### 7.1 `results.jsonl`

只追加。一行一次调用。不删除、不修改旧行。网站不读这个文件。

每行字段：

- 场景、`model`、`effort`、`source`、`harness`、第几次、`batch_id`、开始时间
- wall、TTFT、生成窗口、输出 token、对方账单输入 token
- 端到端 TPS、生成 TPS、生成窗口来源
- 切片 cl100k token 数
- 状态、排除原因、错误摘要

不存模型正文。不存 `events/` 原始流。需要复盘时留在本机，不进 Git。密钥、本机绝对路径不进文件。

### 7.2 `latest.json`

由 `results.jsonl` 重新生成，覆盖写。生成脚本在公开仓库。网站不重算。

每个上站格子一行：场景、`model`、`effort`、`source`、`harness`、有效次数、端到端 TPS 中位数、生成 TPS 中位数（可为空）、TTFT 中位数、输出 token 中位数、对方账单输入 token 中位数、`batch_id`。另有生成时间。

行数等于当前上站格子数，不随历史变长。MVP 只有 200K 的行。

## 8. 发布

数据更新不提交进站点仓库。

把现成的页面文件和新的 `latest.json` 放进一个临时目录，执行 `wrangler pages deploy` 上传到 Cloudflare Pages。临时目录不进任何一个 Git 仓库。HTML 没有改动时原样再传，不重新生成。

这次上传：

- 不跑本地测试，不打包，不执行站点仓库的 `turbo` / `pnpm` 构建。
- 不触发该仓库的 GitHub Actions。
- Cloudflare 上会多一次部署记录。那是文件版本，不是构建。

这个 Pages 项目不连接到站点仓库的 Git。否则推上 `main` 会跑整仓质量门禁和构建。

Cloudflare 令牌留在本机环境，不进公开仓库。不使用 R2。不让浏览器请求 GitHub 上的 JSON。

页面源码只有在页面本身改变时才改站点仓库。

## 9. 明确不采用

- 用生成 TPS（窗口口径）作为排序键，或把两个 TPS 合成一个总分。
- 把多个场景或多次 effort 合成一个总分。
- 给答案打质量分。
- 出 PNG，或保留历史图片。
- 用 SQLite 存结果。
- 把不合格行从 `results.jsonl` 删掉，或在页面上单开「未进入排名」表。
- 把网站放到个人域名，或接上站点仓库的登录、数据库、计费。
- 浏览器每次打开都向 GitHub 要 `latest.json`。
- 为这一份 JSON 使用 R2，或把 HTML 放进 R2 当网站托管。
- 数据更新时构建站点仓库。
- 全部调用严格串行，或全部并发。
- 把官方直连与聚合网关算成同一条队列，或把同一 harness 上的不同 source 绑成一条。
- 全局并发上限。
- 单独的 warmup 轮次。
- 公开模型正文、`events/`、内部私有项目实验材料。

## 10. 待定

- 域名，以及 Pages 项目名。
- MVP 实际跑哪些模型、哪些 effort。规则是：会显式传给 CLI 的档都跑，每一档一行。某模型没有的档不跑，也不改名。具体名单开跑时定。
- `django/django` pin 的 commit。
- 一句话、10K、100K 的任务正文和页面形态。加这些场景时不把它们的行并进 200K 这张表。

## 11. 验收

实现完成的含义是契约落地，不是本文件改为已验证。验证要另有一次按本契约跑出的 200K 数据。

- 公开仓库不含内部私有项目切片、旧跑分、模型正文、`events/`、密钥和本机绝对路径。
- 切片可由脚本按 pin 的 commit 重建，10K 是 100K 的前缀，100K 是 200K 的前缀，cl100k 计数符合文件名中的档。
- 任一 harness 的任务字节与公开任务文件一致。使用工具或读写文件的调用没有成绩。
- 调度日志能看出队列键（source + harness）。同一队列没有时间重叠。不同队列可以重叠。DeepSeek 官方与 opencode-go 两条队列可以重叠。
- 每个格子最多 3 次加 1 次补测。没有单独的 warmup 记录。
- `results.jsonl` 在重跑后仍保留旧行。`latest.json` 只含最新 batch，且该 batch 至少 2 次有效。
- 输出低于 500、账单输入低于切片 cl100k 一半的格子不在 `latest.json` 里，对应原始行仍在 `results.jsonl`。没有生成窗口的格子（codex）在表里，生成 TPS 列为空。
- 页面列与排序符合第 6 节。页面数据来自同一次上传的 `latest.json`，不是页面里现算的。
- 只上传静态文件时，本机不执行测试和打包，站点仓库的 GitHub Actions 不触发。
