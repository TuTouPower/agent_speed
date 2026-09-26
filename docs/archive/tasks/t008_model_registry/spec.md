# Task spec

## 背景

测速仓要扩成 Agent 排名数据底座：速度与单价共用同一套模型身份。现有 `config/benchmark.yaml` 的 `model` 字段与 `data/latest.json` / `data/results.jsonl` 里的 `model` 已是本仓实际使用的模型 ID，但仓库没有权威模型表，无法挂「定价仓上游模型 ID」别名，也无法给后续单价产物做稳定 join。

## 契约区

### 范围

- 新增本仓权威模型表文件 `data/models.json`（覆盖写、入库跟踪）。
- 表结构：数组；每行至少一个字段 `id`（本仓模型 ID，权威主键，原样字符串，禁止大小写折叠）。可选 `pricing_aliases`：字符串数组，存定价仓 `served_model`（上游模型 ID）；与 `id` 相同可不写。第一期不写入本仓实际调用串（benchmark `alias`）。
- 行集合：至少覆盖 `config/benchmark.yaml` 的 `cells[].model` 去重全集，以及 `data/results.jsonl` 中出现过的全部 `model` 值（并集）。同一 `id` 不得重复。
- 能为已知对应关系预先写入 `pricing_aliases`：当定价仓 `served_model` 与本仓 `id` 字面相同，可不写别名；字面不同时才写别名。本 task 不猜测未知对应；对不上的留给 t009 未对齐清单驱动补录。
- 更新 `.gitignore`：在现有 `data/results.jsonl` / `data/latest.json` 例外旁，增加跟踪 `data/models.json`。
- 更新根 `AGENTS.md`「目录与读写规则」：声明 `data/models.json` 用途与写权（模型身份权威；由本 task / 后续维护更新）；并修正「`data/` 下仅跟踪 …」一句，使其包含 `models.json`。
- 短测：断言表可解析、`id` 唯一、benchmark/results 出现的 model 均在表中。

### 非范围

- 不写单价更新脚本，不生成 `pricing_latest.json` / 未对齐清单。
- 不改测速流水线、`report.py`、benchmark 格子语义、前端、外部站点仓、部署。
- 不新增单独映射表；不写展示长名、上游调用 ID、折扣感。
- 不改 `data/latest.json` / `data/results.jsonl` 内容（本 task 只读它们抽 ID）。

### 验收标准

<!-- 规范（门禁必留，不得删除） -->

只写可观察、可独立验证的行为；每条使用稳定且不复用的 `AC-NNN`。需真实部署或人工环境验证时在编号前加 `[deploy]`。技术选型不作为行为 AC。

<!-- /规范 -->

- [ ] AC-001：仓库存在可解析的 `data/models.json`，为对象数组；每行含非空字符串 `id`；可选 `pricing_aliases` 为字符串数组（可缺省或空）。
- [ ] AC-002：`data/models.json` 内全部 `id` 互不相同。
- [ ] AC-003：`config/benchmark.yaml` 的每个 `cells[].model`，以及 `data/results.jsonl` 每条记录的 `model`，都能在模型表中找到相同字面的 `id`。
- [ ] AC-004：`.gitignore` 显式取消忽略 `data/models.json`，且该文件被 git 跟踪。
- [ ] AC-005：根 `AGENTS.md` 目录表声明 `data/models.json` 为权威模型身份库，并写明 `data/` 跟踪文件包含 `models.json`。

### 可测试性声明

<!-- 规范（门禁必留，不得删除） -->

逐条说明不可自动测试的 AC 及替代验证；全部可测则写“全部 AC 可自动测试”。

<!-- /规范 -->

- 全部 AC 可自动测试。

## 上下文区

- 来源：用户确认的 Agent 排名改造方案（2026-09-26）：三表为模型表 + 测速表 + 单价表；身份靠本仓模型 ID；定价仓别名挂在模型表；无单独映射表。

### 有意不测

- 定价仓全量 `served_model` 是否都能对齐：留给 t009。
- 测速实际调用 `alias` 字段：第一期不进模型表。

### 测试策略

- 单元/契约测试读取真实或夹具 `models.json`、benchmark、假 results 行，覆盖唯一性与覆盖 AC。
- gitignore / AGENTS 用文件内容断言。

### 未知契约清单

<!-- 规范（门禁必留，不得删除） -->

未核实的外部契约标为 `UNVERIFIED-BLOCKING` 或 `UNVERIFIED-SPIKE`；核实后改写为结论和验证方式。无则写“无”。

<!-- /规范 -->

- 无。

### 风险与回退

- 风险：漏掉 results 历史 model 会导致后续单价无法覆盖旧测速行。
- 回退：删 `data/models.json` 与相关测试/文档行即可，不影响测速产物。

### 依赖与约束

- 无前置 task。t009 依赖本 task 的模型表产物。

### Finalization 时更新的 blueprint

- `docs/blueprint/architecture.md`：补充模型表在数据底座中的位置（若该文件已有可写段落；空占位则写最小条目）。
- `docs/blueprint/domain.md`：本仓模型 ID 与定价仓别名含义（同上）。
