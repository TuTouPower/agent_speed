# Task review t007（reviewer_focus: 代码）

- task：`t007_scenarios_sentence_10k`
- spec：`docs/tasks/t007_scenarios_sentence_10k/spec.md`
- diff_anchor：`b78cdd1ef4424a2778821e0775444328bb0dea41`
- target：`git -C '/Users/karson/kar/code/agent_rank_t007' diff b78cdd1ef4424a2778821e0775444328bb0dea41`
- round：1
- reviewed_at：2026-09-23 09:33 UTC+8

## Findings

无。本轮零 finding（clean review，不凑数）。

## 结论

- 落点仓库校验：`git rev-parse --show-toplevel` 输出为 `/Users/karson/kar/code/agent_rank_t007`，与 prompt 要求一致。
- 审查范围：`git diff b78cdd1ef4424a2778821e0775444328bb0dea41` 全量 diff，含 `git add -N` 后的新文件（`src/agent_rank/scenarios.py`、`tests/test_scenarios_sentence_10k.py`、`docs/specs/scenarios_sentence_10k.md`）。
- AC 覆盖（实现层）：
    - AC-001：`scenarios.SENTENCE_PROMPT` 与 spec 原句逐字一致，`SENTENCE_CL100K=61` 且 tiktoken 复验为 61；`resolve_scenario_inputs("sentence")` 返回空 fixture；`build_user_message` 空 fixture 时不附加 `CODE FIXTURE`；五类 harness 均经该 helper 组装，`apply_scenario_to_cell` 写入 `scenario=sentence`/`cl100k_tokens=61`。符合。
    - AC-002：`resolve("10k")` 返回 `task_200k.md` 全文与 `django_10k.txt` 全文，cl100k 10000；10k 切片是 200k 字节前缀已由测试断言且本地复验为 True；Kimi 截断与 agy 流水线均加 `cell.scenario == "200k"` 守卫，10k 不进入。符合。
    - AC-003：`run_bench --scenario` 缺省取配置 `scenario` 否则 `200k`；`resolve("200k")` 保持旧 prompt/切片/cl100k 200000。符合。
    - AC-004：`run_bench` 对配置 cells 统一 `apply_scenario_to_cell`，单次运行只有一个 scenario；model/effort/source/harness 集合不变（测试对比 `load_benchmark_config` 前后键集合）。符合。
    - AC-005：除 Kimi/agy 守卫外，10k（49339B）与 sentence（0B）本就低于 850KB/150KB 阈值；`cl100k_tokens` 对短档保持 10000/61，不改写 173218。符合。
    - AC-006：`generate_latest_json(..., scenario=...)` 按档过滤，`SCENARIO_BOARD_FILES` 映射三文件；`report.py` 与 `run_bench.py` 均生成三份，各自 `e2e_tps` 降序，空档写 `[]`；实现只读 results.jsonl（复验 sha 不变）。符合。
    - AC-007：`_is_valid_call` 保持 success/out>=500/wall>0；`_required_half` 取各记录自身 `cl100k_tokens` 的 max/2，200k 缺省 200000，10k/sentence 缺失返回 None 拒上站，比较用 `<`（等于一半上站）；gen 空为 null 照常上站。符合。
    - AC-008：README 含 sentence/10k/200k、各自排名、不合成总分，100k/1k 写明尚未上线。符合。
- 不偏航：改动均可追溯到 AC 或 spec Finalization 蓝图清单；未动 `prompts/task_200k.md`、切片、p002 parked 文件、200K Kimi 截断值。
- 不变量：`data/latest.json` 默认仍只含 200k（复验 18 行与主干一致）；`results.jsonl` 只追加不改写。
- 七视角体检：规格合规、正确性（含边界：空 fixture、缺 `cl100k_tokens`、bool 排除、float 兼容）、错误处理（未知 scenario 抛 ValueError）、并发（未改调度器）、安全（无外部输入拼接执行、无密钥落盘，`CallRecord.to_dict` 仍清洗 `/Users/`）、契约 Breaking（`generate_latest_json` 新增可选参默认 200k，旧单参调用仍过；CLI 新增可选参）、性能（过滤为线性扫描，无 N+1）、可维护性（`build_user_message` 收敛五处重复组装）均已扫过，无 blocking。
- 未进表的提示：无。文件行数最大 266（测试），实现最大 216，均未达过大阈值；圈复杂度无 ≥10 函数。
- 系统性 follow-up：无。

