# 公开仓库与发布规范 (Public Repo Release Spec)

## 1. 概述与目标

确立基准评测项目的开源合规基线、公开代码库治理规范、资产清理标准以及与外部展示站的数据发布契约。

## 2. 开源合规与许可证矩阵

- **核心代码库许可证**：
    仓库根目录采用 **GNU Affero General Public License v3.0 (AGPL-3.0)**（见 `LICENSE`）。所有测速驱动、调度、收集及报告生成代码均受此许可证约束。
- **语料切片许可证**：
    Django 语料切片（`fixtures/django_*.txt`）作为派生切片，严格保留上游原项目的 **3-Clause BSD License**，并在 `fixtures/LICENSE.django` 独立声明。

## 3. 仓库资产与文件治理

- **私有与过时资产清理**：
    - 彻底移除旧版混杂脚本（`bench_*`、`merge_final`、`rescan_stream` 等）及历史私有语料。
    - 不得将调试运行产物（`runs/`）及本地环境变量文件（`.env`）提交入库。
- **基线评测文件纳入**：
    - 200K 语料切片及其 manifest、评测任务 Prompt（`prompts/task_200k.md`）。
    - 原始测速明细 `results.jsonl` 与公开上站聚合数据 `latest.json`。

## 4. 文档与工程蓝图体系

- **README.md**：
    面向社区用户，明确公布：
    - 项目核心定位（真实负载下的 Agent 测速，速度不是能力排名）。
    - 双 TPS 指标（端到端 TPS 与生成 TPS）及含思考 TTFT 的测量口径。
    - 「source + harness」分队列与 3+1 Batch 机制。
    - 快速复现与评测运行命令。
- **docs/blueprint/**：
    维护项目全局技术真相：
    - `architecture.md`：核心包结构、调度器设计与模块职责。
    - `domain.md`：核心术语表与统一业务概念。
    - `testing.md`：自动化测试命令（`test_cmd`）与门禁标准。
- **AGENTS.md**：
    维护开发规范、目录读写权归属与 specs driven / TDD 原则。
