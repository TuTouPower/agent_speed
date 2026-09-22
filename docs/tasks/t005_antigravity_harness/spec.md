# Task spec

## 背景

参考 `call_agents/scripts` 的实现，引入 `antigravity`（CLI 为 `agy`）作为新的测试框架（harness）。支持通过 `-p` 传入 200K 评测切片与任务文本，解析 `--output-format stream-json` 输出，采集 TTFT、生成时间窗、输入输出 token，并纳入矩阵调度与 `results.jsonl` 记录。

## 契约区

### 范围

- 新增 `src/agent_speed/harness/antigravity.py`：实现 `AntigravityHarness`，调用 `agy -p <prompt> --model <model> --effort <effort> --output-format stream-json`。
- 在 `src/agent_speed/harness/__init__.py` 注册 `antigravity` 与 `agy`。
- 在 `src/agent_speed/metrics.py` 新增 `parse_antigravity_metrics(lines)`：
    - TTFT：首个 `step_update.step_type == "agent_response"` 且含 `text_delta` 的到达时刻；
    - 生成窗口：最后一个 `text_delta` 到达时刻减去 TTFT；
    - 来源：`antigravity:last_delta_minus_ttft`；
    - token counts：`usage.input_tokens` 与 `usage.output_tokens`。
- 在 `src/agent_speed/matrix.py` 增加 antigravity 模型条目（source 为 `google`，harness 为 `antigravity`）。
- 编写单测 `tests/test_antigravity_harness.py`。
- 完成真实冒烟验证。

### 非范围

- 不修改现有 opencode / grok / codex / kimi 的适配逻辑。
- 不引入外部未安装的额外二进制。

### 验收标准

<!-- 规范（门禁必留，不得删除） -->

只写可观察、可独立验证的行为；每条使用稳定且不复用的 `AC-NNN`。需真实部署或人工环境验证时在编号前加 `[deploy]`。技术选型不作为行为 AC。

<!-- /规范 -->

- [ ] AC-001：`AntigravityHarness` 成功组装并执行 `agy` 命令，通过 `-p` 传入任务文本与切片，指定 `--model`、`--effort` 与 `--output-format stream-json`。
- [ ] AC-002：`parse_antigravity_metrics` 准确解析 `stream-json` 事件流：TTFT 提取首个可见 token（含 thinking 或 text_delta）到达时刻，生成窗口提取末尾 `text_delta` 减 TTFT，账单输入与输出 token 准确从 `usage` 提取。
- [ ] AC-003：`get_harness("antigravity")` 与 `get_harness("agy")` 均正确返回 `AntigravityHarness` 实例。
- [ ] AC-004：`BENCH_MATRIX_200K` 包含 antigravity 评测格子，队列键为 `google:antigravity`。
- [ ] AC-005：真实 200K 冒烟：`agy` 成功完成一次真实调用并写入 `results.jsonl`，指标字段解析非空。

### 可测试性声明

<!-- 规范（门禁必留，不得删除） -->

逐条说明不可自动测试的 AC 及替代验证；全部可测则写“全部 AC 可自动测试”。

<!-- /规范 -->

- AC-001 ~ AC-004：全部可自动测试（fake process、样本解析、注册校验）。
- AC-005：需真实 API 调用（依赖本地 `agy` 认证），由冒烟运行验证并断言 `results.jsonl` 实际行。

## 上下文区

- 来源：用户显式指定参考 `call_agents/scripts` 接入 antigravity 支持（2026-09-22）。

### 有意不测

- agy 交互式 session / resume：评测仅测非交互 print 模式。

### 测试策略

- pytest：事件流解析单元测试、harness 命令组装测试、registry 映射测试。
- 冒烟运行：真实跑一次 `agy` 200K 并断言数据写入。

### 未知契约清单

<!-- 规范（门禁必留，不得删除） -->

未核实的外部契约标为 `UNVERIFIED-BLOCKING` 或 `UNVERIFIED-SPIKE`；核实后改写为结论和验证方式。无则写“无”。

<!-- /规范 -->

- agy 接收 ~973KB argv 的能力：已核实。实测 971,555 字节经 `-p` 传参调用成功（exit code 0，返回 1706 tokens）。

### 风险与回退

- 风险：agy 未登录或认证过期。
- 回退：未登录时报错拦截，提示用户执行 `agy` 进行交互认证。

### 依赖与约束

- 依赖本地 `/opt/homebrew/bin/agy`。

### Finalization 时更新的 blueprint

- `docs/blueprint/architecture.md`：harness 列表增加 antigravity。
- `docs/blueprint/domain.md`：harness 术语补充。
