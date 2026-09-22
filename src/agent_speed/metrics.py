from __future__ import annotations

import json
import re
from typing import Any

RE_OUT = re.compile(r'"(?:output_tokens|outputTokens|completion_tokens)"\s*:\s*(\d+)')
RE_IN = re.compile(r'"(?:input_tokens|inputTokens|prompt_tokens|promptTokens)"\s*:\s*(\d+)')
RE_REASON = re.compile(r'"reasoning(?:_tokens|Tokens)?"\s*:\s*(\d+)')


def calculate_tps(
    wall: float | None,
    decode_window: float | None,
    out_tokens: int | None,
) -> tuple[float | None, float | None]:
    """AC-004: 计算端到端 TPS 与生成 TPS。"""
    e2e_tps: float | None = None
    gen_tps: float | None = None

    if wall is not None and wall > 0 and out_tokens is not None and out_tokens > 0:
        e2e_tps = round(out_tokens / wall, 2)

    if decode_window is not None and decode_window > 0 and out_tokens is not None and out_tokens > 0:
        gen_tps = round(out_tokens / decode_window, 2)

    return e2e_tps, gen_tps


def parse_opencode_metrics(
    lines: list[tuple[float, str]],
) -> tuple[float | None, float | None, str | None, int | None, int | None, bool]:
    """opencode 指标解析。

    - TTFT: 首个可见 token（含 reasoning 与 text）到达时间
    - 生成窗口: text part 的 time.end - time.start
    - 来源: opencode:text_part_time
    - used_tools: 是否调用了工具
    """
    ttft: float | None = None
    decode_window: float | None = None
    source: str | None = None
    in_toks: int | None = None
    out_toks: int | None = None
    used_tools: bool = False

    for t, line in lines:
        try:
            o = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(o, dict):
            continue

        evt_type = o.get("type")
        part = o.get("part") if isinstance(o.get("part"), dict) else {}

        # 工具调用检测
        if evt_type in ("tool", "action", "tool_call", "call_tool") or (isinstance(part, dict) and part.get("type") in ("tool", "action")):
            used_tools = True

        # TTFT: 首个可见 token，含 reasoning 和 text
        if ttft is None:
            if evt_type in ("reasoning", "thought", "thinking"):
                ttft = t
            elif evt_type == "text" and (part.get("text") or "text" in o):
                ttft = t

        # 生成窗口: text part 的 start 到 end
        if evt_type == "text" and isinstance(part, dict):
            tm = part.get("time") or {}
            if tm.get("start") and tm.get("end") and tm["end"] > tm["start"]:
                decode_window = round((tm["end"] - tm["start"]) / 1000.0, 3)
                source = "opencode:text_part_time"

        # usage 统计
        if evt_type in ("step-finish", "step_finish"):
            toks = part.get("tokens") or {}
            if isinstance(toks, dict):
                in_toks = toks.get("input", in_toks)
                out_toks = toks.get("output", out_toks)

    # 如果 json 未能完全提取 tokens，正则兜底
    if in_toks is None or out_toks is None:
        for _, line in lines:
            m_in = RE_IN.search(line)
            if m_in and in_toks is None:
                in_toks = int(m_in.group(1))
            m_out = RE_OUT.search(line)
            if m_out and out_toks is None:
                out_toks = int(m_out.group(1))

    return ttft, decode_window, source, in_toks, out_toks, used_tools


def parse_grok_metrics(
    lines: list[tuple[float, str]],
) -> tuple[float | None, float | None, str | None, int | None, int | None, bool]:
    """grok 指标解析。

    - TTFT: 首个内容行到达时刻
    - 生成窗口: 最后一条内容增量到达时刻 - TTFT（不用 duration_api_ms）
    - 来源: grok:last_content_minus_ttft
    - used_tools: 是否调用了工具
    """
    ttft: float | None = None
    last_content_t: float | None = None
    in_toks: int | None = None
    out_toks: int | None = None
    used_tools: bool = False

    for t, line in lines:
        try:
            o = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            o = None

        is_content = False
        if isinstance(o, dict):
            # 解包 grok streaming-messages-json: type=stream_event -> event
            evt = o.get("event") if isinstance(o.get("event"), dict) else o
            evt_type = evt.get("type") or o.get("type")

            if evt_type in ("tool_use", "tool_result") or "tool_use" in line or "tool_result" in line:
                used_tools = True
            delta = evt.get("delta") if isinstance(evt.get("delta"), dict) else {}
            if delta.get("stop_reason") == "tool_use":
                used_tools = True

            if evt_type in ("content_block_delta", "content_block_start", "content", "message", "thinking", "reasoning"):
                is_content = True
            elif "delta" in evt or "delta" in o or "text" in evt or "text" in o:
                is_content = True

            usage = evt.get("usage") or o.get("usage") or {}
            if isinstance(usage, dict):
                if usage.get("prompt_tokens") is not None:
                    in_toks = usage["prompt_tokens"]
                elif usage.get("input_tokens") is not None:
                    in_toks = usage["input_tokens"]
                if usage.get("completion_tokens") is not None:
                    out_toks = usage["completion_tokens"]
                elif usage.get("output_tokens") is not None:
                    out_toks = usage["output_tokens"]
        else:
            if any(h in line for h in ('"content":', '"delta"', '"text":', '"thinking"')):
                is_content = True
            if any(h in line for h in ('"tool_use"', '"tool_result"', '"call_tool"')):
                used_tools = True

        if is_content:
            if ttft is None:
                ttft = t
            last_content_t = t

        m_in = RE_IN.search(line)
        if m_in and in_toks is None:
            in_toks = int(m_in.group(1))
        m_out = RE_OUT.search(line)
        if m_out and out_toks is None:
            out_toks = int(m_out.group(1))

    decode_window: float | None = None
    source: str | None = None
    if ttft is not None and last_content_t is not None and last_content_t >= ttft:
        decode_window = round(last_content_t - ttft, 3)
        source = "grok:last_content_minus_ttft"

    return ttft, decode_window, source, in_toks, out_toks, used_tools


