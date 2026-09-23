from __future__ import annotations

import json
from pathlib import Path
from typing import Any
try:
    import yaml
except ImportError:
    yaml = None

from agent_speed.models import GridCell
from agent_speed.scenarios import VALID_SCENARIOS


class BenchmarkConfig:
    def __init__(
        self,
        global_max_concurrency: int = 10,
        per_queue_concurrency: int = 2,
        defaults: dict[str, Any] | None = None,
        cells: list[GridCell] | None = None,
        scenarios: dict[str, dict[str, Any]] | None = None,
    ):
        self.global_max_concurrency = global_max_concurrency
        self.per_queue_concurrency = per_queue_concurrency
        self.defaults = defaults or {}
        self.cells = cells or []
        self.scenarios = scenarios or {}


def parse_scenarios(raw: Any) -> dict[str, dict[str, Any]]:
    """校验并规范化 `scenarios:` 节：三档齐全，prompt 二选一，cl100k 为正整数。"""
    if not isinstance(raw, dict):
        raise ValueError("config 缺少 `scenarios:` 节（三档输入映射）")
    missing = [s for s in VALID_SCENARIOS if s not in raw]
    if missing:
        raise ValueError(f"config `scenarios:` 缺档：{missing}")
    unknown = [s for s in raw if s not in VALID_SCENARIOS]
    if unknown:
        raise ValueError(f"config `scenarios:` 未知档：{unknown}")
    out: dict[str, dict[str, Any]] = {}
    for scen in VALID_SCENARIOS:
        entry = raw[scen]
        if not isinstance(entry, dict):
            raise ValueError(f"config `scenarios.{scen}` 须为映射")
        has_file = bool(entry.get("prompt_file"))
        has_text = bool(entry.get("prompt_text"))
        if has_file == has_text:
            raise ValueError(f"config `scenarios.{scen}` 须且仅须含 prompt_file / prompt_text 其一")
        cl = entry.get("cl100k_tokens")
        if isinstance(cl, bool) or not isinstance(cl, int) or cl <= 0:
            raise ValueError(f"config `scenarios.{scen}.cl100k_tokens` 须为正整数")
        out[scen] = {
            "prompt_file": entry.get("prompt_file"),
            "prompt_text": entry.get("prompt_text"),
            "fixture_file": entry.get("fixture_file"),
            "cl100k_tokens": cl,
        }
    return out


def load_benchmark_config(config_path: Path | str | None = None) -> BenchmarkConfig:
    if config_path is None:
        repo_root = Path(__file__).resolve().parent.parent.parent
        yaml_path = repo_root / "config" / "benchmark.yaml"
        json_path = repo_root / "config" / "benchmark.json"
        config_path = yaml_path if yaml_path.exists() else json_path

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    raw_text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        if yaml is None:
            raise ImportError(
                "PyYAML is required to read benchmark.yaml. "
                "Please run via 'uv run ...' or ensure pyyaml is installed."
            )
        data = yaml.safe_load(raw_text)
    else:
        data = json.loads(raw_text)

    conc = data.get("concurrency", {})
    global_max = conc.get("global_max", 10)
    per_queue = conc.get("per_queue", 2)
    defaults = data.get("defaults", {})

    cells = []
    default_scenario = defaults.get("scenario", "200k")
    for cell_data in data.get("cells", []):
        cell = GridCell.from_dict(cell_data, default_scenario=default_scenario)
        cells.append(cell)

    scenarios = parse_scenarios(data.get("scenarios"))

    return BenchmarkConfig(
        global_max_concurrency=global_max,
        per_queue_concurrency=per_queue,
        defaults=defaults,
        cells=cells,
        scenarios=scenarios,
    )
