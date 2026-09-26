# Task spec

## 背景

Agent 排名需要单价维度。上游公开仓 `FeiZhuLulu/real-api-pricing` 的采用表 `data/adopted.csv` 是来源；本仓要用模型表对齐成本仓模型 ID，并应用两条业务覆盖后写出可排序单价产物。不要「转换配置 + 转换脚本」两套东西，只要一个单价数据更新脚本：抓最新、对齐、覆盖、写出。

## 契约区

### 范围

- 新增脚本 `scripts/update_pricing.py`（可执行）：每次运行从定价仓 **最新 main** 抓取 `data/adopted.csv`（HTTPS raw 或 `git clone`/`git pull` 到本地缓存均可，须可复现说明在脚本头或仓内指南），读取本仓 `data/models.json`，写出：
    - `data/pricing_latest.json`（覆盖写、入库跟踪）
    - `data/pricing_unmatched.json`（覆盖写、入库跟踪；上游有、本仓模型表对不上的行）
- 对齐规则：对采用表每一行，取 `served_model` 为上游模型 ID；在模型表中查找 `id == served_model` 或 `served_model ∈ pricing_aliases`；命中则写入单价行，`model` 字段为本仓 `id`。禁止改写 ID、禁止大小写折叠、禁止猜测。未命中写入未对齐清单（至少含套餐名、上游 `served_model`、原因）。
- 单价行字段（键名可用英文，仓内指南用中文释义）：`plan`（套餐）、`model`（本仓模型 ID）、`source`（可空）、`billing`（订阅/按量）、`price_usd`（月费，按量可空或 0 按上游）、`monthly_tokens`、`monthly_yi`、`real_usd_per_mtok`（真实单价，排序键）、`unmetered`、`promo_until`、`confidence`、`citation`（出处，保留上游 `source` 列）、`notes`（备注，含上游 `decision_note` 与本仓覆盖说明）。
- 套餐→来源：`source` 由脚本内常量对照生成；对不上则 `source` 为空字符串或 null（二选一并在指南写明）。对照至少覆盖本仓已有测速 source 能合理对应的套餐（如 OpenCode Go → `opencode-go`）；不要求覆盖全部上游套餐。
- 覆盖规则（硬编码在脚本内；改动须写入该行 `notes`）：
    1. 套餐为 OpenCode Go，且 `served_model` 为 DeepSeek 系（`served_model` 以 `deepseek-` 开头）：将计算用的单模型月用量上限从上游隐含的 $15 改为 $60，按与上游一致的额度公式重算 `monthly_tokens` / `monthly_yi` / `real_usd_per_mtok`；月费 `price_usd` 不变。若无法从行内还原加权价，允许用「额度 × (60/原用量上限)」等比放大额度并重算真实单价，并在 `notes` 写明采用的算法。
    2. 套餐为 Command Code GOAT：月费从 10 改为 10.78；`monthly_tokens` / `monthly_yi` 不变；仅按新月费重算 `real_usd_per_mtok`；`notes` 记录覆盖。
- 更新 `.gitignore` 与 `AGENTS.md`：跟踪 `data/pricing_latest.json`、`data/pricing_unmatched.json`；声明脚本与产物写权。
- 新增仓内指南 `docs/guides/pricing_update.md`：如何运行脚本、两套覆盖含义、未对齐如何补模型表再跑、置信度来自上游。
- 试跑一次：提交当期 `pricing_latest.json` 与 `pricing_unmatched.json`。对测速仓已有模型，能对齐的应进入单价表；OpenCode DeepSeek 与 Command Code 覆盖结果可核对。
- 测速流水线（`run_bench.py` / `report.py` / results / latest*）不改行为。

### 非范围

- 不改前端、`great_websites`、Cloudflare 部署、公开站 UI。
- 不单独新增「转换配置」文件；对照与覆盖写在脚本内。
- 不输出折扣感、展示长名、分层、负载档、本币价、能力榜、上游调用 ID、单独映射表。
- 不要求把定价仓全部 266 行都对齐进本仓（未对齐进清单即可）；不强制为仅有单价、无测速的模型预建模型表行（需要时人工加）。

