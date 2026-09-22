from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import statistics
from typing import Any


def calculate_median(values: list[float | int]) -> float | None:
    if not values:
        return None
    val = statistics.median(values)
    return round(float(val), 2)


def generate_latest_json(
    results_jsonl: Path | str,
    output_json: Path | str,
) -> list[dict[str, Any]]:
    """读 results.jsonl 重新生成 latest.json。

    - 每个格子只取最新 batch_id；
    - 最新 batch 有效次数 < 2 的格子不上站；
    - 输出 token < 500 或失败的调用无效；
    - 对方账单输入 token < 切片 cl100k 一半的格子不上站；
    - codex 等无生成窗口的格子照常上站，生成 TPS 为 None；
    - 中位数由有效次数计算；
    - 按端到端 TPS 降序覆盖写 latest.json。
    """
    jsonl_path = Path(results_jsonl)
    out_path = Path(output_json)

    if not jsonl_path.exists():
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("[]\n", encoding="utf-8")
        return []

    # 收集全部调用记录并按格子分组
    # grid_key = (scenario, model, effort, source, harness)
    grid_records: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue

            grid_key = (
                rec.get("scenario", ""),
                rec.get("model", ""),
                rec.get("effort", ""),
                rec.get("source", ""),
                rec.get("harness", ""),
            )
            grid_records[grid_key].append(rec)

    now_iso = datetime.now(timezone.utc).astimezone().isoformat()
    rows: list[dict[str, Any]] = []

    for (scenario, model, effort, source, harness), records in grid_records.items():
        if not records:
            continue

        # AC-001: 每个格子只取最新 batch_id
        # records 按出现顺序，最后出现的即为最新 batch
        latest_batch_id = records[-1].get("batch_id")
        batch_records = [r for r in records if r.get("batch_id") == latest_batch_id]

        # AC-003: 过滤有效调用 (status==success, out_tokens >= 500)
        valid_calls = []
        for r in batch_records:
            if r.get("status") != "success":
                continue
            out_toks = r.get("out_tokens")
            if out_toks is None or out_toks < 500:
                continue
            if r.get("wall") is None or r.get("wall", 0) <= 0:
                continue
            valid_calls.append(r)

        # AC-002: 最新 batch 有效次数 < 2 则不上站
        if len(valid_calls) < 2:
            continue

        # 计算账单输入中位数
        in_toks_list = [r["in_tokens"] for r in valid_calls if r.get("in_tokens") is not None]
        in_toks_median = statistics.median(in_toks_list) if in_toks_list else 0

        # AC-004: 对方账单输入 token < 切片 cl100k 一半不上站
        cl100k = valid_calls[0].get("cl100k_tokens") or 200000
        if in_toks_median < (cl100k / 2.0):
            continue

        # 计算各项中位数 (AC-007: 仅由有效次数计算)
        e2e_list = [r["e2e_tps"] for r in valid_calls if r.get("e2e_tps") is not None]
        e2e_median = round(float(statistics.median(e2e_list)), 2) if e2e_list else 0.0

        gen_list = [r["gen_tps"] for r in valid_calls if r.get("gen_tps") is not None]
        gen_median = round(float(statistics.median(gen_list)), 2) if gen_list else None

        ttft_list = [r["ttft"] for r in valid_calls if r.get("ttft") is not None]
        ttft_median = round(float(statistics.median(ttft_list)), 3) if ttft_list else None

        out_toks_list = [r["out_tokens"] for r in valid_calls if r.get("out_tokens") is not None]
        out_toks_median = round(float(statistics.median(out_toks_list)), 1) if out_toks_list else None

        in_toks_res = round(float(in_toks_median), 1) if in_toks_list else None

        row = {
            "scenario": scenario,
            "model": model,
            "effort": effort,
            "source": source,
            "harness": harness,
            "valid_reps": len(valid_calls),
            "e2e_tps": e2e_median,
            "gen_tps": gen_median,
            "ttft": ttft_median,
            "out_tokens": out_toks_median,
            "in_tokens": in_toks_res,
            "batch_id": latest_batch_id,
            "generated_at": now_iso,
        }
        rows.append(row)

    # AC-006: 按端到端 TPS 降序排序
    rows.sort(key=lambda r: r["e2e_tps"], reverse=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rows
