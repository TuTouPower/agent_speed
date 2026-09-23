# 基准测速与模型维护实操指南

面向运维与评测维护人员，说明在不破坏历史数据与全矩阵完整性的前提下，如何进行单模型重测、新模型热插拔、批量子集测试及数据更新。

______________________________________________________________________

## 1. 核心数据流机制

在执行任何操作前，需理解系统的双层数据流机制：

```text
[scripts/run_bench.py] ──(追加写入)──► data/results.jsonl (明细流水账)
                                              │
                                       (提取各网格最新 batch_id)
                                              ▼
[report.py]            ──(覆盖重写)──► data/latest.json (公开站上站表)
```

1. **`data/results.jsonl`（只追加不修改）**：
    - 无论全矩阵测试还是单模型测试，每次调用均作为一个独立事件追加在文件末尾；
    - 每次测速为一个网格分配唯一样本批次 `batch_id`；
    - 绝不手工删除或修改历史行。
2. **`data/latest.json`（最新批次覆盖）**：
    - `report.py` 扫描全部流水账，对每个网格单元**仅锁定最后出现的 `batch_id`**；
    - 只要某个模型重跑产生了新 batch，重新运行 `report.py` 时，该模型在 `data/latest.json` 中的指标就会自动被新批次中位数覆盖，而未重跑的模型继续沿用其各自的上一次最新批次，互不干扰。

______________________________________________________________________

## 2. 场景一：单模型重测与数据刷新

当某个模型服务商升级了模型、服务端网络恢复、或者需要重新验证某条结果时，无需全矩阵重跑。

### 操作步骤

1. **精确触发单模型测速**：
    通过 `--models` 指定模型，建议配合 `--sources` 精确限定渠道：

    ```bash
    # 仅重测 DeepSeek 官方直连组
    uv run python scripts/run_bench.py --models deepseek-v4.1-flash --sources deepseek-official

    # 仅重测 Antigravity 渠道的 Gemini
    uv run python scripts/run_bench.py --models gemini-3.8-flash --sources antigravity
    ```

2. **重新生成上站汇总表**：

    ```bash
    python report.py
    ```

### 结果效果

- `data/results.jsonl` 追加该模型对应的 3 次新调用记录（若失败则自动触发第 4 次补测）；
- `data/latest.json` 中该模型的中位数指标刷新为最新批次数据，其他模型数据完全保留，整体表格按端到端 TPS 自动重排。

______________________________________________________________________

## 3. 场景二：新模型热插拔接入与上站

当平台新增支持了新模型或新网关，按照以下三步完成即插即用接入：

### 步骤 1：在 `config/benchmark.yaml` 登记新条目

打开 `config/benchmark.yaml`，在 `cells` 数组末尾追加配置：

```yaml
  - model: "qwen-2.5-coder-32b"       # 客观标准模型名
    source: "opencode-go"             # 服务商/网关渠道标识
    harness: "opencode"               # 驱动工具（opencode/grok-build/codex/kimi-code/antigravity）
    effort: null                      # 不支持调节思考强度的模型必须显式写 null
    queue: "opencode-go"              # 物理限流并发队列
```

**配置要点**：

- **`alias`**：仅在 CLI 入参名与真实模型名不一致时填写（如 `alias: "qwen-coder-32b-exp"`），一致时严禁填写。
- **`effort`**：模型若不支持调节思考档位，必须填 `null`，严禁伪造 `high`。
- **`queue`**：若与既有服务共用账号或配额（如 Gemini 的多渠道接入），必须指定相同 `queue`。

### 步骤 2：单独执行新模型测速

```bash
uv run python scripts/run_bench.py --models qwen-2.5-coder-32b
```

调度器会自动将该任务放入对应物理队列，完成 3 次 200K 场景压测并实时入账 `data/results.jsonl`。

### 步骤 3：刷新上站表

```bash
python report.py
```

新模型只要满足上站门槛（有效次数 ≥ 2、账单输入 token ≥ 100,000），即自动插入 `data/latest.json`。

______________________________________________________________________

## 4. 场景三：三档独立评测（sentence / 10k / 200k）

一次运行只选一档，未指定时为 `200k`。同一份 `data/results.jsonl` 聚合出三份榜，互不混排，不合成总分：`data/latest.json`（只含 `200k`）、`data/latest_10k.json`（只含 `10k`）、`data/latest_sentence.json`（只含 `sentence`）。

```bash
# 一句话档（单句指令，不附加切片，cl100k_tokens 61）
uv run python scripts/run_bench.py --scenario sentence

# 10K 档（任务说明与 task_200k.md 一致，切片为 django_10k.txt 全文，cl100k_tokens 10000）
uv run python scripts/run_bench.py --scenario 10k

# 200k 档（默认，可省略）
uv run python scripts/run_bench.py --scenario 200k
```

刷新三份榜：

```bash
python report.py
```

______________________________________________________________________

## 5. 场景四：常用命令行过滤与调试组合

`scripts/run_bench.py` 支持丰富的白名单过滤与调试参数：

### 按渠道批量测试

跑完整个特定供应商（例如只测试 OpenCode-Go 网关下的全部模型）：

```bash
uv run python scripts/run_bench.py --sources opencode-go
```

### 按 Harness 框架批量测试

只测试特定工具链下的模型：

```bash
uv run python scripts/run_bench.py --harnesses antigravity
```

### 多模型联合测试

以逗号分隔指定多个模型：

```bash
uv run python scripts/run_bench.py --models mimo-v2.6-flash,deepseek-v4.1-flash
```

### 快速调试与连通性验证

通过 `--reps 1` 与短超时快速验证配置与连通性：

```bash
uv run python scripts/run_bench.py --models gemini-3.8-flash --reps 1 --timeout 60
```

______________________________________________________________________

## 6. 异常排障与脏数据处理

1. **调用过程遭遇限流或网络断开**：
    - 无需手动编辑 `data/results.jsonl` 清理脏数据；
    - 修复网络或等待限流恢复后，直接按原命令重新执行该模型测试；
    - 系统会生成全新的 `batch_id`，`report.py` 会自动跳过历史失败批次，直接采纳最新的完整批次。
2. **测试结果未进入榜单的排查检查单**：
    - **有效次数不足**：最新 batch 成功且输出 token ≥ 500 的次数是否少于 2 次？
    - **账单输入被截断**：事件流返回的 `in_tokens` 中位数是否低于该记录 `cl100k_tokens` 的一半（`200k` 为 100,000，`10k` 为 5,000，`sentence` 为 30.5，等于一半上站）？若低于门槛，契约判定为上下文严重丢失，拒绝上站。注意按档位分榜排查（`200k` 看 `data/latest.json`，`10k` 看 `data/latest_10k.json`，`sentence` 看 `data/latest_sentence.json`）。
