from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from datetime import datetime, timezone

from agent_speed.models import GridCell, CallRecord
from agent_speed.metrics import parse_grok_metrics, calculate_tps
from agent_speed.harness.base import BaseHarness


class GrokHarness(BaseHarness):
    def __init__(self, bin_path: str | None = None):
        self.bin_path = bin_path or os.environ.get("GROK_BIN") or shutil.which("grok") or "grok"

    def run(
        self,
        cell: GridCell,
        rep: int,
        batch_id: str,
        prompt: str,
        fixture_path: Path | None = None,
        fixture_text: str | None = None,
        cwd: Path | str = ".",
        timeout: int = 300,
    ) -> CallRecord:
        start_iso = datetime.now(timezone.utc).astimezone().isoformat()
        cwd_path = Path(cwd)

        if fixture_text is None:
            if fixture_path and fixture_path.exists():
                fixture_text = fixture_path.read_text(encoding="utf-8")
            else:
                fixture_text = ""

        # 构造 prompt-file
        prompt_file = cwd_path / "grok_prompt.md"
        prompt_file.write_text(
            f"{prompt}\n\n===== CODE FIXTURE =====\n{fixture_text}",
            encoding="utf-8",
        )

        cmd = [
            self.bin_path,
            "--output-format", "streaming-messages-json",
            "--include-partial-messages",
            "--tools", "",
            "--no-subagents",
            "-m", cell.resolved_cli_model,
        ]
        if cell.effort:
            cmd += ["--effort", cell.effort]
        cmd += [
            "--always-approve",
            "--cwd", str(cwd_path),
            "--prompt-file", str(prompt_file),
        ]

        t0 = time.monotonic()
        lines: list[tuple[float, str]] = []
        err_msg: str | None = None
        status = "success"

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd_path),
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

        ttft, decode_window, win_source, in_toks, out_toks, used_tools = parse_grok_metrics(lines)
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
