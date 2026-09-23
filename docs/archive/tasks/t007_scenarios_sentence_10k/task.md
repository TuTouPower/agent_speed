---
tid: "t007"
slug: "scenarios_sentence_10k"
title: "新增一句话与 10K 两个独立评测档"
status: "done"
branch: "t007_scenarios_sentence_10k"
worktree: ""
review_level: "full"
review_limit: "5"
verify_limit: "5"
diff_anchor: "b78cdd1ef4424a2778821e0775444328bb0dea41"
depends_on: ""
conflicts_with: ""
note: "来源 p002 的一句话与 10K；100K 仍 parked，不归档 p002"
---

# Task 过程总账

front matter 只经 `task.py` 修改；reviewer 只写对应 `review_*.md`。

## 实施笔记

执行期记录关键步骤、决策、验证、阻塞和用户批准的新轮次上限。

创建期不预测实施步骤。只记有追溯价值的内容；无事项时写“无”。

- preflight `task.py preflight t007 --require-verified` 严格 PASS 后实施；未知契约为无。
- TDD 先红后绿：新增 `tests/test_scenarios_sentence_10k.py` 10 用例初跑 10 红，实现后 10 绿；旧测试零改动。
- 新增 `src/agent_speed/scenarios.py` 收敛档位常量与输入选择（sentence 单句 61、10k 全文 10000、200k 保持）；五 harness 经 `build_user_message` 组装，空 fixture 不附加分隔标记；Kimi 850KB 截断与 agy 150KB 流水线加 `scenario == "200k"` 守卫。
- `src/agent_speed/report.py` 加 `scenario` 过滤与 `_required_half`（200k 缺省 200000，10k/sentence 缺失不上站，等于一半上站）；`scripts/run_bench.py` 加 `--scenario`（一次一档，缺省 200k）并生成三榜；`report.py` 生成三份榜。
- `.gitignore` 放行 `latest_10k.json` / `latest_sentence.json`；README、guides、domain/architecture/decisions、specs/specs_index 同步三档分榜。
- 验证：`uv run pytest tests -q` 32 passed；`pytest .repo_template/tests -q -m contract` 132 passed；`git diff --check` 干净；真实 `results.jsonl` 重聚验证 200k 18 行不变、10k/sentence 为 `[]`、sha 不变；黑盒未定义（见收尾）。
- 阻塞：无；未动 p002 parked；无跨 task 修复。

## Review 处置

每个结构化 finding 一行。`已修` 表示本 task 已修复；`遗留` 必须指向 `pNNN` 或 follow-up tid；`撤回` 必须写清理由。critical/important 未解决时不得 PASS。

### Round 1 (2026-09-23 09:33 UTC+8)

Round 1 零 finding（`review_code.md` / `review_test.md` 均为 PASS，无 finding）。

### Round 2 (2026-09-23 09:55 UTC+8，指纹刷新重审)

Round 1 出报告后交付内容有变化未重审，指纹失配致 cleanup 门禁拦截（reported_uncleaned）。经用户批准手动修复：独立 reviewer 对最终 tip 内容只读重审，双轴均为 PASS、零 finding，`reviewed_scope` 刷新为 8e0bddeb1df704aa；本次只改过程文件（review 报告/handoff/本表），交付指纹不变。模板工具链缺口已另行上报（`.scratch/repo_template_issues/20260923-094458.md`，未入库）。

## 收尾报告

### 验收与验证

- spec：[`spec.md`](spec.md)
- 结果：全部满足
- 测试：`uv run pytest tests -q` 32 passed；`pytest .repo_template/tests -q -m contract` 132 passed
- 黑盒：未定义（`docs/blueprint/testing.md` `blackbox_verify` 章节正文为「无」）
- review：full 双轴 Round 1 PASS 后指纹失配，Round 2 对最终内容重审双 PASS，`reviewed_scope`=8e0bddeb1df704aa
- AC 证据：见 `handoff.json`

### 结果摘要

- 新增 sentence/10k 独立档与三份分榜，200K 行为不变；遗留无；pending/finding 无新增（p002 仍 parked）。
