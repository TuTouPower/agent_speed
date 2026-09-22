from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable
import uuid

from agent_speed.models import GridCell, CallRecord


RunnerFunc = Callable[[GridCell, int, str], CallRecord]


class QueueScheduler:
    """按 source+harness 队列调度：同队列串行、队列间并行、3+1 batch。"""

    def __init__(self, runner: RunnerFunc, max_workers: int | None = None):
        self.runner = runner
        self.max_workers = max_workers

    def run_all(self, cells: list[GridCell], reps: int = 3) -> tuple[list[CallRecord], list[str]]:
        # 按队列键分组
        queues: dict[str, list[GridCell]] = defaultdict(list)
        for cell in cells:
            queues[cell.queue_key].append(cell)

        all_records: list[CallRecord] = []
        all_logs: list[str] = []

        def process_queue(queue_key: str, q_cells: list[GridCell]) -> tuple[list[CallRecord], list[str]]:
            q_records: list[CallRecord] = []
            q_logs: list[str] = []

            retry_list: list[tuple[GridCell, str]] = []

            # 常规 reps 轮执行
            for cell in q_cells:
                batch_id = uuid.uuid4().hex[:12]
                cell_had_failure = False

                for rep in range(1, reps + 1):
                    start_ts = datetime.now(timezone.utc).astimezone().isoformat()
                    q_logs.append(f"[{start_ts}] start queue={queue_key} cell={cell.cell_id} rep={rep} batch={batch_id}")

                    rec = self.runner(cell, rep, batch_id)
                    q_records.append(rec)

                    end_ts = datetime.now(timezone.utc).astimezone().isoformat()
                    q_logs.append(
                        f"[{end_ts}] done queue={queue_key} cell={cell.cell_id} rep={rep} "
                        f"status={rec.status} e2e_tps={rec.e2e_tps} gen_tps={rec.gen_tps}"
                    )

                    if rec.status != "success":
                        cell_had_failure = True

                if cell_had_failure:
                    retry_list.append((cell, batch_id))

            # 队列末尾补测 1 次
            for cell, batch_id in retry_list:
                rep = 4
                start_ts = datetime.now(timezone.utc).astimezone().isoformat()
                q_logs.append(f"[{start_ts}] retry queue={queue_key} cell={cell.cell_id} rep={rep} batch={batch_id}")

                rec = self.runner(cell, rep, batch_id)
                q_records.append(rec)

                end_ts = datetime.now(timezone.utc).astimezone().isoformat()
                q_logs.append(
                    f"[{end_ts}] retry_done queue={queue_key} cell={cell.cell_id} rep={rep} "
                    f"status={rec.status} e2e_tps={rec.e2e_tps} gen_tps={rec.gen_tps}"
                )

            return q_records, q_logs

        # 队列之间并行执行
        worker_count = self.max_workers or max(len(queues), 1)
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(process_queue, q_key, q_cells)
                for q_key, q_cells in queues.items()
            ]
            for fut in futures:
                q_recs, q_l = fut.result()
                all_records.extend(q_recs)
                all_logs.extend(q_l)

        return all_records, all_logs
