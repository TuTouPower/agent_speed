# Task spec

## 背景

契约要求公开仓库（AGPL）不含旧私有材料，README/AGENTS/blueprint 与实现一致，公开仓 `TuTouPower/agent_speed` 建立。当前仓库仍含旧脚本与旧文档。

## 契约区

### 范围

- 删除旧实现与旧文档（`bench_*`、`merge_final`、`rescan_stream`、`render_md`、`ts_capture`、旧三档 prompts、`reproduce_prompt.md`）。
- 本机 `runs/` 旧跑分删除。
- `LICENSE`（AGPL-3.0）；Django 切片的 BSD 声明随切片保留。
- README、`AGENTS.md`、blueprint（architecture/domain/testing）更新。
- 创建 GitHub 公开仓库并首次 push。

### 非范围

- 不写网站页面与部署脚本（页面未实现，后续 task）。

### 验收标准

<!-- 规范（门禁必留，不得删除） -->

只写可观察、可独立验证的行为；每条使用稳定且不复用的 `AC-NNN`。需真实部署或人工环境验证时在编号前加 `[deploy]`。技术选型不作为行为 AC。

<!-- /规范 -->

- [ ] AC-001：仓库不含旧脚本（`src/bench_speed.py`、`bench_stream.py`、`bench_ctx.py`、`merge_final.py`、`rescan_stream.py`、`render_md.py`、`ts_capture.py`）、旧三档 prompts、`reproduce_prompt.md`。
- [ ] AC-002：`LICENSE` 为 AGPL-3.0 全文；Django 切片的 BSD 声明随切片保留。
- [ ] AC-003：README 与新实现一致：含许可证、语料说明（django pin）、用法、结果文件（`results.jsonl`/`latest.json`）说明。
- [ ] AC-004：`AGENTS.md` 目录与读写规则表更新到新结构（`src/agent_speed/`、`tests/`、`fixtures/`、`results.jsonl`、`latest.json`）。
- [ ] AC-005：`docs/blueprint/architecture.md`、`domain.md`、`testing.md` 与实现一致，`test_cmd` 实际可跑。
- [ ] AC-006：本机 `runs/` 旧跑分删除；仓库无对旧跑分的引用。
- [ ] AC-007：[deploy] GitHub `TuTouPower/agent_speed` 公开仓库存在，`main` 与本地一致；远端无私有材料、密钥、本机绝对路径。

### 可测试性声明

<!-- 规范（门禁必留，不得删除） -->

逐条说明不可自动测试的 AC 及替代验证；全部可测则写“全部 AC 可自动测试”。

<!-- /规范 -->

- AC-001~AC-006：可本地自动检查（`git ls-files`、grep、许可文件内容、测试命令）。
- AC-007：[deploy]，需 `gh` 与用户授权；替代验证：`gh repo view` + `git ls-remote` + 远端文件抽查。

## 上下文区

- 来源：`docs/specs/public_site_spec.md` §1/§2/§11（2026-09-22 用户确认）

### 有意不测

- Cloudflare Pages 发布：页面未实现，见契约 §8，后续 task。

### 测试策略

- 全仓 grep 无密钥/绝对路径/私有材料；`git ls-files` 文件清单核对；`pytest` 跑 `test_cmd`。

### 未知契约清单

<!-- 规范（门禁必留，不得删除） -->

未核实的外部契约标为 `UNVERIFIED-BLOCKING` 或 `UNVERIFIED-SPIKE`；核实后改写为结论和验证方式。无则写“无”。

<!-- /规范 -->

- GitHub 建仓权限：已通过 `gh auth status` 核实本地已登录 `TuTouPower` 账号，拥有 repo 作用域权限。建仓时直接验证。

### 风险与回退

- 风险：本机数据删除不可逆；公开 push 泄露敏感信息。
- 回退：删除前确认无引用；push 前全仓扫描；发现泄漏立即删仓重建。

### 依赖与约束

- 依赖 t001/t002/t003。
- AC-007 为外部发布，需用户明确在场批准。

### Finalization 时更新的 blueprint

- `docs/blueprint/architecture.md`、`domain.md`、`testing.md`：本 task 内更新。
