---
tid: "t004"
slug: "public_repo_release"
title: "清理、文档与公开仓：AGPL、README/AGENTS/blueprint、旧资产删除、GitHub 建仓"
status: "done"
branch: "t004_public_repo_release"
worktree: ""
review_level: "full"
review_limit: "5"
verify_limit: "5"
diff_anchor: "6894ee2e861c72dcf38ce16f374c01be6b8d93d0"
depends_on: "t001,t002,t003"
conflicts_with: ""
note: ""
---

# Task 过程总账

front matter 只经 `task.py` 修改；reviewer 只写对应 `review_*.md`。

## 实施笔记

执行期记录关键步骤、决策、验证、阻塞和用户批准的新轮次上限。

创建期不预测实施步骤。只记有追溯价值的内容；无事项时写“无”。

- 删除全部旧脚本（`src/bench_*.py`、`merge_final.py`、`rescan_stream.py`、`render_md.py`、`ts_capture.py`）、旧三档 prompts 与 `reproduce_prompt.md`。
- 根目录添加标准 AGPL-3.0 许可证 `LICENSE`，并在 `fixtures/LICENSE.django` 保留 Django 3-Clause BSD 许可证声明。
- 重写 `README.md`：包含 AGPL 许可证声明、django pin tag 说明、source+harness 分队列机制、双 TPS 指标口径及快速上手命令。
- 更新 `AGENTS.md` 目录规则表至新结构，更新 `docs/blueprint/architecture.md` 与 `domain.md`，清理所有旧资产废弃引用。
- 清理本机 `runs/` 旧跑分目录，全仓安全扫描确认无密钥与绝对路径泄露。
- 全量测试（132 contract + 16 project）全绿通过。

## Review 处置

每个结构化 finding 一行。`已修` 表示本 task 已修复；`遗留` 必须指向 `pNNN` 或 follow-up tid；`撤回` 必须写清理由。critical/important 未解决时不得 PASS。

### Round 1 (2026-09-22 14:35 UTC+8)

Round 1 零 finding。

## 收尾报告

### 验收与验证

- spec：[`spec.md`](spec.md)
- 结果：全部满足
- 测试：pytest .repo_template/tests -q -m contract (132 passed)；pytest tests -v (16 passed)
- 黑盒：未定义（blueprint/testing.md 中 blackbox_verify 声明为“无”）
- review：Round 1 PASS（review_level=full, code_verdict=PASS, test_verdict=PASS, review_scope=ok）
- AC 证据：见 `handoff.json`

### 结果摘要

- 彻底清除历史废弃代码、脚本与 prompts 资产。
- 落地 AGPL-3.0 根许可证与 Django 切片 BSD 声明。
- 全面更新 README.md、AGENTS.md、architecture.md 与 domain.md 至 200K 公开站规范架构。
- 保证测试命令可跑，工作区干净无私有材料泄露。
