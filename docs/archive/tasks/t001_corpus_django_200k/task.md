---
tid: "t001"
slug: "corpus_django_200k"
title: "公开站语料与任务：django 6.1.1 切片（10K/100K/200K）+ 公开任务文本"
status: "done"
branch: "t001_corpus_django_200k"
worktree: ""
review_level: "single"
review_limit: "5"
verify_limit: "5"
diff_anchor: "938f3534effe9f3cc6ebe15f426ff83fae27addf"
depends_on: ""
conflicts_with: ""
note: ""
---

# Task 过程总账

front matter 只经 `task.py` 修改；reviewer 只写对应 `review_*.md`。

## 实施笔记

执行期记录关键步骤、决策、验证、阻塞和用户批准的新轮次上限。

创建期不预测实施步骤。只记有追溯价值的内容；无事项时写“无”。

- 编写 `scripts/build_django_corpus.py`：pin `django/django` tag 6.1.1 (commit `249b13d6e93ee3164dee8ed1775395622a50c337`)，收集 `django/` 与 `docs/`，排除 tests/、js_tests/、tests.py、migrations/、locale/、构建配置与二进制。
- 按 cl100k 计数精确组装 10K, 100K, 200K 三档切片与 manifest，且 10K 为 100K 字节前缀、100K 为 200K 字节前缀。
- 更新 `.gitignore` 移除对 `fixtures/input_*.txt` 的忽略，建立软链接兼容原有代码引用。
- 在 `prompts/task_200k.md` 和 `fixtures/task_200k.md` 写入评测任务文本（包含分层、模块职责、数据流、技术选型，严禁工具与读写文件）。
- 落地 `tests/test_django_corpus.py` 覆盖 AC-001 ~ AC-005。
- 根据 Round 1 review 意见修复 `tests.py` 漏排除及 commit 校验。

## Review 处置

每个结构化 finding 一行。`已修` 表示本 task 已修复；`遗留` 必须指向 `pNNN` 或 follow-up tid；`撤回` 必须写清理由。critical/important 未解决时不得 PASS。

### Round 1 (2026-09-22 13:45 UTC+8)

|finding_id|severity|status|rationale|fix_ref|
|---|---|---|---|---|
|t001_gen_f001|important|已修|过滤规则增加对 tests.py 及测试单文件的排除，重构切片|scripts/build_django_corpus.py:91|
|t001_gen_f002|important|已修|ensure_django_source 增加 git rev-parse HEAD 校验 pin commit|scripts/build_django_corpus.py:53|
|t001_gen_f003|minor|撤回|fixtures/task_200k.md 保持与 prompts 同步满足双向引用兼容|prompts/task_200k.md|
|t001_gen_f004|minor|撤回|临时路径仅为本地缓存优先探测，无则自动 clone，不破坏可移植性|scripts/build_django_corpus.py:46|
|t001_gen_f005|minor|撤回|当前切片档位最后一文件经实际断言确属截断，后续档位调整若有需要再扩展|scripts/build_django_corpus.py:170|
|t001_gen_f006|minor|撤回|testing.md 格式需与模板契约测试严格匹配，环境已有全局带 tiktoken 的 pytest|docs/blueprint/testing.md:26|

## 收尾报告

### 验收与验证

- spec：[`spec.md`](spec.md)
- 结果：全部满足
- 测试：pytest .repo_template/tests -q -m contract (132 passed)；pytest tests -q (5 passed)
- 黑盒：未定义（blueprint/testing.md 中 blackbox_verify 声明为“无”）
- review：Round 2 PASS（review_level=single, review_general.md verdict=PASS, review_scope=ok）
- AC 证据：见 `handoff.json`

### 结果摘要

- 完成 Django 6.1.1 评测切片构建脚本 `scripts/build_django_corpus.py`，排除所有测试用例、测试单文件、migrations、locale 与构建静态文件。
- 生成 10K, 100K, 200K 三档精确 cl100k token 切片与 manifest，且 10K 严格为 100K 字节前缀、100K 严格为 200K 字节前缀。
- 更新 `.gitignore` 追踪 `fixtures/input_*.txt` 并建立软链接。
- 提供中文 200K 场景架构评测任务文本 `prompts/task_200k.md`（含禁止工具与读写文件约束）。
- 落地 `tests/test_django_corpus.py` 自动化测试并通过。
