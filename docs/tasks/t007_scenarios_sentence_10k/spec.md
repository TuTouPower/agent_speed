# Task spec

## 背景

公开榜只有 `200k`。短输入和日常工作集测不到：一句话档的预填可忽略，10K 档的预填开始可见，两者都和 200K 不是同一体制。1K 与一句话同体制，100K 只是 200K 的中间采样，本次都不做。

10K 切片已在主干（`fixtures/django_10k.txt`，cl100k 为 10000，且是 200K 切片的字节前缀）。缺的是档位选择、一句话任务，以及分榜聚合。当前报告把所有 `scenario` 按端到端 TPS 排进同一个数组；`cl100k_tokens` 缺省按 200000 做账单门槛。短档若直接写入该数组，会占满 200K 榜，或被 10 万 token 门槛全部拒掉。

## 契约区

### 范围

- 运行入口一次运行只选一档：`sentence`、`10k`、`200k`。未指定时仍为 `200k`。
- `sentence` 的用户内容就是下面这一句，不附加 Django 切片，不附加 fixture 分隔标记。cl100k_base 计数为 61。

```
请用中文写一篇 800 到 1200 字的短文，说明关系型数据库里的迁移解决什么问题；不要调用工具，不要读写文件，不要输出思考过程。
```

- `10k` 的任务说明与 `prompts/task_200k.md` 全文相同，附加的切片是 `fixtures/django_10k.txt`。记录上的 `cl100k_tokens` 为 10000。
- `200k` 保持现有任务说明、`fixtures/django_200k.txt` 与 `cl100k_tokens` 200000。
- 配置矩阵里的 `model` / `effort` / `source` / `harness` 格子集合不因档位增删。选中的档写入该次每条调用的 `scenario` 与对应 `cl100k_tokens`。
- 聚合从同一份 `results.jsonl` 写出三份榜，互不混排，不合成总分：
    - `data/latest.json`：只含 `200k`
    - `data/latest_10k.json`：只含 `10k`
    - `data/latest_sentence.json`：只含 `sentence`
- 三档继续使用既有上站规则（成功、`out_tokens >= 500`、最近 2 次有效、中位数、无生成窗口时 `gen_tps` 为 null）。账单输入门槛的分母改为该记录自己的 `cl100k_tokens`。
- 仓库入口说明改为三档分榜；不把 `100k` 或 `1k` 写成已上线档位。

### 非范围

- 不新增 `1k`。不实施 `100k`。不归档、不改写 `docs/pending/parked/p002_multi_scenario_expansion.md`。
- 不重切 Django 语料，不改 `prompts/task_200k.md` 正文。
- 不跑实网矩阵，不刷新现有 `data/results.jsonl` 与已上站的 200K 样本。
- 不渲染站点，不改仓外消费者。不要求重截 200K 榜预览图。
- 不改 200K 上 Kimi 超长切片截断（含把 `cl100k_tokens` 记为 173218）。本 task 只保证 `10k` 与 `sentence` 不进入该截断。
- 不自动判定模型是否写成 800 到 1200 字。该句长只是提示词约束；上站仍用 `out_tokens >= 500`。
- 不把三档 TPS 合成总分，也不按端到端 TPS 跨档排序。

### 验收标准

<!-- 规范（门禁必留，不得删除） -->

只写可观察、可独立验证的行为；每条使用稳定且不复用的 `AC-NNN`。需真实部署或人工环境验证时在编号前加 `[deploy]`。技术选型不作为行为 AC。

<!-- /规范 -->

