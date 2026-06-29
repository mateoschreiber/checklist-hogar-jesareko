import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    db_file = Path(tempfile.mkdtemp()) / "test_checklist.db"
    db_file.parent.mkdir(parents=True, exist_ok=True)

    os.environ["APP_SECRET"] = "test-secret-for-api"
    os.environ["ADMIN_EMAIL"] = "admin@test.local"
    os.environ["ADMIN_PASSWORD"] = "admin-pass-123"
    os.environ["ADMIN_NAME"] = "Test Admin"
    os.environ["ALLOW_REGISTRATION"] = "false"
    os.environ["DATABASE_PATH"] = str(db_file)

    import app.db as db_mod
    db_mod.DATABASE_PATH = str(db_file)

    from app.main import app
    from app.db import init_db

    init_db()

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    try:
        db_file.unlink(missing_ok=True)
        db_file.parent.rmdir()
    except OSError:
        pass


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["service"] == "checklist-hogar"


def test_setup_status(client):
    response = client.get("/api/setup/status")
    assert response.status_code == 200
    data = response.json()
    assert data["has_users"] is True
    assert data["allow_registration"] is False


def test_frontend_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_login_with_invalid_credentials(client):
    response = client.post("/api/auth/login", json={
        "email": "admin@test.local",
        "password": "wrong-password"
    })
    assert response.status_code == 401


def test_login_with_valid_credentials(client):
    response = client.post("/api/auth/login", json={
        "email": "admin@test.local",
        "password": "admin-pass-123"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["user"]["role"] == "admin"
    assert response.cookies.get("checklist_session") is not None


def test_register_disabled_when_users_exist(client):
    response = client.post("/api/auth/register", json={
        "name": "Test User",
        "email": "user@test.local",
        "password": "test-pass-123"
    })
    assert response.status_code == 403


def test_unauthorized_access(client):
    response = client.get("/api/users/me")
    assert response.status_code == 401

    response = client.get("/api/checklist")
    assert response.status_code == 401

    response = client.get("/api/runs")
    assert response.status_code == 401


def test_checklist_authenticated(client):
    client.post("/api/auth/login", json={
        "email": "admin@test.local",
        "password": "admin-pass-123"
    })

    response = client.get("/api/checklist")
    assert response.status_code == 200
    data = response.json()
    assert "routines" in data
    assert "user" in data
    assert len(data["routines"]) > 0


def test_create_run_and_receipt(client):
    client.post("/api/auth/login", json={
        "email": "admin@test.local",
        "password": "admin-pass-123"
    })

    checklist = client.get("/api/checklist").json()
    first_task = checklist["routines"][0]["tasks"][0]

    response = client.post("/api/runs", json={
        "routine_id": first_task["routine_id"],
        "responsible": "Test Person",
        "observations": "All good",
        "completed_task_ids": [first_task["id"]],
        "notes_by_task": {},
        "include_pending": True,
        "client_closed_at": "01/01/2025 10:00"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "run_id" in data

    run_id = data["run_id"]
    receipt = client.get(f"/api/runs/{run_id}/receipt")
    assert receipt.status_code == 200
    assert "Comprobante" in receipt.text
    assert "Test Person" in receipt.text

    csv = client.get(f"/api/runs/{run_id}/export.csv")
    assert csv.status_code == 200
    assert "text/csv" in csv.headers["content-type"]


def test_delete_run(client):
    client.post("/api/auth/login", json={
        "email": "admin@test.local",
        "password": "admin-pass-123"
    })

    checklist = client.get("/api/checklist").json()
    first_task = checklist["routines"][0]["tasks"][0]

    created = client.post("/api/runs", json={
        "routine_id": first_task["routine_id"],
        "responsible": "Test Person",
        "observations": "",
        "completed_task_ids": [first_task["id"]],
        "notes_by_task": {},
        "include_pending": False
    })
    run_id = created.json()["run_id"]

    response = client.delete(f"/api/runs/{run_id}")
    assert response.status_code == 200

    response = client.get(f"/api/runs/{run_id}")
    assert response.status_code == 404
