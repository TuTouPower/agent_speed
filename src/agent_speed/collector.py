from __future__ import annotations

import json
import os
from pathlib import Path
from agent_speed.models import CallRecord


def append_result_record(file_path: Path | str, record: CallRecord) -> None:
    """AC-006: results.jsonl 每次调用一行、只追加；字段全集符合 §7.1；不含模型正文、密钥、本机绝对路径。"""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = record.to_dict()
    line = json.dumps(data, ensure_ascii=False) + "\n"

    with open(path, "a", encoding="utf-8") as f:
        f.write(line)