def parse_kimi_metrics(
    lines: list[tuple[float, str]],
    wire_info: dict[str, Any] | None = None,
) -> tuple[float | None, float | None, str | None, int | None, int | None, bool]:
    """kimi 指标解析。

    - TTFT: 首个可见 token
    - 生成窗口: session wire.jsonl 落盘的 llmServerDecodeMs
    - 来源: kimi:llm_server_decode_ms
    - used_tools: 是否调用了工具
    """
    ttft: float | None = None
    in_toks: int | None = None
    out_toks: int | None = None
    used_tools: bool = False

    for t, line in lines:
        try:
            o = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            o = None

        if ttft is None:
            if isinstance(o, dict) and any(o.get(k) for k in ("text", "content", "delta")):
                ttft = t
            elif len(line) > 50:
                ttft = t

        m_in = RE_IN.search(line)
        if m_in and in_toks is None:
            in_toks = int(m_in.group(1))
        m_out = RE_OUT.search(line)
        if m_out and out_toks is None:
            out_toks = int(m_out.group(1))

    decode_window: float | None = None
    source: str | None = None

    if wire_info:
        if wire_info.get("llmServerDecodeMs") is not None:
            decode_window = round(wire_info["llmServerDecodeMs"] / 1000.0, 3)
            source = "kimi:llm_server_decode_ms"
        if wire_info.get("in_tokens") is not None:
            in_toks = wire_info["in_tokens"]
        if wire_info.get("out_tokens") is not None:
            out_toks = wire_info["out_tokens"]
        used_tools = bool(wire_info.get("has_tool_call", False))

    return ttft, decode_window, source, in_toks, out_toks, used_tools


def parse_codex_metrics(
    lines: list[tuple[float, str]],
) -> tuple[float | None, float | None, str | None, int | None, int | None, bool]:
    """codex 指标解析。

    - TTFT: 首个可见 token
    - 生成窗口: 契约 §5 codex 事件流没有生成窗口，字段为空
    - 来源: None
    - used_tools: 是否调用了工具
    """
    ttft: float | None = None
    in_toks: int | None = None
    out_toks: int | None = None
    used_tools: bool = False

    for t, line in lines:
        try:
            o = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            o = None

        if ttft is None:
            if isinstance(o, dict):
                evt_type = o.get("type", "")
                if evt_type in ("item.completed", "response.output_item.added", "message"):
                    ttft = t
                elif any(k in o for k in ("content", "text", "delta")):
                    ttft = t
            elif any(h in line for h in ('"item"', '"text":', '"delta"')):
                ttft = t

        if isinstance(o, dict):
            evt_type = o.get("type", "")
            if evt_type in ("function_call", "tool_call", "call_tool") or "function_call" in str(o):
                used_tools = True
            usage = o.get("usage") or {}
            if isinstance(usage, dict):
                if usage.get("input_tokens") is not None:
                    in_toks = usage["input_tokens"]
                elif usage.get("prompt_tokens") is not None:
                    in_toks = usage["prompt_tokens"]
                if usage.get("output_tokens") is not None:
                    out_toks = usage["output_tokens"]
                elif usage.get("completion_tokens") is not None:
                    out_toks = usage["completion_tokens"]

        m_in = RE_IN.search(line)
        if m_in and in_toks is None:
            in_toks = int(m_in.group(1))
        m_out = RE_OUT.search(line)
        if m_out and out_toks is None:
            out_toks = int(m_out.group(1))

    return ttft, None, None, in_toks, out_toks, used_tools


def parse_antigravity_metrics(
    lines: list[tuple[float, str]],
) -> tuple[float | None, float | None, str | None, int | None, int | None, bool]:
    """antigravity (agy stream-json) 指标解析。

    - TTFT: 首个可见 token（含 thinking 或 text_delta）到达时刻
    - 生成窗口: 最后一条 text_delta 到达时刻减去 TTFT
    - 来源: antigravity:last_delta_minus_ttft
    - used_tools: 是否调用了工具
    """
    ttft: float | None = None
    last_delta_t: float | None = None
    in_toks: int | None = None
    out_toks: int | None = None
    used_tools: bool = False

    for t, line in lines:
        try:
            o = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(o, dict):
            continue

        evt = o.get("event")
        step_update = o.get("step_update") if isinstance(o.get("step_update"), dict) else {}
        result = o.get("result") if isinstance(o.get("result"), dict) else {}

        if step_update.get("step_type") in ("tool_call", "tool_result") or "denied_actions" in o or "call_tool" in str(o):
            used_tools = True

        delta = step_update.get("text_delta")
        if delta is not None and len(delta) > 0:
            if ttft is None:
                ttft = t
            last_delta_t = t

        # 从 step_update 或 result 中提取 usage
        usage = step_update.get("usage") or result.get("usage")
        if isinstance(usage, dict):
            if usage.get("input_tokens") is not None:
                in_toks = usage["input_tokens"]
            if usage.get("output_tokens") is not None:
                out_toks = usage["output_tokens"]

    decode_window: float | None = None
    source: str | None = None
    if ttft is not None and last_delta_t is not None and last_delta_t >= ttft:
        decode_window = round(last_delta_t - ttft, 3)
        source = "antigravity:last_delta_minus_ttft"

    return ttft, decode_window, source, in_toks, out_toks, used_tools
