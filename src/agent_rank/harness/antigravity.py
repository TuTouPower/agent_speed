from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from datetime import datetime, timezone

from agent_rank.models import GridCell, CallRecord
from agent_rank.metrics import parse_antigravity_metrics, calculate_tps
from agent_rank.scenarios import build_user_message
from agent_rank.harness.base import BaseHarness


def build_antigravity_cmd(
    cell: GridCell,
    prompt: str,
    fixture_text: str,
    bin_name: str = "agy",
) -> list[str]:
    full_prompt = build_user_message(prompt, fixture_text)
    cmd = [
        bin_name,
        "-p", full_prompt,
        "--output-format", "stream-json",
    ]
    if cell.resolved_cli_model:
        cmd += ["--model", cell.resolved_cli_model]
    if cell.effort:
        cmd += ["--effort", cell.effort]
    return cmd


class AntigravityHarness(BaseHarness):
    def __init__(self, bin_path: str | None = None):
        self.bin_path = (
            bin_path
            or os.environ.get("ANTIGRAVITY_BIN")
            or shutil.which("agy")
            or "agy"
        )

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

        # 读取 fixture 内容
        if fixture_text is None:
            if fixture_path and fixture_path.exists():
                fixture_text = fixture_path.read_text(encoding="utf-8")
            else:
                fixture_text = ""

        # 当输入超过 150KB 时，采用方案 1（多轮对话分块累积流水线），规避 agy 单消息截断。
        # 该流水线只适用于 200k 档；10k 与 sentence 走单轮，不分块。
        if cell.scenario == "200k" and len(fixture_text.encode("utf-8")) > 150 * 1024:
            return self._run_multiturn_pipeline(
                cell=cell,
                rep=rep,
                batch_id=batch_id,
                prompt=prompt,
                fixture_text=fixture_text,
                cwd_path=cwd_path,
                start_iso=start_iso,
                timeout=timeout,
            )

        # 较小输入走单轮
        cmd = build_antigravity_cmd(cell, prompt, fixture_text, self.bin_path)

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

        ttft, decode_window, win_source, in_toks, out_toks, used_tools = parse_antigravity_metrics(lines)
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

    def _run_multiturn_pipeline(
        self,
        cell: GridCell,
        rep: int,
        batch_id: str,
        prompt: str,
        fixture_text: str,
        cwd_path: Path,
        start_iso: str,
        timeout: int,
    ) -> CallRecord:
        """方案 1: 多轮对话分块累积法。前 3 轮各灌入 1/4 切片仅回复 OK，第 4 轮灌入最后 1/4 并正式测速。"""
        total_len = len(fixture_text)
        num_chunks = 4
        step = total_len // num_chunks
        chunks = [
            fixture_text[i * step : (i + 1) * step if i < num_chunks - 1 else total_len]
            for i in range(num_chunks)
        ]

        conv_id: str | None = None

        # 执行前置灌入轮 (Turn 1 ~ 3)
        for turn_idx in range(1, 4):
            ch = chunks[turn_idx - 1]
            turn_msg = f"这是代码切片第 {turn_idx}/4 部分，仅作上下文灌入。严格只回复两个字符：OK。严禁输出任何分析、解释或标点。\n\n{ch}"
            cmd = [
                self.bin_path,
                "-p", turn_msg,
                "--output-format", "json",
            ]
            if cell.resolved_cli_model:
                cmd += ["--model", cell.resolved_cli_model]
            if conv_id:
                cmd += ["--conversation", conv_id]

            try:
                res = subprocess.run(cmd, cwd=str(cwd_path), capture_output=True, text=True, timeout=60)
                if res.returncode != 0:
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
                        status="failed",
                        used_tools=False,
                        error_summary=f"Turn {turn_idx} prep failed (exit {res.returncode}): {res.stderr[-200:]}",
                    )
                data = json.loads(res.stdout)
                if not conv_id:
                    conv_id = data.get("conversation_id")
            except Exception as ex:
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
                    status="failed",
                    used_tools=False,
                    error_summary=f"Turn {turn_idx} exception: {str(ex)}",
                )

        # 第 4 轮：正式基准测速轮 (Turn 4)
        ch_final = chunks[3]
        final_msg = (
            f"这是代码切片第 4/4 部分。\n\n{ch_final}\n\n"
            f"现在请结合上面接收到的全部 4 个部分的完整代码展开分析。\n\n{prompt}"
        )

        final_cmd = [
            self.bin_path,
            "-p", final_msg,
            "--output-format", "stream-json",
        ]
        if cell.resolved_cli_model:
            final_cmd += ["--model", cell.resolved_cli_model]
        if cell.effort:
            final_cmd += ["--effort", cell.effort]
        if conv_id:
            final_cmd += ["--conversation", conv_id]

        t0 = time.monotonic()
        lines: list[tuple[float, str]] = []
        err_msg: str | None = None
        status = "success"

        try:
            proc = subprocess.Popen(
                final_cmd,
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
                err_msg = f"Final turn exit code {proc.returncode}: {stderr_text[-300:]}"
                status = "failed"
        except subprocess.TimeoutExpired:
            proc.kill()
            err_msg = f"Final turn timeout after {timeout}s"
            status = "failed"
        except Exception as ex:
            err_msg = f"Final turn exception: {str(ex)}"
            status = "failed"

        wall = round(time.monotonic() - t0, 3)

        ttft, decode_window, win_source, in_toks, out_toks, used_tools = parse_antigravity_metrics(lines)
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
