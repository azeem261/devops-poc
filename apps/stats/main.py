"""TaskFlow stats service.

Read-only service: returns task counts by status from the shared Postgres.
It does NOT own the schema (the api service creates the tasks table), so it
must tolerate the table not existing yet on a fresh database.
"""

import os

from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://taskflow:taskflow@localhost:5432/taskflow",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
app = FastAPI(title="TaskFlow Stats")

STATS_SQL = text("SELECT status, COUNT(*) FROM tasks GROUP BY status")


@app.get("/healthz")
def healthz():
    # Deliberately does not touch the DB: the pod is "alive" even while
    # Postgres is still starting. Readiness for traffic is a separate concern.
    return {"status": "ok"}


@app.get("/api/stats")
def stats():
    counts = {"pending": 0, "processing": 0, "done": 0}
    try:
        with engine.connect() as conn:
            for status, count in conn.execute(STATS_SQL):
                counts[status] = count
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database not ready: {exc}")
    counts["total"] = sum(counts.values())
    return counts
