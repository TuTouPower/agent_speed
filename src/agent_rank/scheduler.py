from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import threading
from typing import Callable
import uuid

from agent_rank.models import GridCell, CallRecord


RunnerFunc = Callable[[GridCell, int, str], CallRecord]


class QueueScheduler:
    """双层受控并发调度器：全局上限 + 单队列上限、3+1 batch。"""

    def __init__(
        self,
        runner: RunnerFunc,
        global_max_workers: int = 10,
        per_queue_concurrency: int = 2,
    ):
        self.runner = runner
        self.global_max_workers = global_max_workers
        self.per_queue_concurrency = per_queue_concurrency

    def run_all(
        self,
        cells: list[GridCell],
        reps: int = 3,
    ) -> tuple[list[CallRecord], list[str]]:
        # 按队列键分组
        queues: dict[str, list[GridCell]] = defaultdict(list)
        for cell in cells:
            queues[cell.queue_key].append(cell)

        all_records: list[CallRecord] = []
        all_logs: list[str] = []
        records_lock = threading.Lock()
        logs_lock = threading.Lock()

        # 每个队列独立的信号量（控单队并发 <= per_queue_concurrency）
        queue_semaphores = {
            q_key: threading.Semaphore(self.per_queue_concurrency)
            for q_key in queues
        }

        # 调度执行函数
        def execute_one(cell: GridCell, rep: int, batch_id: str, is_retry: bool = False) -> CallRecord:
            q_key = cell.queue_key
            sem = queue_semaphores[q_key]

            with sem:
                start_ts = datetime.now(timezone.utc).astimezone().isoformat()
                prefix = "retry" if is_retry else "start"
                log_line = f"[{start_ts}] {prefix} queue={q_key} cell={cell.cell_id} rep={rep} batch={batch_id}"
                with logs_lock:
                    all_logs.append(log_line)

                rec = self.runner(cell, rep, batch_id)

                end_ts = datetime.now(timezone.utc).astimezone().isoformat()
                done_prefix = "retry_done" if is_retry else "done"
                done_line = (
                    f"[{end_ts}] {done_prefix} queue={q_key} cell={cell.cell_id} rep={rep} "
                    f"status={rec.status} e2e_tps={rec.e2e_tps} gen_tps={rec.gen_tps}"
                )
                with logs_lock:
                    all_logs.append(done_line)
                with records_lock:
                    all_records.append(rec)

                return rec

        # 每个队列的处理逻辑
        def process_queue_batches(q_key: str, q_cells: list[GridCell], pool: ThreadPoolExecutor):
            retry_list: list[tuple[GridCell, str]] = []

            for cell in q_cells:
                batch_id = uuid.uuid4().hex[:12]
                cell_futures = []

                for rep in range(1, reps + 1):
                    fut = pool.submit(execute_one, cell, rep, batch_id, False)
                    cell_futures.append(fut)

                # 等待当前 cell 的常规轮次完成，判断是否需要补测
                cell_had_failure = False
                for fut in cell_futures:
                    rec = fut.result()
                    if rec.status != "success":
                        cell_had_failure = True

                if cell_had_failure:
                    retry_list.append((cell, batch_id))

            # 队列末尾补测 1 次
            retry_futures = []
            for cell, batch_id in retry_list:
                rep = reps + 1  # 补测为第 4 次
                fut = pool.submit(execute_one, cell, rep, batch_id, True)
                retry_futures.append(fut)

            for fut in retry_futures:
                fut.result()

        # 全局线程池（控全局并发 <= global_max_workers）
        with ThreadPoolExecutor(max_workers=self.global_max_workers) as pool:
            # 启动各队列的主循环（由内部线程协调各队列的提交与完成）
            queue_workers = []
            for q_key, q_cells in queues.items():
                t = threading.Thread(
                    target=process_queue_batches,
                    args=(q_key, q_cells, pool),
                )
                t.start()
                queue_workers.append(t)

            for t in queue_workers:
                t.join()

        return all_records, all_logs
