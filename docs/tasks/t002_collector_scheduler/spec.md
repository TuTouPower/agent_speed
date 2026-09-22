# Task spec

## 背景

公开基准契约（`docs/specs/public_site_spec.md`）§4/§5/§7.1 要求：按「厂商+入口」分队列调度、每格 3 次+失败补测 1 次、只承认生成窗口、两个 TPS、`results.jsonl` 一行一次调用。现有 `src/bench_speed.py`、`bench_stream.py`、`bench_ctx.py` 口径混杂（全局并发、e2e 口径、warmup 丢弃），整体替换为统一实现。

## 契约区

### 范围

- 新包 `src/agent_speed/`：矩阵配置、通道适配（opencode/grok/codex/kimi）、单次执行与指标、队列调度器。
- 队列键 = 厂商+入口；同队列串行、队列间并行、无全局上限。
- 每格 3 次 + 失败在该队列末尾补测 1 次；`batch_id`；无 warmup。
- 指标：wall、TTFT（含思考）、生成窗口、端到端 TPS、生成 TPS、生成窗口来源；codex 生成窗口为空。
- kimi：任务+200K 切片经 `-p` argv 直传（不借工具）；effort 取全局 `~/.kimi-code/config.toml`，不匹配则跳过。
- `results.jsonl` 追加写（契约 §7.1 schema）。
- `tests/` 与 `docs/blueprint/testing.md` 的 `test_cmd`。

### 非范围

- 不生成 `latest.json`（t003）。
- 不写网站、不做发布。
- 不删旧脚本（t004）。

### 验收标准

<!-- 规范（门禁必留，不得删除） -->

只写可观察、可独立验证的行为；每条使用稳定且不复用的 `AC-NNN`。需真实部署或人工环境验证时在编号前加 `[deploy]`。技术选型不作为行为 AC。

<!-- /规范 -->

- [ ] AC-001：调度器以「厂商+入口」为队列键；同一队列内调用无时间重叠，不同队列可并行（fake 通道测试断言并发窗口；调度日志含队列键）。
- [ ] AC-002：每格 3 次调用属于同一 `batch_id`；失败调用在该队列末尾补测 1 次；无 warmup 记录；同队列同格最多 4 次。
- [ ] AC-003：生成窗口来源符合契约：opencode=文本段服务端窗、grok=末内容增量−TTFT、kimi=`llmServerDecodeMs`、codex=空。
- [ ] AC-004：TTFT 取含思考的首个可见 token；端到端 TPS=输出 token ÷ wall；生成 TPS=输出 token ÷ 生成窗口（空则空）。
- [ ] AC-005：kimi 调用经 argv 直传完整任务文本+200K 切片，事件流中无工具调用；effort 与全局配置不符的组跳过并记录原因。
- [ ] AC-006：`results.jsonl` 每次调用一行、只追加；字段全集符合契约 §7.1；不含模型正文、`events/`、密钥、本机绝对路径。
- [ ] AC-007：真实 200K 冒烟：kimi 组与 opencode 组各完成一次真实调用并写入 `results.jsonl`，指标字段非空。

### 可测试性声明

<!-- 规范（门禁必留，不得删除） -->

逐条说明不可自动测试的 AC 及替代验证；全部可测则写“全部 AC 可自动测试”。

<!-- /规范 -->

- AC-001、AC-002、AC-003（解析样本）、AC-004、AC-006：可自动测试（fake 通道、事件流样本、schema 校验）。
- AC-005：可用 fake 二进制记录 argv 验证“无工具、argv 含完整切片”；真实行为归 AC-007。
- AC-007：需真实 API 调用（网络+凭据），人工触发；以 `results.jsonl` 实际行作为证据。

## 上下文区

- 来源：`docs/specs/public_site_spec.md` §4/§5/§7.1（2026-09-22 用户确认）

### 有意不测

- 连续多次失败补测的组合：只测一处代表性路径，避免过度用例。
- opencode/grok 事件流全部变体：单测用已落盘样本与人工构造样本，不枚举。

### 测试策略

- fake channel（记录开始/结束时间与 argv）+ pytest 断言队列串行与跨队列并行。
- 事件流解析测试用 `runs/` 既有样本（只读）与人工构造样本。
- `results.jsonl` 写入用临时目录断言 schema 与追加语义。

### 未知契约清单

<!-- 规范（门禁必留，不得删除） -->

未核实的外部契约标为 `UNVERIFIED-BLOCKING` 或 `UNVERIFIED-SPIKE`；核实后改写为结论和验证方式。无则写“无”。

<!-- /规范 -->

- kimi 对约 1MB argv 的真实解析行为：`UNVERIFIED-BLOCKING`，由 AC-007 冒烟验证；失败则回报用户（kimi 退出 MVP）。
- opencode `-f` 附件是否仍有 50KB 截断：`UNVERIFIED-BLOCKING`，由 AC-007 冒烟验证。
- opencode 事件流 `reasoning` part 事件名与到达顺序：`UNVERIFIED-BLOCKING`，实现时用真实样本核对（TTFT 含思考）。

### 风险与回退

- 风险：kimi argv 余量不足（实测 996KB vs 1MB 上限）；opencode 附件截断导致账单输入不足一半。
- 回退：kimi 失败停用该组并回报；opencode 改回分块附件策略。

### 依赖与约束

- 依赖 t001 切片（真实冒烟需要 200K 切片）。
- 密钥经本机环境/`.env`（不入库）；`runs/` 本地保留。

### Finalization 时更新的 blueprint

- `docs/blueprint/architecture.md`：采集与调度模块。
- `docs/blueprint/testing.md`：`test_cmd`。
