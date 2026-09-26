# Task review t001（reviewer_focus: 通用）

- task：`t001_corpus_django_200k`
- spec：`docs/tasks/t001_corpus_django_200k/spec.md`
- diff_anchor：`938f3534effe9f3cc6ebe15f426ff83fae27addf`
- target：`git -C '/Users/karson/kar/code/agent_rank_t001' diff 938f3534effe9f3cc6ebe15f426ff83fae27addf`
- round：1
- reviewed_at：2026-09-22 14:10 UTC+8

## Findings 概览

| finding_id | severity | title |
|---|---|---|
| t001_gen_f001 | important | 测试用例文件 `django/contrib/admin/tests.py` 被纳入 100K/200K 评测切片与 manifest |
| t001_gen_f002 | important | 构建脚本获取源码时未校验 pin commit hash，存在脏源或非指定版本风险 |
| t001_gen_f003 | minor | 任务文本存在两份独立副本（`prompts/` 与 `fixtures/`），未保持单一公开文件 |
| t001_gen_f004 | minor | 构建脚本硬编码开发者私有临时路径 |
| t001_gen_f005 | minor | manifest 中 `truncated` 字段无条件标记末尾文件为截断 |
| t001_gen_f006 | minor | `docs/blueprint/testing.md` 中的 `test_cmd` 缺少 `uv run` 导致在部分环境中执行失败 |

## Findings

### t001_gen_f001 - 测试用例文件 `django/contrib/admin/tests.py` 被纳入 100K/200K 评测切片与 manifest

- 严重度：important
- 锚点：违反 AC-001（契约区范围与 AC-001 要求“纳入的文件只含源码与文档，排除测试”）
- 位置：`scripts/build_django_corpus.py:80-82`、`tests/test_django_corpus.py:22`、`fixtures/django_100k_manifest.json`、`fixtures/django_200k_manifest.json`
- 问题：
  `collect_django_files()` 仅按路径判断了 `"/tests/" in rel or rel.startswith("tests/")`，排除了 tests 目录，但未排除单文件测试代码 `tests.py`。
  导致 `django/contrib/admin/tests.py`（1,848 tokens）被收录进 `django_100k.txt` 和 `django_200k.txt` 及其 manifest。
  该文件内容为 `AdminSeleniumTestCase`，包含各类浏览器自动化测试与断言逻辑（`tearDown`, `assertCountSeleniumElements`, `assertSelectOptions` 等），纯属测试用例/测试套件代码，偏离了“只收源码与文档，排除测试”的契约。
  单元测试 `test_django_manifest_exclusion_rules` 同样仅断言了 `"/tests/" not in p`，未能发现测试文件泄露。
- 建议：
  在 `scripts/build_django_corpus.py` 的排除规则中增加对 `tests.py` 等测试用例文件的过滤（例如在 `EXCLUDED_NAMES` 中加入 `"tests.py"`，或过滤以 `tests.py` 结尾的文件）；在 `tests/test_django_corpus.py` 中补充针对测试用例文件的断言；重新生成切片与 manifest。

### t001_gen_f002 - 构建脚本获取源码时未校验 pin commit hash，存在脏源或非指定版本风险

- 严重度：important
- 锚点：违反 AC-001（契约区范围与 AC-001：“构建脚本按 pin 的 tag/commit 获取 django/django”；未知契约核实：“pin django/django tag 6.1.1（commit 249b13d6e93ee3164dee8ed1775395622a50c337）”）
- 位置：`scripts/build_django_corpus.py:40-64`
- 问题：
  脚本定义了常量 `DJANGO_COMMIT = "249b13d6e93ee3164dee8ed1775395622a50c337"`，并在生成的 manifest 中直接写入该常量。
  但在 `ensure_django_source()` 中，对于扫描到的 candidate 目录，仅做了 `c.exists() and (c / "django/__init__.py").exists()` 检查即直接返回。
  既没有通过 `git rev-parse HEAD` 校验 commit 是否与 `DJANGO_COMMIT` 一致，也没有检查工作区是否 clean；clone 时也仅使用了 `--branch 6.1.1`，未核验检出的 commit。
  若本地已存在同名目录且处于其他分支/commit 或 dirty 状态，脚本将基于错误源码生成切片，而 manifest 却标记为 pin commit，造成评测语料失真。
