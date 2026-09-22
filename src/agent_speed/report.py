from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
from typing import Any


def calculate_median(values: list[float | int]) -> float | None:
    if not values:
        return None
    val = statistics.median(values)
    return round(float(val), 2)


def _parse_start(rec: dict[str, Any]) -> datetime:
    raw = rec.get("start_time")
    if not raw:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(raw))
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def _is_valid_call(r: dict[str, Any]) -> bool:
    if r.get("status") != "success":
        return False
    out_toks = r.get("out_tokens")
    if out_toks is None or out_toks < 500:
        return False
    if r.get("wall") is None or r.get("wall", 0) <= 0:
        return False
    return True


def generate_latest_json(
    results_jsonl: Path | str,
    output_json: Path | str,
) -> list[dict[str, Any]]:
    """读 results.jsonl 重新生成 latest.json。

    - 每个格子跨全部 batch 收集有效成功调用；
    - 按 start_time 取最近 2 次有效成功；有效次数 < 2 不上站；
    - 不再要求同一次 bench / 同一 batch_id 内凑满 2 次；
    - 输出 token < 500 或失败的调用无效；
    - 对方账单输入 token < 切片 cl100k 一半的格子不上站；
    - codex 等无生成窗口的格子照常上站，生成 TPS 为 None；
    - 中位数由最近 2 次有效成功计算（含 wall 秒，三位小数）；
    - 按端到端 TPS 降序覆盖写 latest.json。
    """
    jsonl_path = Path(results_jsonl)
    out_path = Path(output_json)

    if not jsonl_path.exists():
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("[]\n", encoding="utf-8")
        return []

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

        valid_calls = [r for r in records if _is_valid_call(r)]
        # 最近两次有效成功（跨 batch）
        valid_calls.sort(key=_parse_start)
        if len(valid_calls) < 2:
            continue
        used = valid_calls[-2:]

        in_toks_list = [r["in_tokens"] for r in used if r.get("in_tokens") is not None]
        in_toks_median = statistics.median(in_toks_list) if in_toks_list else 0

        cl100k = used[-1].get("cl100k_tokens") or used[0].get("cl100k_tokens") or 200000
        if in_toks_median < (cl100k / 2.0):
            continue

        e2e_list = [r["e2e_tps"] for r in used if r.get("e2e_tps") is not None]
        e2e_median = round(float(statistics.median(e2e_list)), 2) if e2e_list else 0.0

        gen_list = [r["gen_tps"] for r in used if r.get("gen_tps") is not None]
        gen_median = round(float(statistics.median(gen_list)), 2) if gen_list else None

        ttft_list = [r["ttft"] for r in used if r.get("ttft") is not None]
        ttft_median = round(float(statistics.median(ttft_list)), 3) if ttft_list else None

        out_toks_list = [r["out_tokens"] for r in used if r.get("out_tokens") is not None]
        out_toks_median = round(float(statistics.median(out_toks_list)), 1) if out_toks_list else None

        in_toks_res = round(float(in_toks_median), 1) if in_toks_list else None

        wall_list = [r["wall"] for r in used if r.get("wall") is not None]
        wall_median = round(float(statistics.median(wall_list)), 3) if wall_list else None

        # batch_id：最近一次成功所属 batch（兼容字段；页面可不展示）
        latest_batch_id = used[-1].get("batch_id")
        sample_times = [str(r["start_time"]) for r in used if r.get("start_time")]

        row = {
            "scenario": scenario,
            "model": model,
            "effort": effort,
            "source": source,
            "harness": harness,
            "valid_reps": len(used),
            "e2e_tps": e2e_median,
            "gen_tps": gen_median,
            "ttft": ttft_median,
            "wall": wall_median,
            "out_tokens": out_toks_median,
            "in_tokens": in_toks_res,
            "batch_id": latest_batch_id,
            "sample_times": sample_times,
            "generated_at": now_iso,
        }
        rows.append(row)

    rows.sort(key=lambda r: r["e2e_tps"], reverse=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rows
