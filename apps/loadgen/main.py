"""TaskFlow load generator.

Continuously creates tasks through the API at a configurable rate with a
configurable priority mix, so the system always has realistic traffic —
dashboards, SLOs, and error budgets are meaningless on an idle app.

Also enforces a cap on total tasks by deleting the oldest finished ones,
so days of load generation don't grow the table unboundedly.

Env vars:
    API_URL           base URL of the api service (default http://api:8000)
    TASKS_PER_MINUTE  average creation rate (default 3; 0 pauses creation)
    HIGH_PCT          fraction of tasks with high priority (default 0.2)
    LOW_PCT           fraction with low priority (default 0.3)
    MAX_TASKS         cap on total tasks, oldest done/failed pruned (default
                      200; 0 disables pruning)
"""

import json
import logging
import os
import random
import time
from datetime import datetime, timezone

import httpx

_STANDARD_ATTRS = set(
    vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record):
        out = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "service": "loadgen",
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
log = logging.getLogger("loadgen")

API_URL = os.environ.get("API_URL", "http://api:8000").rstrip("/")
TASKS_PER_MINUTE = float(os.environ.get("TASKS_PER_MINUTE", "3"))
HIGH_PCT = float(os.environ.get("HIGH_PCT", "0.2"))
LOW_PCT = float(os.environ.get("LOW_PCT", "0.3"))
MAX_TASKS = int(os.environ.get("MAX_TASKS", "200"))

VERBS = ["deploy", "backup", "index", "sync", "compress", "migrate", "scan", "render"]
NOUNS = ["invoices", "logs", "images", "reports", "metrics", "orders", "emails"]


def pick_priority() -> str:
    r = random.random()
    if r < HIGH_PCT:
        return "high"
    if r < HIGH_PCT + LOW_PCT:
        return "low"
    return "normal"


def make_title() -> str:
    return f"{random.choice(VERBS)} {random.choice(NOUNS)} #{random.randint(100, 999)}"


def prune(client: httpx.Client) -> None:
    if MAX_TASKS <= 0:
        return
    tasks = client.get(f"{API_URL}/api/tasks").json()
    if len(tasks) <= MAX_TASKS:
        return
    finished = [t for t in tasks if t["status"] in ("done", "failed")]
    # tasks come newest-first; prune from the oldest end
    to_delete = finished[::-1][: len(tasks) - MAX_TASKS]
    for t in to_delete:
        client.delete(f"{API_URL}/api/tasks/{t['id']}")
    if to_delete:
        log.info("pruned finished tasks", extra={"count": len(to_delete)})


def main() -> None:
    log.info(
        "loadgen started",
        extra={
            "api_url": API_URL,
            "tasks_per_minute": TASKS_PER_MINUTE,
            "high_pct": HIGH_PCT,
            "low_pct": LOW_PCT,
            "max_tasks": MAX_TASKS,
        },
    )
    client = httpx.Client(timeout=5.0)
    iteration = 0

    while True:
        if TASKS_PER_MINUTE <= 0:
            time.sleep(30)
            continue
        # jittered sleep around the average interval, so traffic isn't a metronome
        interval = 60.0 / TASKS_PER_MINUTE
        time.sleep(random.uniform(0.5 * interval, 1.5 * interval))

        payload = {"title": make_title(), "priority": pick_priority()}
        try:
            r = client.post(f"{API_URL}/api/tasks", json=payload)
            r.raise_for_status()
            log.info(
                "task created",
                extra={"task_id": r.json()["id"], "priority": payload["priority"]},
            )
        except Exception:
            # API down/restarting is normal life; log and keep going —
            # failed synthetic requests are themselves useful signal later.
            log.exception("task creation failed")

        iteration += 1
        if iteration % 20 == 0:
            try:
                prune(client)
            except Exception:
                log.exception("prune failed")


if __name__ == "__main__":
    main()
