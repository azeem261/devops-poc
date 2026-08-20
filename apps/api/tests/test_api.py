import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_task_lifecycle():
    with TestClient(app) as client:
        r = client.get("/healthz")
        assert r.status_code == 200

        r = client.post("/api/tasks", json={"title": "learn argocd"})
        assert r.status_code == 201
        task = r.json()
        assert task["title"] == "learn argocd"
        assert task["status"] == "pending"
        assert task["priority"] == "normal"
        assert task["attempts"] == 0

        r = client.get("/api/tasks")
        assert r.status_code == 200
        assert any(t["id"] == task["id"] for t in r.json())

        r = client.delete(f"/api/tasks/{task['id']}")
        assert r.status_code == 204

        r = client.delete(f"/api/tasks/{task['id']}")
        assert r.status_code == 404


def test_priority_accepted():
    with TestClient(app) as client:
        r = client.post("/api/tasks", json={"title": "urgent thing", "priority": "high"})
        assert r.status_code == 201
        assert r.json()["priority"] == "high"


def test_invalid_priority_rejected():
    with TestClient(app) as client:
        r = client.post("/api/tasks", json={"title": "bad", "priority": "urgent"})
        assert r.status_code == 422
