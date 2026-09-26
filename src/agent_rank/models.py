from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class GridCell:
    scenario: str
    model: str
    effort: str | None
    source: str
    harness: str
    alias: str | None = None
    cli_model: str | None = None
    queue: str | None = None
    cl100k_tokens: int = 200000

    @property
    def queue_key(self) -> str:
        return self.queue if self.queue else f"{self.source}:{self.harness}"

    @property
    def cell_id(self) -> str:
        effort_str = self.effort if self.effort else "none"
        return f"{self.scenario}:{self.source}:{self.harness}:{self.model}:{effort_str}"

    @property
    def resolved_cli_model(self) -> str:
        return self.alias or self.cli_model or self.model

    @classmethod
    def from_dict(cls, data: dict[str, Any], default_scenario: str = "200k") -> GridCell:
        return cls(
            scenario=data.get("scenario", default_scenario),
            model=data["model"],
            effort=data.get("effort"),
            source=data["source"],
            harness=data["harness"],
            alias=data.get("alias"),
            cli_model=data.get("cli_model"),
            queue=data.get("queue"),
            cl100k_tokens=data.get("cl100k_tokens", 200000),
        )


@dataclass
class CallRecord:
    scenario: str
    model: str
    effort: str
    source: str
    harness: str
    rep: int
    batch_id: str
    start_time: str
    wall: float | None = None
    ttft: float | None = None
    decode_window: float | None = None
    out_tokens: int | None = None
    in_tokens: int | None = None
    e2e_tps: float | None = None
    gen_tps: float | None = None
    decode_window_source: str | None = None
    cl100k_tokens: int = 200000
    status: str = "success"  # "success" | "failed" | "skipped"
    used_tools: bool = False
    exclude_reason: str | None = None
    error_summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """输出符合契约 §7.1 的纯净记录字典，绝不含模型正文、密钥、本机绝对路径。"""
        # 清洗 error_summary 中可能混入的绝对路径
        safe_error = self.error_summary
        if safe_error and "/Users/" in safe_error:
            import re
            safe_error = re.sub(r"/Users/[^/\s]+/", "~/", safe_error)

        return {
            "scenario": self.scenario,
            "model": self.model,
            "effort": self.effort,
            "source": self.source,
            "harness": self.harness,
            "rep": self.rep,
            "batch_id": self.batch_id,
            "start_time": self.start_time,
            "wall": self.wall,
            "ttft": self.ttft,
            "decode_window": self.decode_window,
            "out_tokens": self.out_tokens,
            "in_tokens": self.in_tokens,
            "e2e_tps": self.e2e_tps,
            "gen_tps": self.gen_tps,
            "decode_window_source": self.decode_window_source,
            "cl100k_tokens": self.cl100k_tokens,
            "status": self.status,
            "used_tools": self.used_tools,
            "exclude_reason": self.exclude_reason,
            "error_summary": safe_error,
        }