### 验收标准

<!-- 规范（门禁必留，不得删除） -->

只写可观察、可独立验证的行为；每条使用稳定且不复用的 `AC-NNN`。需真实部署或人工环境验证时在编号前加 `[deploy]`。技术选型不作为行为 AC。

<!-- /规范 -->

- [ ] AC-001：运行 `scripts/update_pricing.py` 后生成（或覆盖）可解析的 `data/pricing_latest.json` 与 `data/pricing_unmatched.json`；二者被 git 跟踪。
- [ ] AC-002：`pricing_latest.json` 每行含范围所列字段；`model` 等于模型表某行 `id`；可用 `real_usd_per_mtok` 数值排序。
- [ ] AC-003：对齐仅通过模型表 `id` 或 `pricing_aliases` 精确匹配 `served_model`；对大小写不同或未登记的上游模型，该行只出现在 `pricing_unmatched.json`，不出现在 `pricing_latest.json`。
- [ ] AC-004：OpenCode Go × `served_model` 以 `deepseek-` 开头的行：相对未覆盖基线，月费不变，月额度按 15→60 放大逻辑变大，`real_usd_per_mtok` 变小，且 `notes` 含覆盖说明。
- [ ] AC-005：Command Code GOAT 各行：`price_usd` 为 10.78，月额度与未覆盖基线相同，`real_usd_per_mtok` 按 10.78 重算，`notes` 含覆盖说明。
- [ ] AC-006：存在 `docs/guides/pricing_update.md`，写明运行方式、覆盖规则、未对齐补录流程。
- [ ] AC-007：根 `AGENTS.md` 声明 `scripts/update_pricing.py` 与两份定价产物的用途/写权；测速相关脚本与 `latest.json` / `results.jsonl` 行为不被本 task 改变。

### 可测试性声明

<!-- 规范（门禁必留，不得删除） -->

逐条说明不可自动测试的 AC 及替代验证；全部可测则写“全部 AC 可自动测试”。

<!-- /规范 -->

- AC-001 中「从 GitHub 拉取最新」可在测试中注入本地采用表夹具，另保留一次实网或已缓存抓取的手工/集成验证说明于指南；其余字段与覆盖用夹具自动测。
- AC-004 / AC-005：用夹具 adopted 行自动测。
- AC-006 / AC-007：文件内容断言。

## 上下文区

- 来源：用户确认的 Agent 排名改造方案（2026-09-26）；单价更新为单脚本抓最新，无独立转换配置文件。

### 有意不测

- 上游采用表未来改列名时的自动迁移。
- 网站展示与双榜 UI。

### 测试策略

- 夹具：小模型表 + 小 adopted.csv（含可对齐、不可对齐、OpenCode deepseek、Command Code）。
- 断言输出行字段、未对齐、两条覆盖数值。
- 不在单测中强依赖外网；脚本支持环境变量或参数指向本地 CSV 以便测。

### 未知契约清单

<!-- 规范（门禁必留，不得删除） -->

未核实的外部契约标为 `UNVERIFIED-BLOCKING` 或 `UNVERIFIED-SPIKE`；核实后改写为结论和验证方式。无则写“无”。

<!-- /规范 -->

- 无。

### 风险与回退

- 风险：外网不可用导致无法刷新；模型表别名不全导致大量未对齐。
- 回退：保留上一份 `pricing_*.json`；脚本可指向本地 CSV。删脚本与产物不影响测速。

### 依赖与约束

- 依赖 t008（需要 `data/models.json`）。
- 仅改测速仓；禁止改 `great_websites` 与部署配置。

### Finalization 时更新的 blueprint

- `docs/blueprint/architecture.md`：单价更新旁路与测速流水线关系。
- `docs/blueprint/decisions.md`：为何单脚本内嵌覆盖、为何不建独立映射表。
