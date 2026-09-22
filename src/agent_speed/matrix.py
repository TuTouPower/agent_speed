from __future__ import annotations

from agent_speed.models import GridCell

# 标准 200K 评测矩阵
BENCH_MATRIX_200K = [
    # opencode-go
    GridCell(
        scenario="200k",
        model="deepseek-v4.1-flash",
        effort="high",
        source="opencode-go",
        harness="opencode",
        cli_model="opencode-go/deepseek-v4.1-flash",
    ),
    GridCell(
        scenario="200k",
        model="deepseek-v4.1-flash",
        effort="max",
        source="opencode-go",
        harness="opencode",
        cli_model="opencode-go/deepseek-v4.1-flash",
    ),
    GridCell(
        scenario="200k",
        model="muse-spark-1.3-contributor",
        effort="high",
        source="muse",
        harness="opencode",
        cli_model="opencode-go/muse-spark-1.3-contributor",
    ),
    GridCell(
        scenario="200k",
        model="mimo-v2.6-flash",
        effort="high",
        source="mimo",
        harness="opencode",
        cli_model="opencode-go/mimo-v2.6-flash",
    ),
    GridCell(
        scenario="200k",
        model="step-5-preview",
        effort="high",
        source="stepfun",
        harness="opencode",
        cli_model="stepfun/step-5-preview",
    ),
    # Gemini (cpa/)
    GridCell(
        scenario="200k",
        model="gemini-3.8-flash",
        effort="high",
        source="cpa",
        harness="opencode",
        cli_model="cpa/gemini-3.8-flash",
    ),
    # DeepSeek 官方直连 (ds-off/)
    GridCell(
        scenario="200k",
        model="deepseek-flash",
        effort="high",
        source="official",
        harness="opencode",
        cli_model="ds-off/deepseek-flash",
    ),
    # Grok
    GridCell(
        scenario="200k",
        model="grok-4.7",
        effort="xhigh",
        source="xai",
        harness="grok",
        cli_model="grok-4.7",
    ),
    # Codex
    GridCell(
        scenario="200k",
        model="gpt-5.6-luna",
        effort="high",
        source="openai",
        harness="codex",
        cli_model="gpt-5.6-luna",
    ),
    # Kimi
    GridCell(
        scenario="200k",
        model="kimi-code/k3",
        effort="max",
        source="moonshot",
        harness="kimi",
        cli_model="kimi-code/k3",
    ),
    GridCell(
        scenario="200k",
        model="kimi-code/k3",
        effort="high",
        source="moonshot",
        harness="kimi",
        cli_model="kimi-code/k3",
    ),
]
