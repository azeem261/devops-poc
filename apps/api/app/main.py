import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Base, engine, get_session
from .jsonlog import setup_json_logging
from .models import Task

setup_json_logging("api")
log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # POC-level schema management: creates missing TABLES only — it will NOT
    # add new columns to an existing table. Proper migrations (Alembic) are
    # a planned milestone; until then a schema change needs the table dropped.
    Base.metadata.create_all(bind=engine)
    log.info("schema ensured")
    yield


app = FastAPI(title="TaskFlow API", lifespan=lifespan)


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


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    priority: Literal["high", "normal", "low"] = "normal"


class TaskRead(BaseModel):
    id: int
    title: str
    status: str
    priority: str
    attempts: int
    error: str | None
    created_at: datetime
    started_at: datetime | None
    processed_at: datetime | None

    model_config = {"from_attributes": True}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/api/tasks", response_model=list[TaskRead])
def list_tasks(session: Session = Depends(get_session)):
    tasks = session.scalars(select(Task).order_by(Task.created_at.desc())).all()
    return tasks


@app.post("/api/tasks", response_model=TaskRead, status_code=201)
def create_task(payload: TaskCreate, session: Session = Depends(get_session)):
    task = Task(title=payload.title, priority=payload.priority)
    session.add(task)
    session.commit()
    session.refresh(task)
    log.info("task created", extra={"task_id": task.id, "priority": task.priority})
    return task


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    session.delete(task)
    session.commit()
    log.info("task deleted", extra={"task_id": task_id})
