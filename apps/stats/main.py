"""TaskFlow stats service.

Read-only: task counts by status plus operational metrics (average completion
time, oldest pending age — the raw material for a worker-freshness SLO).
Tolerates the tasks table not existing yet (the api service owns the schema).
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from sqlalchemy import create_engine, text

_STANDARD_ATTRS = set(
    vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record):
        out = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "service": "stats",
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
log = logging.getLogger("stats")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://taskflow:taskflow@localhost:5432/taskflow",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
app = FastAPI(title="TaskFlow Stats")

COUNTS_SQL = text("SELECT status, COUNT(*) FROM tasks GROUP BY status")
AVG_COMPLETION_SQL = text(
    "SELECT AVG(EXTRACT(EPOCH FROM processed_at - created_at)) "
    "FROM tasks WHERE status = 'done'"
)
OLDEST_PENDING_SQL = text(
    "SELECT EXTRACT(EPOCH FROM (now() - MIN(created_at))) "
    "FROM tasks WHERE status = 'pending'"
)


@app.middleware("http")
async def access_log(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    log.info(
        "request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round((time.perf_counter() - start) * 1000, 1),
        },
    )
    return response


@app.get("/healthz")
def healthz():
    # Deliberately does not touch the DB: the pod is "alive" even while
    # Postgres is still starting. Readiness for traffic is a separate concern.
    return {"status": "ok"}


@app.get("/api/stats")
def stats():
    counts = {"pending": 0, "processing": 0, "done": 0, "failed": 0}
    try:
        with engine.connect() as conn:
            for status, count in conn.execute(COUNTS_SQL):
                counts[status] = count
            avg_completion = conn.execute(AVG_COMPLETION_SQL).scalar()
            oldest_pending = conn.execute(OLDEST_PENDING_SQL).scalar()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database not ready: {exc}")
    counts["total"] = sum(counts.values())
    counts["avg_completion_seconds"] = (
        round(float(avg_completion), 1) if avg_completion is not None else None
    )
    counts["oldest_pending_seconds"] = (
        round(float(oldest_pending), 1) if oldest_pending is not None else None
    )
    return counts
