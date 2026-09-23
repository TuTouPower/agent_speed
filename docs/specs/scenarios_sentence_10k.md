# 三档独立评测规范 (Scenarios: sentence / 10k / 200k)

## 1. 概述与目标

在 200K 长上下文基准之外，新增一句话（`sentence`）与 10K（`10k`）两个独立评测档。同一份 `data/results.jsonl` 写出唯一合一榜单 `data/latest.json`（扁平数组，行内 `scenario` 自描述），互不混排，不合成总分。`100k` 与 `1k` 不在本规范的上线范围。

## 2. 运行入口与输入选择

- 一次运行只选一档：`sentence`、`10k`、`200k`；未指定时仍为 `200k`（`scripts/run_bench.py --scenario`）。
- `sentence` 的用户内容为单句中文指令，不附加 Django 切片，不附加 fixture 分隔标记；cl100k_base 计数为 61：
    - `请用中文写一篇 800 到 1200 字的短文，说明关系型数据库里的迁移解决什么问题；不要调用工具，不要读写文件，不要输出思考过程。`
- `10k` 的任务说明与 `prompts/task_200k.md` 全文一致，附加切片为 `fixtures/django_10k.txt` 全文（cl100k 为 10000，且是 `fixtures/django_200k.txt` 的字节前缀），切片不被截断。
- `200k` 保持现有任务说明、`fixtures/django_200k.txt` 与 cl100k 200000。
- 配置矩阵里的 `model` / `effort` / `source` / `harness` 格子集合不因档位增删；选中的档写入该次每条调用的 `scenario` 与对应 `cl100k_tokens`（61 / 10000 / 200000）。
- 同一次运行只产生一个 `scenario`。
- `10k` 与 `sentence` 不截断输入，也不把 `cl100k_tokens` 改写成 173218；200K 上 Kimi 超长切片截断行为不变。

## 3. 聚合与上站

- 同一份 `results.jsonl` 聚合出唯一文件 `data/latest.json`，为扁平数组，按 200k / 10k / sentence 分档块拼接。
- 每档内部按 `e2e_tps` 降序；聚合不改写 `results.jsonl`。
- 三档共用既有有效性（`status == success`、`out_tokens >= 500`、最近 2 次有效成功、中位数；无生成窗口时 `gen_tps` 为 null）。
- 账单输入中位数低于该记录 `cl100k_tokens` 的一半则不上站，等于一半上站；`200k` 记录缺 `cl100k_tokens` 时分母仍为 200000；`10k` 或 `sentence` 缺 `cl100k_tokens` 时不上站，且不得把分母当成 200000。

## 4. 非范围

- 不新增 `1k`，不实施 `100k`；不重切语料，不改 `prompts/task_200k.md` 正文；不跑实网矩阵；不渲染站点；不改 200K 上 Kimi 超长截断；不判定 800 到 1200 字；不合成总分。
