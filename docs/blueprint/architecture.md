# 架构

模型速度基准评测系统，测量主流 coding agent 及通道在真实超长上下文（200K）下的真实响应速度与吞吐（TPS）。

## 模块划分

- `src/`：核心测速与分析工具链
    - `agent_speed/`：评测驱动核心包，提供数据模型（models）、各 harness（opencode/grok/codex/kimi）适配器、指标计算（metrics）、按 source+harness 分队列调度器（scheduler）以及报告生成模块（report）。
- `report.py`：公开报告生成脚本，读 `results.jsonl` 按最新 batch、有效次数与账单输入过滤规则计算中位数并覆盖写 `latest.json`。
- `scripts/`：项目构建与运行脚本。
    - `run_bench.py`：按 source+harness 分队列基准测速驱动入口。
    - `build_django_corpus.py`：公开语料构建工具，pin `django/django` tag 6.1.1，按 cl100k 组装 10K/100K/200K 嵌套切片与 manifest。
- `fixtures/`：评测输入素材与切片元数据（包含 `django_10k.txt`、`django_100k.txt`、`django_200k.txt`、对应 manifest、task 文件与 Django BSD 许可证）。
- `prompts/`：公开评测任务 prompt（`task_200k.md`）。
- `results.jsonl`：原始测速调用账本（追加写）。
- `latest.json`：公开展示站聚合汇总表（覆盖写）。
- `tests/`：自动化测试套件。
- `docs/`：项目规范与知识库。
    - `docs/specs/public_site_spec.md`：公开展示站与评测契约规范。
- `.repo_template/`：标准 Agent 开发工具链（task / pending / findings / spikes 状态机与工作流）。
