from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import time
from datetime import datetime, timezone

from agent_rank.models import GridCell, CallRecord
from agent_rank.metrics import parse_mimo_metrics, calculate_tps
from agent_rank.harness.base import BaseHarness


# Node argv 上限：mimo CLI 是 node 脚本，整包 200K（约 972KB）走 argv 会
# RangeError 爆栈（与 Kimi d002 同类）。超限时改经 node --stack-size 直接拉起
# （已实测可过），切片不截断；小消息保持直调。
MIMO_ARGV_MAX_BYTES = 850000
MIMO_NODE_STACK_SIZE = "8192"


def _node_bin() -> str | None:
    return os.environ.get("MIMO_NODE_BIN") or shutil.which("node")


def _is_node_script(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            first_line = f.read(256).split(b"\n", 1)[0]
    except OSError:
        return False
    return first_line.startswith(b"#!") and b"node" in first_line


def _resolve_mimo_path(bin_name: str) -> str | None:
    if os.path.sep in bin_name:
        return bin_name
    return shutil.which(bin_name)


def build_mimo_cmd(
    cell: GridCell,
    prompt: str,
    fixture_content: str,
    cwd: Path | str = ".",
    bin_name: str = "mimo",
) -> list[str]:
    # 直传完整 200K 切片，避免 -f 附件的内部截断
    full_message = f"{prompt}\n\n===== CODE FIXTURE =====\n{fixture_content}" if fixture_content else prompt
    # mimo-code 支持 --variant 设置思考强度（如 high），与 opencode 调小米只走 auto 不同
    cmd = [
        bin_name,
        "run",
        "--format", "json",
        "--dir", str(cwd),
    ]
    if cell.effort:
        cmd += ["--variant", cell.effort]
    cmd += [
        "-m", cell.resolved_cli_model,
        full_message,
    ]
    if len(full_message.encode("utf-8")) > MIMO_ARGV_MAX_BYTES:
        node = _node_bin()
        mimo_path = _resolve_mimo_path(bin_name)
        if node and mimo_path and _is_node_script(mimo_path):
            stack = os.environ.get("MIMO_NODE_STACK", MIMO_NODE_STACK_SIZE)
            cmd = [node, f"--stack-size={stack}", mimo_path] + cmd[1:]
    return cmd


class MimoHarness(BaseHarness):
    def __init__(self, bin_path: str | None = None):
        self.bin_path = bin_path or os.environ.get("MIMO_BIN") or shutil.which("mimo") or "mimo"

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

        cmd = build_mimo_cmd(cell, prompt, fixture_text, cwd_path, self.bin_path)

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

        ttft, decode_window, win_source, in_toks, out_toks, used_tools = parse_mimo_metrics(lines)
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