### AC 复验方式

- re_verified AC-001/AC-002：独立读 `src/agent_rank/scenarios.py`、`src/agent_rank/harness/*.py`，确认 helper 与守卫；重跑 `uv run pytest tests/test_scenarios_sentence_10k.py::test_ac001_sentence_inputs tests/test_scenarios_sentence_10k.py::test_ac002_10k_inputs -q` 通过。
- re_verified AC-003/AC-004：查 `scripts/run_bench.py --help` 含 `--scenario`；重跑 `uv run pytest tests/test_scenarios_sentence_10k.py::test_ac003_default_200k tests/test_scenarios_sentence_10k.py::test_ac004_single_scenario_per_run -q` 通过。
- re_verified AC-005：查 Kimi/agy 源码含 `cell.scenario == "200k"`；重跑对应单测通过。
- re_verified AC-006/AC-007：重跑 `uv run pytest tests/test_scenarios_sentence_10k.py::test_ac006_three_boards_split tests/test_scenarios_sentence_10k.py::test_ac006_sort_desc_within_board tests/test_scenarios_sentence_10k.py::test_ac007_billing_thresholds -q` 通过；另用真实 `data/results.jsonl` 跑 `report.py` 到 /tmp，验证 200k 18 行且 sha 不变、10k/sentence 为 `[]`。
- re_verified AC-008：读 README 相关段落，确认三档与 100k/1k 表述；重跑 `test_ac008_readme_docs` 通过。

coverage = 8 / 8

verdict: PASS

reviewed_scope: 07b020202c22033b

## Round 2 (2026-09-23 09:52 UTC+8)

- 本轮为只读指纹刷新重审，未修改任何文件。以 worktree `/Users/karson/kar/code/agent_rank_t007` 在执行 commit `f4a695e` 的完整交付为准，等价审查范围为相对 `b78cdd1ef4424a2778821e0775444328bb0dea41` 的全量 worktree 差异；本轮核验时 worktree 干净，`log` 仅含一个实现 commit。prompt 内指向主仓的 target 为渲染位置假象，本轮一律看上述 worktree diff；prompt 内旧指纹按任务指示废弃，本轮门禁值以本节末行统一锚定。
- 本轮以 `diff` 与文件直读独立查证实现层，未重跑 pytest 与实网；测试执行状态仅引用既有记录，不作为 finding 降级依据。

### 前轮 finding 复核

- 无。前轮 Round 1 为零 finding 的 clean review，本轮以 diff 为准逐项复核未发现前轮漏报或修复引入回归。

### 本轮新发现

- 无。本轮零 finding，不凑数。规格合规与七视角均已扫过，具体证据见下两节；未达到 blocking 硬阈值的观察只写入“未进表的提示”。

### 规格与七视角复验（附证据）