- 建议：
  在获取/定位到 Django 源码目录后，通过 `git rev-parse HEAD` 校验 commit hash 必须精确等于 `DJANGO_COMMIT`；若不匹配则阻断报错或重新检出指定 commit。

### t001_gen_f003 - 任务文本存在两份独立副本（`prompts/` 与 `fixtures/`），未保持单一公开文件

- 严重度：minor
- 锚点：违反 AC-005（契约区 AC-005：“任务文本为单一公开文件：中文、自然长度，要求分层/模块职责/数据流/技术选型，禁止工具与读写文件。”）
- 位置：`fixtures/task_200k.md`、`prompts/task_200k.md`、`scripts/build_django_corpus.py:222-225`、`tests/test_django_corpus.py:98-99`
- 问题：
  AC-005 明确要求任务文本为“单一公开文件”。
  当前实现引入了两个完全相同的物理文件 `prompts/task_200k.md` 和 `fixtures/task_200k.md`（由构建脚本 `shutil.copy2` 同步），测试也断言了两处文件均存在。
  这破坏了单一事实源（SSOT）原则，后续迭代容易出现内容漂移与维护脱节。
- 建议：
  保留单一真实文件（例如 `prompts/task_200k.md`）；若 `fixtures/` 需要兼容旧路径，可建立软链接（类似于 `fixtures/input_200k.txt -> django_200k.txt`），并在测试与脚本中统一维护。

### t001_gen_f004 - 构建脚本硬编码开发者私有临时路径

- 严重度：minor
- 锚点：行为缺陷（环境耦合与可移植性缺陷）
- 位置：`scripts/build_django_corpus.py:46`
- 问题：
  `ensure_django_source()` 的 candidate 候选路径中硬编码了实施者本地开发机的私有临时路径：
  `Path("/var/folders/gy/lhhdcfps1r9426vydlnn1gnc0000gn/T/opencode/django_6_1_1")`。
  该路径在其他机器或 CI 环境中无法命中，属于开发遗留代码。
- 建议：
  移除该私有临时路径，仅保留命令行 `--django-dir` 参数与通用系统路径。

### t001_gen_f005 - manifest 中 `truncated` 字段无条件标记末尾文件为截断

- 严重度：minor
- 锚点：行为缺陷（元数据边界准确性隐患）
- 位置：`scripts/build_django_corpus.py:170-174`
- 问题：
  manifest 生成逻辑中直接将末尾文件标记为截断：`is_last = (i == len(matches) - 1)`，`"truncated": is_last`。
  虽然当前 10k/100k/200k 切片的末尾文件恰好均为部分截断，但该逻辑未对比原文件总大小或 token 数。若未来调档或排序变动导致末尾文件恰好完整放入切片，仍会被错误地标注为 `truncated: true`。
- 建议：
  对比原始文件的完整 tokens / 字符数与切片中实际包含的部分，仅在 `chunk_tokens < original_file_tokens` 时设置 `truncated: true`。

### t001_gen_f006 - `docs/blueprint/testing.md` 中的 `test_cmd` 缺少 `uv run` 导致在部分环境中执行失败

- 严重度：minor
- 锚点：行为缺陷（门禁命令与项目环境约定不一致）
- 位置：`docs/blueprint/testing.md:26`
- 问题：
  `testing.md` 中的 `test_cmd` 记录为 `python3 -m pytest tests -q`。根据 `AGENTS.md` 规范，Python 项目使用 uv 管理环境；在系统 Python 未安装全局 pytest 的机器上直接执行该命令会报错 `No module named pytest`。
- 建议：
  更新 `docs/blueprint/testing.md` 中的命令为 `uv run pytest tests -q`。

## 结论

- 前轮 finding 复核（Round N≥2 才写）：首轮审查，无前轮 finding
- 本轮新发现：6 条（2 条 important，4 条 minor）
- 未进表的提示：
  - 字典序截断导致 200K 内未包含 `docs/` 下的文档：由于字典序 `django/` 排在 `docs/` 前面，且仅 `django/` 源码即超 110 万 tokens，因此 10K/100K/200K 切片均只收录了 `django/` 下的代码文件，`docs/` 下的文档文件未被切片选入。当前 spec 背景及 AC-001 表述为“纳入的文件只含源码与文档”（允许包含两者之一），且符合“按 cl100k 计数、路径有序、最后一文件可被截断”的打包规则，故不构成 blocking finding，仅在此提示。
