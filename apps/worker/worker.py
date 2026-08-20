"""TaskFlow worker.

Claims the highest-priority pending task (FOR UPDATE SKIP LOCKED, so multiple
replicas never grab the same task), simulates work, and randomly fails a
configurable fraction of tasks to exercise the retry/dead-letter path:

    pending -> processing -> done
                    \\-> pending again (retry, exponential backoff)
                    \\-> failed (after MAX_ATTEMPTS)

Env vars:
    DATABASE_URL           Postgres URL
    POLL_INTERVAL_SECONDS  idle sleep between claim attempts (default 2)
    WORK_SECONDS           simulated processing time (default 5)
    FAILURE_RATE           fraction of attempts that fail, 0..1 (default 0.15)
    MAX_ATTEMPTS           attempts before dead-lettering (default 3)
    RETRY_BASE_SECONDS     backoff base: base * 2^(attempts-1) (default 10)
"""

import json
import logging
import os
import random
import time
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

_STANDARD_ATTRS = set(
    vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record):
        out = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "service": "worker",
            "msg": record.getMessage(),
        }
        out.update(
            {k: v for k, v in record.__dict__.items() if k not in _STANDARD_ATTRS}
        )
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
log = logging.getLogger("worker")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://taskflow:taskflow@localhost:5432/taskflow",
)
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL_SECONDS", "2"))
WORK_SECONDS = float(os.environ.get("WORK_SECONDS", "5"))
FAILURE_RATE = float(os.environ.get("FAILURE_RATE", "0.15"))
MAX_ATTEMPTS = int(os.environ.get("MAX_ATTEMPTS", "3"))
RETRY_BASE_SECONDS = float(os.environ.get("RETRY_BASE_SECONDS", "10"))

CLAIM_SQL = text(
    """
    UPDATE tasks SET status = 'processing', started_at = now()
    WHERE id = (
        SELECT id FROM tasks
        WHERE status = 'pending'
          AND (next_attempt_at IS NULL OR next_attempt_at <= now())
        ORDER BY
          CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,
          created_at
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING id, title, priority, attempts
    """
)

DONE_SQL = text(
    "UPDATE tasks SET status = 'done', processed_at = now(), error = NULL "
    "WHERE id = :id"
)

RETRY_SQL = text(
    """
    UPDATE tasks SET
        status = 'pending',
        attempts = :attempts,
        error = :error,
        next_attempt_at = now() + make_interval(secs => :backoff)
    WHERE id = :id
    """
)

DEAD_LETTER_SQL = text(
    """
    UPDATE tasks SET
        status = 'failed',
        attempts = :attempts,
        error = :error,
        processed_at = now()
    WHERE id = :id
    """
)


def main() -> None:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    log.info(
        "worker started",
        extra={
            "poll_interval": POLL_INTERVAL,
            "failure_rate": FAILURE_RATE,
            "max_attempts": MAX_ATTEMPTS,
        },
    )

    while True:
        try:
            with engine.begin() as conn:
                row = conn.execute(CLAIM_SQL).first()
            if row is None:
                time.sleep(POLL_INTERVAL)
                continue

            task_id, title, priority, attempts = row
            attempt = attempts + 1
            log.info(
                "task claimed",
                extra={"task_id": task_id, "priority": priority, "attempt": attempt},
            )
            time.sleep(WORK_SECONDS)  # simulate real work

            if random.random() < FAILURE_RATE:
                error = f"simulated failure on attempt {attempt}"
                if attempt >= MAX_ATTEMPTS:
                    with engine.begin() as conn:
                        conn.execute(
                            DEAD_LETTER_SQL,
                            {"id": task_id, "attempts": attempt, "error": error},
                        )
                    log.error(
                        "task dead-lettered",
                        extra={"task_id": task_id, "attempts": attempt},
                    )
                else:
                    backoff = RETRY_BASE_SECONDS * (2 ** (attempt - 1))
                    with engine.begin() as conn:
                        conn.execute(
                            RETRY_SQL,
                            {
                                "id": task_id,
                                "attempts": attempt,
                                "error": error,
                                "backoff": backoff,
                            },
                        )
                    log.warning(
                        "task failed, will retry",
                        extra={
                            "task_id": task_id,
                            "attempt": attempt,
                            "backoff_seconds": backoff,
                        },
                    )
            else:
                with engine.begin() as conn:
                    conn.execute(DONE_SQL, {"id": task_id})
                log.info(
                    "task done", extra={"task_id": task_id, "attempt": attempt}
                )
        except Exception:
            # DB not up yet, schema missing, transient network error, etc.
            log.exception("worker iteration failed, retrying in 5s")
            time.sleep(5)


if __name__ == "__main__":
    main()
