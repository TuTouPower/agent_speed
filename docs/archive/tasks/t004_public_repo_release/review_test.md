# Test Review: t004 清理、文档与公开仓

reviewed_scope: d085715263d4e406

## 审查范围与基准

- 审查基线：`6894ee2e861c72dcf38ce16f374c01be6b8d93d0`
- 审查命令：`git -C '/Users/karson/kar/code/agent_speed_t004' diff 6894ee2e861c72dcf38ce16f374c01be6b8d93d0`
- 变更范围：
  - `AGENTS.md`（路径与读写规则更新）
  - `LICENSE`（新增 AGPL-3.0 全文）
  - `README.md`（新架构说明、调度与口径、快速上手）
  - `docs/blueprint/architecture.md` / `domain.md`（架构与领域术语对齐）
  - `docs/tasks/t004_public_repo_release/task.md`（任务状态维护）
  - `fixtures/LICENSE.django`（Django 3-Clause BSD 许可）
  - 删除旧资产：`prompts/{short,medium,long}.md`、`reproduce_prompt.md`、`src/{bench_speed,bench_stream,bench_ctx,merge_final,render_md,rescan_stream,ts_capture}.py`

## AC 自动化可测性验证 (AC-001 ~ AC-006)

1. **AC-001：旧脚本与旧 prompts 删除**：PASS
   - 自动化验证：`git ls-files` 确认 7 个旧脚本及旧三档 prompts、`reproduce_prompt.md` 已脱离版本控制；工作区文件系统无残留。
   - 可测性结论：完全可自动化验证。

2. **AC-002：开源许可证与切片第三方声明**：PASS
   - 自动化验证：`LICENSE` 为 AGPL-3.0 官方正文（660 行）；`fixtures/LICENSE.django` 独立保留 Django 3-Clause BSD 完整声明。
   - 可测性结论：完全可自动化验证。

3. **AC-003：README 与新实现一致**：PASS
   - 自动化验证：README 包含 AGPL-3.0 与 Django BSD 许可证说明、语料来源固定 pin（Django 6.1.1 `249b13d`）、切片排除规则、分队列串行调度、3+1 batch 机制、wall/TTFT/decode_window/双 TPS 口径说明、`results.jsonl` 与 `latest.json` 规则及完整快速上手步骤。
   - 可测性结论：完全可自动化验证。

4. **AC-004：AGENTS.md 读写规则表更新**：PASS
   - 自动化验证：读写规则表补充 `src/agent_speed/`、`tests/`、`scripts/`、`report.py`、`fixtures/`、`prompts/`、`results.jsonl`、`latest.json`，且已清除已废弃的旧脚本条目。
   - 可测性结论：完全可自动化验证。

5. **AC-005：Blueprint 与 test_cmd 实际可跑性**：PASS
   - 自动化验证：`architecture.md` 与 `domain.md` 已全面更新至新体系；执行测试套件：
     - 契约测试：`pytest .repo_template/tests -q -m contract` → **132 passed**
     - 项目测试：`pytest tests -q` → **16 passed**
     - 总计 **148 passed**，零 failure，零 error。
   - 可测性结论：完全可自动化验证。

6. **AC-006：本机 runs/ 删除与零引用**：PASS
   - 自动化验证：工作区 `runs/` 目录已不存在；全仓检索生产代码、测试及运行脚本均无对旧跑分产物的代码级依赖与引用。
   - 可测性结论：完全可自动化验证。

## AC-007 [deploy] 可测试性声明与验证方式披露

- **性质**：AC-007 属于带 `[deploy]` 标签的外部发布行为（在 GitHub 创建 `TuTouPower/agent_speed` 公开仓库并首次 push）。
- **可测试性声明**：`spec.md` 明确声明该 AC 需凭据与用户授权，不可完全本地自动化测试；披露了替代验证路径（`gh repo view` + `git ls-remote` + 远端抽查）。
- **安全与合规**：工作区未在未经用户明确授权前擅自进行外部建仓或远端 push；本地暂存与工作区状态干净，无密钥泄露风险。

## 危险模式扫描

- **恒真断言（Tautological Assertions）**：全仓单测逐一排查，无 `assert True`、无恒等式比较、无无意义断言，所有断言均明确校验输出内容、数值范围、集合包含关系或异常原因。
- **删断言（Deleted Assertions）**：本次 diff 未修改 `tests/` 下任何文件，无断言被删除或弱化。
- **Mock 生产逻辑（Mocking Production Logic）**：
  - `tests/test_scheduler.py` 中的 `FakeHarness` 仅用于并发调度时间戳与批次逻辑的外部 runner 模拟，未 mock 调度器及核心领域模型。
  - `tests/test_kimi_harness.py` 仅 mock 全局外部配置文件路径，生产调用逻辑完全受测。
  - 核心模块（`models`、`metrics`、`report`、`collector`、`scheduler`）均直接受测。

## 观察项 (Non-blocking)

1. `docs/blueprint/testing.md` 中 `test_cmd` 第二行写为 `python3 -m pytest tests -q`。在部分独立 pytest 环境（如 `uv tool`）下执行该行可能提示系统 python3 缺少 pytest 模块；直接使用 `pytest tests -q` 可稳定执行。建议后续统一运行命令规范。

## AC 复验方式

在工作仓库 `/Users/karson/kar/code/agent_speed_t004` 执行以下命令复验：

```bash
# 1. 验证 AC-001：旧资产全部删除
git -C '/Users/karson/kar/code/agent_speed_t004' status --porcelain | grep -E "prompts/(short|medium|long)\.md|reproduce_prompt\.md|src/(bench_|merge_final|render_md|rescan_stream|ts_capture)"

# 2. 验证 AC-002：许可证完整性
head -n 2 '/Users/karson/kar/code/agent_speed_t004/LICENSE'
head -n 1 '/Users/karson/kar/code/agent_speed_t004/fixtures/LICENSE.django'

# 3. 验证 AC-003 & AC-004：README 与 AGENTS.md 规则
grep -E "AGPL-3.0|django/django|249b13d|results.jsonl|latest.json" '/Users/karson/kar/code/agent_speed_t004/README.md'
grep -E "src/agent_speed/|report.py|results.jsonl|latest.json" '/Users/karson/kar/code/agent_speed_t004/AGENTS.md'

# 4. 验证 AC-005：测试实际可跑（契约测试 132 passed + 项目测试 16 passed）
pytest /Users/karson/kar/code/agent_speed_t004/.repo_template/tests -q -m contract
pytest /Users/karson/kar/code/agent_speed_t004/tests -q

# 5. 验证 AC-006：runs/ 目录与引用清理
test ! -d '/Users/karson/kar/code/agent_speed_t004/runs' && echo "runs directory deleted"

# 6. 验证 AC-007：[deploy] 外部发布状态
git -C '/Users/karson/kar/code/agent_speed_t004' remote -v
```

verdict: PASS
