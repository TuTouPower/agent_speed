from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from agent_rank.models import GridCell, CallRecord


class BaseHarness(ABC):
    @abstractmethod
    def run(
        self,
        cell: GridCell,
        rep: int,
        batch_id: str,
        prompt: str,
        fixture_path: Path,
        cwd: Path | str,
        timeout: int = 300,
    ) -> CallRecord:
        pass
