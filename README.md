# bench_speed：模型速度基准

## 当前状态

10 组 x 3 档 prompt x 3 次 = 90 次调用，默认全部并发，统计 wall 时间中位数排名。

### 口径说明

并发测的是**限流与争抢下的吞吐表现**，不是纯净单次速度；要后者用 `--workers 1`。被限流（429/timeout）的样本记失败，体现在 `n_clean` 里，不参与排名。

### 矩阵

| id | 通道 | `-m` | 强度 | 透传 |
|----|------|------|------|------|
| ds-high / ds-max | opencode | `opencode-go/deepseek-v4.1-flash` | high / max | `--variant` |
| mu-high / mu-xhigh | opencode | `opencode-go/muse-spark-1.3-contributor` | high / xhigh | `--variant` |
| gm-high | opencode | `cpa/gemini-3.8-flash` | high | `--variant` |
| g45-high | grok | `grok-4.5` | high | `--effort`（直调二进制） |
| g46-xhigh | grok | `grok-4.6` | xhigh | `--effort`（直调二进制） |
| luna-high / luna-max | codex | `gpt-5.6-luna` | high / max | `-c model_reasoning_effort`（直调，直传 max） |
| astra-high | codex | `gpt-6-astra` | high | `-c model_reasoning_effort`（直调） |

### 与 call_agents 的偏离（有意）

1. grok 不走 `call_agents.py`：`agents_lib.run_grok` 暂不支持 effort 透传，而 grok 原生支持 `--effort`/`--reasoning-effort`，故直调。
2. codex 全部直调：`call_agents` 把 `max` 全局归一为 ultra，luna 只支持到 max（`codex debug models` 实测），直传 max 才能跑。

### 官方直连行（dsoff-high/max）

key/URL 经 `OPENCODE_CONFIG` 指向临时 jsonc（`/tmp/oc_ds.jsonc`，不进仓库），跑这俩组时必须带上：

```bash
OPENCODE_CONFIG=/tmp/oc_ds.jsonc python3 bench_stream.py --only "dsoff-high:short:1,..."
```

### 用法

```bash
cd 本地私有目录
python3 bench_speed.py --list                                  # 看矩阵
python3 bench_speed.py --dry-run                               # 打印 90 个任务，不调用
python3 bench_speed.py --step0                                 # 每组 1 次最小 prompt，连通性验收
python3 bench_speed.py --smoke                                 # 第 1 组 x short x 1 次冒烟
nohup python3 bench_speed.py > runs/manual_$(date +%m%d-%H%M).log 2>&1 &   # 全量后台跑（默认 90 并发）
python3 bench_speed.py --workers 1                                   # 严格串行
python3 bench_speed.py --workers 10                                  # 限 10 并发
python3 bench_speed.py --groups ds-high,gm-high --tiers short --reps 2     # 子集
```

### 方法

- 三档 prompt 见 `prompts/`（short 问答 / medium 代码生成 / long 推理设计），全部禁工具、定输出长度，保证 tok/s 可比。
- 同一空 `work/` 目录、只读任务、timeout 600s、间隔 5s；顺序随机打乱（seed=42，可复现）。
- rep1 作 warmup：计分用 rep>1 的 clean 样本中位数；clean = 成功且输出字符数在该档守卫区间内（short 200–4000 / medium 2000–30000 / long 5000–60000）。
- overall 得分 = 三档 median 均值，越小越快。
- 结果：`runs/<stamp>/meta.json`（矩阵/顺序/二进制版本）+ `results.jsonl`（每 call 一行，实时追加，可 Ctrl-C 中断后按原命令续跑）+ `summary.json/md`。

## 待验证

- `opencode-go/muse` 的 `xhigh` variant 若被服务端忽略（等价默认），step0 文本长度会暴露，届时在 summary 标注，不重跑。
- `agents_lib.run_grok` 缺 effort 透传：上游补齐后可切回 `call_agents.py` 统一调用。
