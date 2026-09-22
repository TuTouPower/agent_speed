# 架构

模型速度基准评测系统，测量主流 coding agent 及通道在多档位 prompt 及超长上下文（如 300K）下的真实响应速度与吞吐（TPS）。

## 模块划分

- `src/`：核心测速与分析工具链
    - `agent_speed/`：重构的评测驱动核心包，提供数据模型、各 harness（opencode/grok/codex/kimi）适配器、指标计算、按 source+harness 分队列调度器以及报告生成模块。
    - `report.py`：公开报告生成脚本，读 `results.jsonl` 按最新 batch、有效次数与账单输入过滤规则计算中位数并覆盖写 `latest.json`。
    - `bench_speed.py`：常规三档（short/medium/long）矩阵测速驱动器，支持并发/串行、样本过滤与中位数统计。
    - `bench_ctx.py`：300K 长上下文输入基准评测，测量首 token 延迟（TTFT）与解码 TPS。
    - `bench_stream.py`：流式捕获与事件记录驱动（支持 opencode / codex / grok 等直调）。
    - `render_md.py`：基准结果 Markdown 转高分辨率 Retina 图片渲染器。
    - `build_fixture.py`：超长输入切片构建工具（生成 `fixtures/chunks_300k/`）。
    - `merge_final.py` / `rescan_stream.py` / `ts_capture.py`：历史数据重扫与合并工具。
- `scripts/`：项目构建与工具脚本。
    - `run_bench.py`：按 source+harness 分队列基准测速驱动入口。
    - `build_django_corpus.py`：公开语料构建工具，pin `django/django` tag 6.1.1，按 cl100k 组装 10K/100K/200K 嵌套切片与 manifest。
- `fixtures/`：评测输入素材与元数据（包含 `django_10k.txt`、`django_100k.txt`、`django_200k.txt` 及对应 manifest 与 task 文件）。
- `prompts/`：标准评测 prompt 集（`short.md`、`medium.md`、`long.md`、`task_200k.md`）。
- `runs/`：每次运行产物（`meta.json`、`results.jsonl`、`summary.md` 等，本地保留，不入库）。
- `docs/`：项目规范与知识库。
    - `docs/specs/public_site_spec.md`：未来公开展示站（Cloudflare Pages 静态站 + `django/django` 切片语料）设计契约（待拆分 task 实现）。
- `.repo_template/`：标准 Agent 开发工具链（task / pending / findings / spikes 状态机与工作流）。
