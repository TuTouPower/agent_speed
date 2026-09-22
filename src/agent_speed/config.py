from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_speed.models import GridCell


class BenchmarkConfig:
    def __init__(
        self,
        global_max_concurrency: int = 10,
        per_queue_concurrency: int = 2,
        defaults: dict[str, Any] | None = None,
        cells: list[GridCell] | None = None,
    ):
        self.global_max_concurrency = global_max_concurrency
        self.per_queue_concurrency = per_queue_concurrency
        self.defaults = defaults or {}
        self.cells = cells or []


def load_benchmark_config(config_path: Path | str | None = None) -> BenchmarkConfig:
    if config_path is None:
        repo_root = Path(__file__).resolve().parent.parent.parent
        config_path = repo_root / "config" / "benchmark.json"

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    conc = data.get("concurrency", {})
    global_max = conc.get("global_max", 10)
    per_queue = conc.get("per_queue", 2)
    defaults = data.get("defaults", {})

    cells = []
    default_scenario = defaults.get("scenario", "200k")
    for cell_data in data.get("cells", []):
        cell = GridCell.from_dict(cell_data, default_scenario=default_scenario)
        cells.append(cell)

    return BenchmarkConfig(
        global_max_concurrency=global_max,
        per_queue_concurrency=per_queue,
        defaults=defaults,
        cells=cells,
    )