- AC-001：`src/agent_rank/scenarios.py:8` 原句与契约逐字一致，`:10` 为 61，`:23-27` 空 fixture 只返 prompt，`:42-43` sentence 返回空 fixture；`scripts/run_bench.py:65` sentence 档 prompt 路径为 None；五 harness 经 `build_user_message` 组装（`src/agent_rank/harness/opencode.py:42`、`codex.py:41`、`grok.py:44`、`kimi.py:39`、`antigravity.py:23`）。符合。
- AC-002：`src/agent_rank/scenarios.py:44-48` 10k 取 `task_200k.md` 全文与 `django_10k.txt` 全文，cl100k 10000；`src/agent_rank/harness/kimi.py:146-149` 与 `src/agent_rank/harness/antigravity.py:66-68` 均加 `cell.scenario == "200k"` 守卫，10k 不截断。符合。
- AC-003：`scripts/run_bench.py:48` 新增 `--scenario` 三选一，`:54-58` 缺省取配置否则 `200k` 并校验合法性；`src/agent_rank/scenarios.py:49-52` 200k 保持旧 prompt 与切片。符合。
- AC-004：`scripts/run_bench.py:83` 对全部 cells 统一 `apply_scenario_to_cell`，单次运行只有一个档；`src/agent_rank/scenarios.py:55-62` 只改写 `scenario` 与 `cl100k_tokens`，不增删格子集合。符合。
- AC-005：除上述两处守卫外，10k 与 sentence 本就低于 850KB 与 150KB 阈值；短档 `cl100k_tokens` 保持 10000 与 61，不改写 173218。符合。
- AC-006：`src/agent_rank/report.py:78-82` 定义三榜映射，`:85-89` 按档过滤（None 兼容旧调用），`:124-126` 按档分格，`:200` 档内按 `e2e_tps` 降序，`:202` 空档写 `[]` 且只读 results；`report.py:37-41` 与 `scripts/run_bench.py:141-143` 均生成三份。符合。
- AC-007：`src/agent_rank/report.py:28-36` 保持有效性定义，`:46-75` 分母取记录自身值且 bool 排除、float 兼容，200k 缺失回退 200000、短档缺失返回 None 拒上站，调用方 `:157` 用 `<` 使等于一半上站；无生成窗口时 `gen_tps` 为 None 照常上站。符合。
- AC-008：`README.md:15` 写明三档各自排名且 `100k` 与 `1k` 尚未上线，`:28` 写明档位输入规则，`:56-60` 写明分榜归属，`:127` 数据产物含三份榜，未把 `100k` 或 `1k` 写成已上线。符合。
- 不偏航与不变量：实现改动均可追溯到 AC 或 Finalization 蓝图清单；未动 `prompts/task_200k.md`、切片、`docs/pending/parked`、200K 截断值 173218、`data/results.jsonl`；`data/latest.json` 默认仍只含 200k（`src/agent_rank/report.py:88` 默认 `200k`，旧双参调用经 `_record_scenario` 回退兼容，`tests/test_report.py:103` 旧用例不受影响）。
- 安全：diff 触及路径无外部输入拼接执行、无新增网络暴露、无密钥与 PII 落盘进日志；`src/agent_rank/models.py:72-78` 路径清洗保持。
- 契约 Breaking：`generate_latest_json` 新增可选参默认 `200k`，旧调用兼容；CLI 新增可选 `--scenario`；新增榜文件经 `.gitignore:5-6` 放行。无公开签名破坏。
- 性能资源：聚合为线性扫描，无循环内查库；harness 改动仅为字符串组装与守卫判断。无 N+1 与阻塞 IO。
- 健壮性：未知档位在 `src/agent_rank/scenarios.py:39-40,57-58` 与 `scripts/run_bench.py:55-56` 抛错或退出；空 fixture、缺 `cl100k_tokens`、bool 与 float 分支均有处理。

### AC 复验方式

- re_verified AC-001：直读 `scenarios.py` 原句与空 fixture 分支，确认五 harness 经同一 helper 组装且 sentence 不附加分隔标记。
- re_verified AC-002：直读 `resolve_scenario_inputs` 10k 分支与两处 `200k` 守卫，确认切片来源与不截断语义。
- re_verified AC-003：直读 `run_bench.py` 参数与缺省逻辑，确认未指定仍为 200k。
- re_verified AC-004：直读 `apply_scenario_to_cell` 与 cells 统一改写，确认单 scenario 且格子集合不变。
- re_verified AC-005：直读 Kimi 与 agy 守卫及阈值注释，确认短档不进入截断或分块流水线。
- re_verified AC-006：直读 `report.py` 过滤、分格、排序与写盘逻辑，以及顶层 `report.py` 与 `run_bench.py` 三榜调用。
- re_verified AC-007：直读 `_is_valid_call`、`_cl100k_value`、`_required_half` 与 `<` 判定，确认等于一半上站与缺失语义。
- re_verified AC-008：直读 `README.md` 三档、分榜与 `100k` / `1k` 表述，确认与契约一致。

coverage = 8 / 8

### 未进表的提示

- 无需进表的规模提示：审查范围实现文件最大 290 行（antigravity），`scenarios.py` 63 行、`report.py` 216 行，均未达过大阈值；未发现需拆分的 ≥10 圈复杂度函数。
- 范围外观察，不进表：`src/agent_rank/report.py:207` 的 `generate_all_boards` 暂无生产调用，两处榜生成点为等价手写循环，属轻微重复但无行为分叉；预览仍只重截 200k（`report.py:43`、`scripts/run_bench.py:145`），与“不要求重截 200K 榜预览图”一致；`--prompt` / `--fixture` 手动覆盖时 `cl100k` 仍取档位值，该组合契约未定义，不出 finding。

### 总体判断

- 本轮无新增 finding，前轮零 finding 依然成立；当前交付在实现层满足 AC-001 至 AC-008，无未解决阻断项。

### 系统性 follow-up

- 无。

verdict: PASS
reviewed_scope: 8e0bddeb1df704aa
