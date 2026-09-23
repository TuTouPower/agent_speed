"""coverage.py — 缺数据检测纯逻辑（与 report.py 同口径，不写盘）。"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any

from agent_speed.models import GridCell
from agent_speed.report import _is_valid_call, _parse_start, _record_scenario, _required_half


@dataclass
class CellCoverage:
    scenario: str
    model: str
    effort: str | None
    source: str
    harness: str
    total: int = 0
    valid: int = 0
    status: str = "missing"  # onboard | gate-blocked | thin | missing
    note: str = ""


def _norm_effort(v: Any) -> str | None:
    return v if v else None


def cell_key(scenario: str, model: str, effort: Any, source: str, harness: str) -> tuple:
    return (scenario, model, _norm_effort(effort), source, harness)


def compute_coverage(
    cells: list[GridCell],
    records: list[dict[str, Any]],
    scenario: str,
    board_rows: list[dict[str, Any]] | None = None,
) -> tuple[list[CellCoverage], list[tuple]]:
    """判定某档下每个矩阵格的数据状态，并找出榜上有但矩阵已无的行。"""
    grouped: dict[tuple, list[dict[str, Any]]] = {}
    for r in records:
        if not isinstance(r, dict):
            continue
        if _record_scenario(r) != scenario:
            continue
        key = cell_key(scenario, r.get("model", ""), r.get("effort"), r.get("source", ""), r.get("harness", ""))
        grouped.setdefault(key, []).append(r)

    matrix_keys = {cell_key(scenario, c.model, c.effort, c.source, c.harness) for c in cells}

    statuses: list[CellCoverage] = []
    for c in cells:
        key = cell_key(scenario, c.model, c.effort, c.source, c.harness)
        recs = grouped.get(key, [])
        cov = CellCoverage(scenario=scenario, model=c.model, effort=c.effort, source=c.source,
                           harness=c.harness, total=len(recs))
        valid_calls = sorted(
            (r for r in recs if _is_valid_call(r)), key=_parse_start)
        cov.valid = len(valid_calls)
        if cov.valid < 1:
            cov.status = "missing"
            fails = [r for r in recs if r.get("status") not in ("success", None)]
            if fails:
                err = fails[-1].get("error_summary") or fails[-1].get("status")
                cov.note = f"last error: {str(err)[:120]}"
        elif cov.valid < 2:
            cov.status = "thin"
        else:
            used = valid_calls[-2:]
            in_toks = [r["in_tokens"] for r in used if r.get("in_tokens") is not None]
            median_in = statistics.median(in_toks) if in_toks else 0
            required_half = _required_half(used, scenario)
            if required_half is None or median_in < required_half:
                cov.status = "gate-blocked"
                cov.note = f"in_tokens median {median_in} < gate {required_half}"
            else:
                cov.status = "onboard"
        statuses.append(cov)

    stale: list[tuple] = []
    for row in board_rows or []:
        if not isinstance(row, dict):
            continue
        key = cell_key(scenario, row.get("model", ""), row.get("effort"), row.get("source", ""), row.get("harness", ""))
        if key not in matrix_keys:
            stale.append((scenario,) + key[1:])
    return statuses, stale
