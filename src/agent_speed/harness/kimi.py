from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone

from agent_speed.models import GridCell, CallRecord
from agent_speed.metrics import parse_kimi_metrics, calculate_tps


def get_kimi_config_path() -> Path:
    return Path.home() / ".kimi-code" / "config.toml"


def get_kimi_global_effort() -> str:
    cfg_path = get_kimi_config_path()
    if not cfg_path.exists():
        return ""
    try:
        text = cfg_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.search(r"\[thinking\][^\[]*?effort\s*=\s*\"([^\"]+)\"", text, re.S)
    return m.group(1) if m else ""


def build_kimi_cmd(cell: GridCell, prompt: str, fixture_content: str, bin_name: str = "kimi") -> list[str]:
    full_prompt = f"{prompt}\n\n===== CODE FIXTURE =====\n{fixture_content}"
    cmd = [
        bin_name,
        "-m", cell.resolved_cli_model,
        "-p", full_prompt,
        "--output-format", "stream-json",
    ]
    return cmd


def find_latest_kimi_wire(workdir: Path | str) -> dict | None:
    """从 ~/.kimi-code/sessions/ 或 workdir 查找最新 wire.jsonl。"""
    sessions_dir = Path.home() / ".kimi-code" / "sessions"
    if not sessions_dir.exists():
        return None

    cands = []
    for s in sessions_dir.iterdir():
        if s.is_dir():
            wire = s / "agents" / "main" / "wire.jsonl"
            if wire.exists():
                cands.append(wire)

    if not cands:
        return None
    latest_wire = max(cands, key=lambda p: p.stat().st_mtime)

    # 读取统计
    tin = tou = dec = 0
    first_ttft = None
    has_tool_call = False

    try:
        for line in latest_wire.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            if not isinstance(o, dict):
                continue

            if o.get("type") in ("tool_call", "call_tool", "tool_use"):
                has_tool_call = True

            if (o.get("type") == "context.append_loop_event"
                    and isinstance(o.get("event"), dict)):
                evt = o["event"]
                if evt.get("tool_call") or evt.get("tool_name"):
                    has_tool_call = True
                if evt.get("type") == "step.end":
                    u = evt.get("usage") or {}
                    tin += u.get("inputOther", 0) + u.get("inputCacheRead", 0) + u.get("inputCacheCreation", 0)
                    tou += u.get("output", 0)
                    if evt.get("llmServerDecodeMs"):
                        dec += evt["llmServerDecodeMs"]
                    if first_ttft is None and evt.get("llmServerFirstTokenMs") is not None:
                        first_ttft = evt["llmServerFirstTokenMs"]
    except OSError:
        return None

    return {
        "llmServerDecodeMs": dec or None,
        "in_tokens": tin or None,
        "out_tokens": tou or None,
        "has_tool_call": has_tool_call,
    }


class KimiHarness:
    def __init__(self, bin_path: str | None = None):
        self.bin_path = bin_path or shutil.which("kimi") or "kimi"

    def run(
        self,
        cell: GridCell,
        rep: int,
        batch_id: str,
        prompt: str,
        fixture_text: str,
        cwd: Path | str,
        timeout: int = 300,
    ) -> CallRecord:
        start_iso = datetime.now(timezone.utc).astimezone().isoformat()
        global_effort = get_kimi_global_effort()

        # AC-005: effort 与全局配置不符的组跳过并记录原因
        if cell.effort and global_effort and cell.effort != global_effort:
            return CallRecord(
                scenario=cell.scenario,
                model=cell.model,
                effort=cell.effort,
                source=cell.source,
                harness=cell.harness,
                rep=rep,
                batch_id=batch_id,
                start_time=start_iso,
                cl100k_tokens=cell.cl100k_tokens,
                status="skipped",
                exclude_reason=f"effort mismatch: requested '{cell.effort}' != global '{global_effort}'",
            )

        cmd = build_kimi_cmd(cell, prompt, fixture_text, self.bin_path)

        t0 = time.monotonic()
        lines: list[tuple[float, str]] = []
        err_msg: str | None = None
        status = "success"

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                lines.append((round(time.monotonic() - t0, 3), line.rstrip("\n")))

            proc.wait(timeout=timeout)
            if proc.returncode != 0:
                stderr_text = proc.stderr.read() if proc.stderr else ""
                err_msg = f"exit code {proc.returncode}: {stderr_text[-300:]}"
                status = "failed"
        except subprocess.TimeoutExpired:
            proc.kill()
            err_msg = f"timeout after {timeout}s"
            status = "failed"
        except Exception as ex:
            err_msg = str(ex)
            status = "failed"

        wall = round(time.monotonic() - t0, 3)

        # wire 数据提取
        wire_info = find_latest_kimi_wire(cwd)
        if wire_info and wire_info.get("has_tool_call"):
            status = "failed"
            err_msg = "disallowed tool call detected in kimi execution"

        ttft, decode_window, win_source, in_toks, out_toks, used_tools = parse_kimi_metrics(lines, wire_info)
        e2e_tps, gen_tps = calculate_tps(wall, decode_window, out_toks)

        return CallRecord(
            scenario=cell.scenario,
            model=cell.model,
            effort=cell.effort,
            source=cell.source,
            harness=cell.harness,
            rep=rep,
            batch_id=batch_id,
            start_time=start_iso,
            wall=wall,
            ttft=ttft,
            decode_window=decode_window,
            out_tokens=out_toks,
            in_tokens=in_toks,
            e2e_tps=e2e_tps,
            gen_tps=gen_tps,
            decode_window_source=win_source,
            cl100k_tokens=cell.cl100k_tokens,
            status=status,
            used_tools=used_tools,
            error_summary=err_msg,
        )