- [ ] AC-001：选定 `sentence` 时，送入模型的用户内容等于范围中的那一句（cl100k_base 为 61），且不含 fixture 正文与 fixture 分隔标记。写出的调用记录 `scenario` 为 `sentence`，`cl100k_tokens` 为 61。
- [ ] AC-002：选定 `10k` 时，任务说明与 `prompts/task_200k.md` 全文一致，附加切片为 `fixtures/django_10k.txt` 的全文（cl100k 为 10000，且是 `fixtures/django_200k.txt` 的字节前缀），切片不被截断。写出的调用记录 `scenario` 为 `10k`，`cl100k_tokens` 为 10000。
- [ ] AC-003：未指定档位时仍跑 `200k`：任务说明为 `prompts/task_200k.md`，切片为 `fixtures/django_200k.txt`，记录 `scenario` 为 `200k`，`cl100k_tokens` 为 200000。
- [ ] AC-004：同一次运行只产生一个 `scenario`。三档各自跑完后，格子的 `model`、`effort`、`source`、`harness` 集合与配置矩阵一致，不因档位增删格子。
- [ ] AC-005：`10k` 与 `sentence` 不截断输入，也不把 `cl100k_tokens` 改写成 173218。
- [ ] AC-006：同一份 `results.jsonl` 聚合出三份 JSON 数组。`data/latest.json` 只含 `200k`，`data/latest_10k.json` 只含 `10k`，`data/latest_sentence.json` 只含 `sentence`。每份内部按 `e2e_tps` 降序；某档无上站行时该文件为 `[]`。聚合不改写 `results.jsonl`。
- [ ] AC-007：三档共用既有有效性（`status == success`、`out_tokens >= 500`、最近 2 次有效成功、中位数；无生成窗口时 `gen_tps` 为 null）。账单输入中位数低于该记录 `cl100k_tokens` 的一半则不上站，等于一半上站。`200k` 记录缺 `cl100k_tokens` 时分母仍为 200000。`10k` 或 `sentence` 缺 `cl100k_tokens` 时不上站，且不得把分母当成 200000。
- [ ] AC-008：仓库入口说明写明已支持 `sentence`、`10k`、`200k`，三档各自排名、不合成总分，且不把 `100k` 或 `1k` 写成已上线档位。

### 可测试性声明

<!-- 规范（门禁必留，不得删除） -->

逐条说明不可自动测试的 AC 及替代验证；全部可测则写“全部 AC 可自动测试”。

<!-- /规范 -->

- 全部 AC 可自动测试。

## 上下文区

- 来源：p002（2026-09-23 核实）。p002 暂搁一句话、10K、100K。本次只立项一句话与 10K；100K 仍 parked，不归档 p002。1K 已否定。10K 切片已在主干。当前 `data/latest.json` 是跨 scenario 的单一数组，报告缺省把账单门槛分母当成 200000。

### 有意不测

- 实网调用与真实 TTFT / TPS：不在本 task 访问服务商，也不刷新已上站样本。
- 模型是否遵守 800 到 1200 字：只检查提示词含该约束。
- `100k` 与 `1k`：未立项。
- 站点页面与仓外对 `data/latest.json` 的读取：数组形状保持只含 `200k`，消费者不在本仓。
- 200K 榜预览图：200K 行集规则不变，不要求重截图。
- 200K 上 Kimi 超长截断：既有行为，本 task 只锁定 `10k` 与 `sentence` 不进入该分支。

### 测试策略

- 用假 harness 或拦截子进程，断言三档送出的用户内容、切片、`scenario` 与 `cl100k_tokens`。`10k` 断言切片字节等于 `fixtures/django_10k.txt`，且是 `fixtures/django_200k.txt` 的前缀。
- 构造 `results.jsonl`，覆盖分榜、空档、`e2e_tps` 降序，以及账单门槛边界：等于一半上站、低于一半不上站、`200k` 缺 `cl100k_tokens` 仍按 200000、`10k` / `sentence` 缺 `cl100k_tokens` 不上站。短输出（`out_tokens` 499）不上站。
- 既有 200K 报告用例的预期保持不变。新增用例覆盖新语义，不把旧断言改成新实现的输出。

### 未知契约清单

<!-- 规范（门禁必留，不得删除） -->

未核实的外部契约标为 `UNVERIFIED-BLOCKING` 或 `UNVERIFIED-SPIKE`；核实后改写为结论和验证方式。无则写“无”。

<!-- /规范 -->

- 无。

### 风险与回退

- 风险：三档若排进同一个数组，短输入会占满公开榜。若改掉 `200k` 缺省分母 200000，历史 200K 行会掉榜。
- 回退：三份榜都可由 `results.jsonl` 重算。保持 `data/latest.json` 为只含 `200k` 的数组，即恢复现有消费者。

### 依赖与约束

- 无未合并 task。`fixtures/django_10k.txt` 与 `prompts/task_200k.md` 已在主干。不新增外部服务。

### Finalization 时更新的 blueprint

- `docs/blueprint/domain.md`：Scenario 改为已支持 `sentence`、`10k`、`200k`；`100k` 仍未做。
- `docs/blueprint/architecture.md`：按档选择输入；三份榜分文件，不合成总分。
- `docs/blueprint/decisions.md`：记录档位取舍。不做 `1k`；`100k` 不在本 task；三档分榜；`sentence` 是单句输入加有界短输出提示，上站门槛仍是 `out_tokens >= 500`。