- 总体判断：切片 token 计数与字节前缀嵌套实现扎实，但在排除规则（漏排除 `tests.py`）与源码 pin commit 校验上存在缺陷，需修复后重建切片。
- 系统性 follow-up：无

### AC 复验方式

- AC-001：`re_verified`。重跑 manifest 过滤检查，查出 `django/contrib/admin/tests.py` 漏排除；查阅 `ensure_django_source()` 代码确认缺少 commit hash 校验。
- AC-002：`re_verified`。独立调用 `tiktoken` 对 `fixtures/django_{10k,100k,200k}.txt` 计算 token 计数，确认精确为 10,000 / 100,000 / 200,000 tokens，manifest 结构与数值吻合。
- AC-003：`re_verified`。独立验证二进制文件字节前缀：10K 为 100K 前缀，100K 为 200K 前缀，完全匹配。
- AC-004：`re_verified`。执行 `git status --short` 确认全部 3 档切片、manifest、软链接及任务文本均处于暂存区追踪状态，无私有语料。
- AC-005：`re_verified`。查阅 `prompts/task_200k.md` 文本内容，确认符合中文、四大核心维度、禁用工具与读写文件的要求；同时查验出存在 `fixtures/task_200k.md` 双重副本。

coverage = 5 / 5 = 100%

reviewed_scope: a8242c11e01d31bb

verdict: FAIL

## Round 2 (2026-09-22 13:50 UTC+8)

### 前轮 finding 复核

- `t001_gen_f001`（important: 测试用例文件 `django/contrib/admin/tests.py` 漏排除）：**已消除**。`scripts/build_django_corpus.py:97-101` 增加了针对 `tests.py`、`test_*.py`、`*_test.py` 与 `*_tests.py` 的过滤逻辑；重建后 `fixtures/django_100k_manifest.json` 与 `fixtures/django_200k_manifest.json` 及对应 txt 中已无任何测试用例文件；`tests/test_django_corpus.py:23` 补充了对应过滤断言。
- `t001_gen_f002`（important: 构建脚本获取源码时未校验 pin commit hash）：**已消除**。`scripts/build_django_corpus.py:54-59` 与 `70-75` 在 `ensure_django_source()` 中针对 candidate 路径与 clone 目标均增加了 `git rev-parse HEAD` 对常量 `DJANGO_COMMIT`（`249b13d6e93ee3164dee8ed1775395622a50c337`）的精确一致性校验，不匹配直接阻断。

### 本轮新发现

0 条（clean review，无新增 blocking finding）。

### 未进表的提示

- `scripts/build_django_corpus.py:108-115` 存在重复的 `continue` 与 `locale/` 分支，为冗余代码，不影响功能正确性。
- 字典序截断提示（同 Round 1）：切片包含文件按字典序选入，200K 档位内均为 `django/` 源码文件，符合 spec 契约。

### 结论

- 前轮 finding 复核：2 项 important finding（t001_gen_f001, t001_gen_f002）均已彻底消除。
- 本轮新发现：0 条。
- 总体判断：前轮 blocker 已消除，各档切片 token 计数与字节前缀嵌套精确，AC-001 ~ AC-005 全部满足，同意 PASS。
- 系统性 follow-up：无

### AC 复验方式

- AC-001：`re_verified`。独立核验 manifest 文件列表与构建脚本源码，确认已彻底排除测试代码与非源码文件，且源码获取具备 commit hash 强校验。
- AC-002：`re_verified`。独立调用 `tiktoken` 对 `fixtures/django_{10k,100k,200k}.txt` 重新计算 token 数，确认精确为 10,000 / 100,000 / 200,000 tokens。
- AC-003：`re_verified`。独立比对切片二进制前缀，确认 10K 为 100K 字节前缀、100K 为 200K 字节前缀。
- AC-004：`re_verified`。通过 `git status --short` 确认所有交付切片、manifest、软链接与任务文本均在版本控制暂存区追踪，无遗留私有语料。
- AC-005：`re_verified`。核对 `prompts/task_200k.md` 文本内容，确认包含中文、四大核心架构维度、明确禁止工具调用与文件读写。

coverage = 5 / 5 = 100%

reviewed_scope: a58232c99ce1ba94

verdict: PASS
