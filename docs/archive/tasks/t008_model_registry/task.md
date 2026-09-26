---
tid: "t008"
slug: "model_registry"
title: "建立本仓模型表（权威 ID + 定价仓别名）"
status: "done"
branch: "t008_model_registry"
worktree: ""
review_level: "single"
review_limit: "5"
verify_limit: "5"
diff_anchor: "6944aea3cb5767e5984935859a748d7cbda39273"
depends_on: ""
conflicts_with: ""
note: "Agent 排名数据底座：模型身份唯一库"
---

# Task 过程总账

front matter 只经 `task.py` 修改；reviewer 只写对应 `review_*.md`。

## 实施笔记

执行期记录关键步骤、决策、验证、阻塞和用户批准的新轮次上限。

创建期不预测实施步骤。只记有追溯价值的内容；无事项时写“无”。

- 并集 ID 来自 `config/benchmark.yaml` cells[].model 与 `data/results.jsonl` model（17 个）。
- 已知别名仅 `MiniMax-M3` → `minimax-m3`（大小写不同）；其余字面相同或不猜测。
- 黑盒：`testing.md` blackbox_verify 正文为「无」，记录为未定义。
- attempt=1 execution_id=ec6fad32cd2845b1837256b4c235e652

## Review 处置

每个结构化 finding 一行。`已修` 表示本 task 已修复；`遗留` 必须指向 `pNNN` 或 follow-up tid；`撤回` 必须写清理由。critical/important 未解决时不得 PASS。

### Round 1 (2026-09-26 08:56 UTC+8)

Round 1 零 finding。

## 收尾报告

### 验收与验证

- spec：[`spec.md`](spec.md)
- 结果：全部满足
- 测试：`pytest tests -q` 62 passed；`pytest .repo_template/tests -q -m contract` 132 passed
- 黑盒：未定义（`docs/blueprint/testing.md` blackbox_verify 正文为「无」）
- review：Round 1 PASS（single / review_general.md，零 finding，scope de99157a4992d7e3）
- AC 证据：见 `handoff.json`

### 结果摘要

- 新增 `data/models.json`（17 行）与契约测试；更新 `.gitignore` / `AGENTS.md` / blueprint 最小条目。遗留无。
