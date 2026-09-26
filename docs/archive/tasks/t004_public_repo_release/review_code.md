# Code Review: t004 清理、文档与公开仓

reviewed_scope: d085715263d4e406

## 审查范围

- 比较基线：`6894ee2e861c72dcf38ce16f374c01be6b8d93d0`
- 审查命令：`git -C '/Users/karson/kar/code/agent_rank_t004' diff 6894ee2e861c72dcf38ce16f374c01be6b8d93d0`
- 审查文件：
  - `AGENTS.md`
  - `LICENSE`
  - `README.md`
  - `docs/blueprint/architecture.md`
  - `docs/blueprint/domain.md`
  - `docs/tasks/t004_public_repo_release/task.md`
  - `fixtures/LICENSE.django`
  - 删除旧文件：`prompts/{short,medium,long}.md`、`reproduce_prompt.md`、`src/{bench_speed,bench_stream,bench_ctx,merge_final,render_md,rescan_stream,ts_capture}.py`

## 契约核验 (AC-001 ~ AC-007)

1. **AC-001 (旧脚本与旧 prompts 删除)**: PASS
   - 7 个旧脚本（`src/bench_speed.py`、`bench_stream.py`、`bench_ctx.py`、`merge_final.py`、`rescan_stream.py`、`render_md.py`、`ts_capture.py`）已全部删除。
   - 旧三档 prompts（`prompts/short.md`、`prompts/medium.md`、`prompts/long.md`）与 `reproduce_prompt.md` 已全部删除。
   - 仅保留 200K 超长上下文公开评测任务 `prompts/task_200k.md`。

2. **AC-002 (开源许可证与第三方声明)**: PASS
   - 根目录新增 `LICENSE`，为 GNU AGPL-3.0 官方全文（660 行）。
   - `fixtures/LICENSE.django` 独立保留 Django 3-Clause BSD License 原文，归属 Django Software Foundation 及其贡献者。

3. **AC-003 (README 与新架构对齐)**: PASS
   - 包含 AGPL-3.0 与 Django BSD 许可证说明。
   - 完整披露语料来源（固定 pin Django 6.1.1，commit `249b13d`）、切片排除规则与 `prompts/task_200k.md`。
   - 说明按 source+harness 分队列调度机制、3+1 batch 与 wall / TTFT / decode window / 两个 TPS 口径。
   - 说明 `results.jsonl`（脱敏、不存回答正文）与 `latest.json`（最新 batch、>=2 次有效、输入 token 半数门槛、端到端 TPS 降序）。
   - 快速上手步骤涵盖语料构建、评测调度、报告汇总与 pytest 测试。

4. **AC-004 (AGENTS.md 读写规则更新)**: PASS
   - 读写规则表补充 `src/agent_rank/`、`tests/`、`scripts/`、`report.py`、`fixtures/`、`prompts/`、`results.jsonl`、`latest.json`。
   - 明确各文件写权归属与职责范围，移除旧资产条目。

5. **AC-005 (Blueprint 架构与领域模型更新)**: PASS
   - `architecture.md` 移除旧 300K / 短中长三档脚本描述，更新为 `agent_rank/` 驱动核心与新脚本入口。
   - `domain.md` 统一定义比较单位、Source、Harness、Reasoning Effort、Queue Key、3+1 Batch、Wall、TTFT、Decode Window、双 TPS、Corpus Slice、Billed Input Tokens、Latest Report 等核心领域术语。
   - 架构与领域定义与当前代码实现完全一致。

6. **AC-006 (本机 runs/ 清理与零引用)**: PASS
   - 本机 `runs/` 目录已删除。
   - 全仓检索除历史归档（`docs/archive/`）和规范声明（`AGENTS.md`、`.gitignore`）外，无对旧跑分产物与旧脚本的引用。

7. **AC-007 ([deploy] 外部公开仓待批准状态披露)**: PASS
   - 外部 GitHub 仓库创建与首次推送需凭据与用户现场授权，属于 `[deploy]` 门禁。
   - 合并前保持待部署状态，远端无未受控推送，符合部署与发布安全规范。

## 观察项 (Non-blocking)

1. `src/build_fixture.py` 遗留：为旧 300K 切片构建工具，全仓无引用且已在 `architecture.md` 剔除，建议后续清理删除。
2. `docs/blueprint/testing.md` 中 `test_cmd` 第二行使用 `python3 -m pytest tests -q`，若采用独立 pytest 环境（如 `uv tool`）会因 python3 模块缺失报错；可与第一行保持一致使用 `pytest tests -q`。

## AC 复验方式

在工作仓库 `/Users/karson/kar/code/agent_rank_t004` 下执行以下命令复验：

1. **AC-001：旧脚本与旧 prompts 删除复验**
   ```bash
   git -C '/Users/karson/kar/code/agent_rank_t004' status --porcelain | grep -E "prompts/(short|medium|long)\.md|reproduce_prompt\.md|src/(bench_|merge_final|render_md|rescan_stream|ts_capture)"
   ```
   预期输出：所有对应项状态为 ` D`（已删除）。

2. **AC-002：许可证全文复验**
   ```bash
   head -n 2 '/Users/karson/kar/code/agent_rank_t004/LICENSE'
   head -n 1 '/Users/karson/kar/code/agent_rank_t004/fixtures/LICENSE.django'
   ```
   预期输出：`GNU AFFERO GENERAL PUBLIC LICENSE` 与 `Copyright (c) Django Software Foundation and individual contributors.`。

3. **AC-003 & AC-004：README 与 AGENTS.md 新结构检查**
   ```bash
   grep -E "AGPL-3.0|django/django|249b13d|results.jsonl|latest.json" '/Users/karson/kar/code/agent_rank_t004/README.md'
   grep -E "src/agent_rank/|report.py|results.jsonl|latest.json" '/Users/karson/kar/code/agent_rank_t004/AGENTS.md'
   ```
   预期输出：均匹配新架构与路径规则。

4. **AC-005：Blueprint 与单测验证**
   ```bash
   pytest /Users/karson/kar/code/agent_rank_t004/.repo_template/tests -q -m contract
   pytest /Users/karson/kar/code/agent_rank_t004/tests -q
   ```
   预期输出：132 passed、16 passed。

5. **AC-006：runs 目录与旧引用清理检查**
   ```bash
   test ! -d '/Users/karson/kar/code/agent_rank_t004/runs' && echo "runs directory deleted"
   ```
   预期输出：`runs directory deleted`。

6. **AC-007：[deploy] 外部仓状态复验**
   ```bash
   git -C '/Users/karson/kar/code/agent_rank_t004' remote -v
   ```
   预期输出：无未受权远端配置，符合待部署状态披露。

verdict: PASS
