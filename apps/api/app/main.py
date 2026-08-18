from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Base, engine, get_session
from .models import Task


@asynccontextmanager
async def lifespan(app: FastAPI):
    # POC-level schema management. A real project would use Alembic migrations
    # (that is one of the follow-up exercises in the README).
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="TaskFlow API", lifespan=lifespan)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class TaskRead(BaseModel):
    id: int
    title: str
    status: str
    created_at: datetime
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
    task = Task(title=payload.title)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    session.delete(task)
    session.commit()
