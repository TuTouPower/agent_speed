# 架构

模型速度基准评测系统，测量主流 coding agent 及通道在真实超长上下文（200K）下的真实响应速度与吞吐（TPS）。

## 模块划分

- `config/`：集中式评测主配置文件
    - `benchmark.yaml`：定义全局并发（10）、单队列并发（2）、默认参数与 200K 全量评测网格清单。
- `src/`：核心测速与分析工具链
    - `agent_speed/`：评测驱动核心包，提供数据模型（models）、档位输入选择（scenarios：`sentence` / `10k` / `200k` 一次一档，未指定为 `200k`）、各 harness（opencode/grok-build/codex/kimi-code/antigravity）适配器、指标计算（metrics）、双层受控并发调度器（scheduler）以及报告生成模块（report：分档榜 latest_{200k,10k,sentence}.json，不合成总分）。
- `report.py`：公开报告生成脚本，读 `data/results.jsonl` 按有效次数与账单输入过滤规则计算中位数并覆盖写分档榜 `data/latest_{200k,10k,sentence}.json`。
- `scripts/`：项目构建与运行脚本。
    - `run_bench.py`：默认加载 `config/benchmark.yaml` 的双层并发基准测速驱动入口；`--scenario` 一次只选一档，选中的档写入每条调用的 `scenario` 与对应 `cl100k_tokens`。
    - `build_django_corpus.py`：公开语料构建工具，pin `django/django` tag 6.1.1，按 cl100k 组装 10K/100K/200K 嵌套切片与 manifest。
- `fixtures/`：评测输入素材与切片元数据（包含 `django_10k.txt`、`django_100k.txt`、`django_200k.txt`、对应 manifest、task 文件与 Django BSD 许可证）。
- `prompts/`：公开评测任务 prompt（`task_200k.md`）。
- `data/results.jsonl`：原始测速调用账本（追加写）。
- `data/latest_{200k,10k,sentence}.json`：公开展示站分档聚合表（覆盖写，扁平数组，行内 `scenario` 自描述）。
- `data/models.json`：本仓权威模型身份表（`id` 主键；可选 `pricing_aliases` 挂定价仓 `served_model`）；测速与单价共用同一套模型 ID。
- `scripts/update_pricing.py`：单价旁路——抓取定价仓 `adopted.csv`，按模型表精确对齐并应用硬编码覆盖，写出 `data/latest_pricing.json` / `data/unmatched_pricing.json`；**不**改测速流水线。
- `data/latest_pricing.json` / `data/unmatched_pricing.json`：单价产物与未对齐清单（覆盖写）。
- `tests/`：自动化测试套件。
- `docs/`：项目规范与知识库。
    - `docs/specs/`：生效需求级规范（语料、调度、上站报告、发布）。
    - `docs/guides/`：实操运维指南（单模型重测、新模型热插拔、批量测试）。
- `.repo_template/`：标准 Agent 开发工具链（task / pending / findings / spikes 状态机与工作流）。
