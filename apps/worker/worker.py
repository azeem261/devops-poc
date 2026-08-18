"""TaskFlow worker.

Polls Postgres for pending tasks, "processes" them (simulated work),
and marks them done. Uses FOR UPDATE SKIP LOCKED so multiple worker
replicas can run concurrently without grabbing the same task.
"""

import logging
import os
import time

from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("worker")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://taskflow:taskflow@localhost:5432/taskflow",
)
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL_SECONDS", "2"))
WORK_SECONDS = float(os.environ.get("WORK_SECONDS", "5"))

CLAIM_SQL = text(
    """
    UPDATE tasks SET status = 'processing'
    WHERE id = (
        SELECT id FROM tasks
        WHERE status = 'pending'
        ORDER BY created_at
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING id, title
    """
)

FINISH_SQL = text(
    "UPDATE tasks SET status = 'done', processed_at = now() WHERE id = :id"
)


def main() -> None:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    log.info("worker started, polling every %ss", POLL_INTERVAL)

    while True:
        try:
            with engine.begin() as conn:
                row = conn.execute(CLAIM_SQL).first()
            if row is None:
                time.sleep(POLL_INTERVAL)
                continue

            task_id, title = row
            log.info("processing task %s: %r", task_id, title)
            time.sleep(WORK_SECONDS)  # simulate real work

            with engine.begin() as conn:
                conn.execute(FINISH_SQL, {"id": task_id})
            log.info("task %s done", task_id)
        except Exception:
            # DB not up yet, tasks table not created yet, transient network
            # error, etc. Log and retry rather than crash-looping the pod.
            log.exception("worker iteration failed, retrying in 5s")
            time.sleep(5)


if __name__ == "__main__":
    main()
