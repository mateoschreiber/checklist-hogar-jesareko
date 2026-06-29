from __future__ import annotations

import csv
<<<<<<< HEAD
import io
import json
import os
=======
import gzip
import hashlib
import io
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
>>>>>>> 998f1df084449202d0ee5055565d63abfeb46b81
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Optional

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

<<<<<<< HEAD
from .auth import create_token, hash_password, iso_now, session_expiry, token_hash, verify_password
from .db import connect, init_db, rows_to_dicts
=======
from .auth import create_token, hash_password, iso_now, session_expiry, verify_password
from .db import (
    DEFAULT_CATEGORIES,
    connect,
    create_backup_file,
    db_path,
    init_db,
    replace_database_from_file,
    rows_to_dicts,
)
>>>>>>> 998f1df084449202d0ee5055565d63abfeb46b81

APP_ROOT = Path(__file__).resolve().parent
STATIC_DIR = APP_ROOT / "static"
COOKIE_NAME = "checklist_session"
ROLE_CHOICES = ["admin", "usuario", "solo_lectura"]
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "/backups"))
BACKUP_KEEP = max(1, int(os.getenv("BACKUP_KEEP", "10")))

<<<<<<< HEAD
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Checklist Hogar", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
=======
app = FastAPI(title="Checklist Hogar", version="2.0.0")
>>>>>>> 998f1df084449202d0ee5055565d63abfeb46b81
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class UserCreateIn(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)
    role: str = Field(default="usuario")


class UserUpdateIn(BaseModel):
    password: Optional[str] = Field(default=None, min_length=1, max_length=200)
    role: Optional[str] = None
    is_active: Optional[bool] = None


class RunCreateIn(BaseModel):
    routine_id: Optional[str] = None
    responsible: str = Field(min_length=1, max_length=120)
    observations: str = Field(default="", max_length=3000)
    completed_task_ids: list[str] = Field(default_factory=list)
    notes_by_task: dict[str, str] = Field(default_factory=dict)
    include_pending: bool = True
    local_date: str = Field(min_length=10, max_length=10)
    local_time: str = Field(min_length=5, max_length=5)


class ChecklistItemCreateIn(BaseModel):
    section_key: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=240)
    zone: str = Field(min_length=1, max_length=160)
    category: str = Field(default="Otros")
    sort_order: int = Field(default=1, ge=0, le=10000)
    is_required: bool = True
    active: bool = True


class ChecklistItemUpdateIn(BaseModel):
    section_key: Optional[str] = Field(default=None, min_length=1, max_length=80)
    title: Optional[str] = Field(default=None, min_length=1, max_length=240)
    zone: Optional[str] = Field(default=None, min_length=1, max_length=160)
    category: Optional[str] = None
    sort_order: Optional[int] = Field(default=None, ge=0, le=10000)
    is_required: Optional[bool] = None
    active: Optional[bool] = None


class MoveItemIn(BaseModel):
    direction: str = Field(pattern="^(up|down)$")


class BackupRestoreIn(BaseModel):
    filename: str = Field(min_length=1, max_length=200)


class DeleteRunIn(BaseModel):
    reason: str = Field(default="", max_length=300)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)


def bool_env(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


<<<<<<< HEAD
def now_local_text() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")
=======
def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
>>>>>>> 998f1df084449202d0ee5055565d63abfeb46b81


def cookie_settings() -> dict[str, Any]:
    return {
        "key": COOKIE_NAME,
        "httponly": True,
        "samesite": "lax",
        "secure": bool_env("COOKIE_SECURE", False),
        "path": "/",
        "max_age": int(os.getenv("SESSION_DAYS", "30")) * 86400,
    }


def parse_local_date(date_text: str) -> str:
    try:
        return datetime.strptime(date_text, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="La fecha debe usar el formato YYYY-MM-DD.") from exc


def parse_local_time(time_text: str) -> str:
    try:
        return datetime.strptime(time_text, "%H:%M").strftime("%H:%M")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="La hora debe usar el formato HH:MM.") from exc


def normalize_role(value: str) -> str:
    role = (value or "usuario").strip().lower()
    if role not in ROLE_CHOICES:
        raise HTTPException(status_code=422, detail="Rol inválido.")
    return role


def normalize_username(value: str) -> str:
    username = value.strip().lower()
    if not username:
        raise HTTPException(status_code=422, detail="El usuario es obligatorio.")
    return username


def sanitize_csv_value(value: Any) -> str:
    text = "" if value is None else str(value)
    if text[:1] in {"=", "+", "-", "@", "\t", "\r"}:
        return f"'{text}"
    return text


def log_activity(conn: sqlite3.Connection, user_id: Optional[int], action: str, target_type: str, target_id: str = "", details: str = "") -> None:
    conn.execute(
        "INSERT INTO activity_logs (user_id, action, target_type, target_id, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, action, target_type, target_id, details.strip(), iso_now()),
    )


def serialize_user(row: dict | sqlite3.Row) -> dict:
    data = dict(row)
    return {
        "id": data["id"],
        "username": data.get("username") or data.get("name") or "",
        "role": data.get("role", "usuario"),
        "is_active": bool(data.get("is_active", 1)),
        "created_at": data.get("created_at"),
        "last_login": data.get("last_login"),
    }


def get_current_user(checklist_session: Optional[str] = Cookie(default=None)) -> dict:
    if not checklist_session:
        raise HTTPException(status_code=401, detail="Sesión requerida.")
    hashed = token_hash(checklist_session)
    with connect() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.username, u.role, u.is_active, u.created_at, u.last_login
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.expires_at > ? AND u.is_active = 1
            """,
            (hashed, iso_now()),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Sesión inválida o vencida.")
    return serialize_user(row)


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Permisos insuficientes.")
    return user


def require_writer(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in {"admin", "usuario"}:
        raise HTTPException(status_code=403, detail="Tu perfil es solo lectura.")
    return user


def ensure_section_exists(conn: sqlite3.Connection, section_key: str) -> None:
    exists = conn.execute("SELECT 1 FROM routines WHERE id = ?", (section_key,)).fetchone()
    if not exists:
        raise HTTPException(status_code=404, detail="Sección no encontrada.")


def get_tasks_for_scope(conn: sqlite3.Connection, routine_id: Optional[str], include_inactive: bool = False) -> list[dict]:
    where = []
    params: list[Any] = []
    if routine_id and routine_id != "all":
        where.append("t.routine_id = ?")
        params.append(routine_id)
    if not include_inactive:
        where.append("t.active = 1")
    query = """
        SELECT t.*, r.title AS routine_title
        FROM tasks t
        JOIN routines r ON r.id = t.routine_id
    """
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY r.sort_order, t.sort_order, t.id"
    return rows_to_dicts(conn.execute(query, params).fetchall())


def fetch_run(conn: sqlite3.Connection, run_id: int, user: dict) -> dict:
    params: list[Any] = [run_id]
    query = """
        SELECT r.*, u.username AS user_username
        FROM runs r
        JOIN users u ON u.id = r.user_id
        WHERE r.id = ? AND r.deleted_at IS NULL
    """
    if user["role"] != "admin":
        query += " AND r.user_id = ?"
        params.append(user["id"])
    run = conn.execute(query, params).fetchone()
    if not run:
        raise HTTPException(status_code=404, detail="Cierre no encontrado.")
    tasks = rows_to_dicts(conn.execute("SELECT * FROM run_tasks WHERE run_id = ? ORDER BY id", (run_id,)))
    data = dict(run)
    data["tasks"] = tasks
    return data


def backup_filename() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"checklist_backup_{stamp}.db.gz"


def list_backups() -> list[dict]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for path in sorted(BACKUP_DIR.glob("*.db.gz"), reverse=True):
        stat = path.stat()
        files.append({
            "filename": path.name,
            "size": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        })
    return files


def cleanup_old_backups() -> None:
    files = sorted(BACKUP_DIR.glob("*.db.gz"), key=lambda item: item.stat().st_mtime, reverse=True)
    for path in files[BACKUP_KEEP:]:
        path.unlink(missing_ok=True)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "checklist-hogar", "local_only": bool_env("LOCAL_ONLY", True)}


@app.get("/api/setup/status")
def setup_status() -> dict:
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
    return {
        "has_users": count > 0,
        "allow_registration": bool_env("ALLOW_REGISTRATION", False) and not bool_env("LOCAL_ONLY", True),
        "local_only": bool_env("LOCAL_ONLY", True),
        "default_admin_user": os.getenv("ADMIN_USER", "admin"),
    }


<<<<<<< HEAD
@app.post("/api/auth/register")
@limiter.limit("10/minute")
def register(request: Request, payload: RegisterIn, response: Response) -> dict:
    with connect() as conn:
        total_users = conn.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
        if total_users > 0 and not bool_env("ALLOW_REGISTRATION", False):
            raise HTTPException(status_code=403, detail="El registro público está deshabilitado.")
        role = "admin" if total_users == 0 else "user"
        try:
            cur = conn.execute(
                """
                INSERT INTO users (name, email, password_hash, role, is_active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                (payload.name.strip(), payload.email.lower(), hash_password(payload.password), role, iso_now()),
            )
        except Exception:
            raise HTTPException(status_code=409, detail="El correo ya está registrado.")
        user_id = cur.lastrowid
        token, hashed = create_token()
        conn.execute(
            "INSERT INTO sessions (user_id, token_hash, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (user_id, hashed, iso_now(), session_expiry()),
        )
    response.set_cookie(value=token, **cookie_settings())
    return {"ok": True, "user": {"id": user_id, "name": payload.name, "email": payload.email, "role": role}}


@app.post("/api/auth/login")
@limiter.limit("10/minute")
def login(request: Request, payload: LoginIn, response: Response) -> dict:
=======
@app.post("/api/auth/login")
def login(payload: LoginIn, request: Request, response: Response) -> dict:
    username = normalize_username(payload.username)
>>>>>>> 998f1df084449202d0ee5055565d63abfeb46b81
    with connect() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, role, is_active FROM users WHERE lower(username) = ?",
            (username,),
        ).fetchone()
        if not row or not row["is_active"] or not verify_password(payload.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Usuario o contraseña inválidos.")
        token, hashed = create_token()
        now = iso_now()
        conn.execute(
            "INSERT INTO sessions (user_id, token_hash, created_at, expires_at, user_agent, ip_address) VALUES (?, ?, ?, ?, ?, ?)",
            (
                row["id"],
                hashed,
                now,
                session_expiry(),
                request.headers.get("user-agent", ""),
                request.client.host if request.client else "",
            ),
        )
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now, row["id"]))
        log_activity(conn, row["id"], "login", "user", str(row["id"]), f"username={row['username']}")
    response.set_cookie(value=token, **cookie_settings())
    user_data = {"id": row["id"], "username": row["username"], "role": row["role"], "is_active": row["is_active"], "created_at": None, "last_login": now}
    return {"ok": True, "user": serialize_user(user_data)}


@app.post("/api/auth/logout")
def logout(response: Response, checklist_session: Optional[str] = Cookie(default=None)) -> dict:
    if checklist_session:
        with connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(checklist_session),))
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@app.post("/api/auth/change-password")
def change_my_password(payload: ChangePasswordIn, user: dict = Depends(get_current_user)) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
        if not row or not verify_password(payload.current_password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="La contraseña actual no coincide.")
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(payload.new_password, min_length=1), user["id"]),
        )
        log_activity(conn, user["id"], "password_changed", "user", str(user["id"]), "Cambio de contraseña propio")
    return {"ok": True}


@app.get("/api/users/me")
def me(user: dict = Depends(get_current_user)) -> dict:
    return {"user": user}


@app.get("/api/users")
def list_users(_: dict = Depends(require_admin)) -> dict:
    with connect() as conn:
        users = rows_to_dicts(
            conn.execute(
                "SELECT id, username, role, is_active, created_at, last_login FROM users ORDER BY username"
            )
        )
    return {"users": [serialize_user(row) for row in users], "roles": ROLE_CHOICES}


@app.post("/api/users")
<<<<<<< HEAD
@limiter.limit("10/minute")
def create_user(request: Request, payload: UserCreateIn, _: dict = Depends(require_admin)) -> dict:
=======
def create_user(payload: UserCreateIn, admin: dict = Depends(require_admin)) -> dict:
    username = normalize_username(payload.username)
    role = normalize_role(payload.role)
>>>>>>> 998f1df084449202d0ee5055565d63abfeb46b81
    with connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, role, is_active, created_at, name) VALUES (?, ?, ?, 1, ?, ?)",
                (username, hash_password(payload.password, min_length=1), role, iso_now(), username),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Ese usuario ya existe.") from exc
        log_activity(conn, admin["id"], "user_created", "user", str(cur.lastrowid), f"username={username}; role={role}")
    return {"ok": True, "id": cur.lastrowid}


@app.put("/api/users/{user_id}")
def update_user(user_id: int, payload: UserUpdateIn, admin: dict = Depends(require_admin)) -> dict:
    updates: list[str] = []
    params: list[Any] = []
    role = None
    with connect() as conn:
        existing = conn.execute("SELECT id, username, role, is_active FROM users WHERE id = ?", (user_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        if payload.role is not None:
            role = normalize_role(payload.role)
            updates.append("role = ?")
            params.append(role)
        if payload.is_active is not None:
            if existing["id"] == admin["id"] and payload.is_active is False:
                raise HTTPException(status_code=422, detail="No puedes desactivarte a ti mismo.")
            updates.append("is_active = ?")
            params.append(1 if payload.is_active else 0)
        if payload.password is not None:
            updates.append("password_hash = ?")
            params.append(hash_password(payload.password, min_length=1))
        if not updates:
            return {"ok": True}
        params.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
        details = []
        if role is not None:
            details.append(f"role={role}")
        if payload.is_active is not None:
            details.append(f"is_active={int(payload.is_active)}")
        if payload.password is not None:
            details.append("password=updated")
        log_activity(conn, admin["id"], "user_updated", "user", str(user_id), "; ".join(details))
    return {"ok": True}


@app.get("/api/checklist")
def get_checklist(user: dict = Depends(get_current_user)) -> dict:
    with connect() as conn:
        routines = rows_to_dicts(conn.execute("SELECT * FROM routines ORDER BY sort_order"))
        tasks = rows_to_dicts(
            conn.execute(
                "SELECT * FROM tasks WHERE active = 1 ORDER BY routine_id, sort_order, id"
            )
        )
    by_routine: dict[str, list[dict]] = {}
    for task in tasks:
        task["active"] = bool(task["active"])
        task["is_required"] = bool(task["is_required"])
        by_routine.setdefault(task["routine_id"], []).append(task)
    for routine in routines:
        routine["tasks"] = by_routine.get(routine["id"], [])
    return {"routines": routines, "user": user, "categories": DEFAULT_CATEGORIES, "roles": ROLE_CHOICES}


@app.get("/api/admin/checklist/items")
def list_admin_checklist_items(
    section_key: Optional[str] = None,
    include_inactive: bool = False,
    _: dict = Depends(require_admin),
) -> dict:
    query = """
        SELECT t.*, r.title AS section_title
        FROM tasks t
        JOIN routines r ON r.id = t.routine_id
    """
    conditions: list[str] = []
    params: list[Any] = []
    if section_key:
        conditions.append("t.routine_id = ?")
        params.append(section_key)
    if not include_inactive:
        conditions.append("t.active = 1")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY r.sort_order, t.sort_order, t.id"
    with connect() as conn:
        items = rows_to_dicts(conn.execute(query, params).fetchall())
    for item in items:
        item["active"] = bool(item["active"])
        item["is_required"] = bool(item["is_required"])
    return {"items": items, "categories": DEFAULT_CATEGORIES}


@app.post("/api/admin/checklist/items")
def create_checklist_item(payload: ChecklistItemCreateIn, admin: dict = Depends(require_admin)) -> dict:
    category = payload.category if payload.category in DEFAULT_CATEGORIES else "Otros"
    with connect() as conn:
        ensure_section_exists(conn, payload.section_key)
        item_id = f"custom-{uuid.uuid4().hex[:12]}"
        conn.execute(
            """
            INSERT INTO tasks (id, routine_id, title, zone, category, is_required, sort_order, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                payload.section_key,
                payload.title.strip(),
                payload.zone.strip(),
                category,
                1 if payload.is_required else 0,
                payload.sort_order,
                1 if payload.active else 0,
            ),
        )
        log_activity(conn, admin["id"], "item_created", "task", item_id, payload.title.strip())
    return {"ok": True, "id": item_id}


@app.put("/api/admin/checklist/items/{item_id}")
def update_checklist_item(item_id: str, payload: ChecklistItemUpdateIn, admin: dict = Depends(require_admin)) -> dict:
    with connect() as conn:
        existing = conn.execute("SELECT * FROM tasks WHERE id = ?", (item_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Ítem no encontrado.")
        section_key = payload.section_key or existing["routine_id"]
        ensure_section_exists(conn, section_key)
        category = payload.category if payload.category in DEFAULT_CATEGORIES else (existing["category"] or "Otros")
        conn.execute(
            """
            UPDATE tasks
            SET routine_id = ?, title = ?, zone = ?, category = ?, sort_order = ?, is_required = ?, active = ?
            WHERE id = ?
            """,
            (
                section_key,
                payload.title.strip() if payload.title is not None else existing["title"],
                payload.zone.strip() if payload.zone is not None else existing["zone"],
                category,
                payload.sort_order if payload.sort_order is not None else existing["sort_order"],
                1 if (payload.is_required if payload.is_required is not None else existing["is_required"]) else 0,
                1 if (payload.active if payload.active is not None else existing["active"]) else 0,
                item_id,
            ),
        )
        log_activity(conn, admin["id"], "item_updated", "task", item_id, payload.title or existing["title"])
    return {"ok": True}


@app.post("/api/admin/checklist/items/{item_id}/move")
def move_checklist_item(item_id: str, payload: MoveItemIn, admin: dict = Depends(require_admin)) -> dict:
    with connect() as conn:
        current = conn.execute(
            "SELECT id, routine_id, sort_order FROM tasks WHERE id = ?",
            (item_id,),
        ).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="Ítem no encontrado.")
        comparator = "<" if payload.direction == "up" else ">"
        ordering = "DESC" if payload.direction == "up" else "ASC"
        neighbor = conn.execute(
            f"""
            SELECT id, sort_order FROM tasks
            WHERE routine_id = ? AND sort_order {comparator} ?
            ORDER BY sort_order {ordering}, id {ordering}
            LIMIT 1
            """,
            (current["routine_id"], current["sort_order"]),
        ).fetchone()
        if not neighbor:
            return {"ok": True}
        conn.execute("UPDATE tasks SET sort_order = ? WHERE id = ?", (neighbor["sort_order"], current["id"]))
        conn.execute("UPDATE tasks SET sort_order = ? WHERE id = ?", (current["sort_order"], neighbor["id"]))
        log_activity(conn, admin["id"], "item_reordered", "task", item_id, payload.direction)
    return {"ok": True}


@app.delete("/api/admin/checklist/items/{item_id}")
def deactivate_checklist_item(item_id: str, admin: dict = Depends(require_admin)) -> dict:
    with connect() as conn:
        cur = conn.execute("UPDATE tasks SET active = 0 WHERE id = ?", (item_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Ítem no encontrado.")
        log_activity(conn, admin["id"], "item_deactivated", "task", item_id)
    return {"ok": True}


@app.post("/api/runs")
def create_run(payload: RunCreateIn, user: dict = Depends(require_writer)) -> dict:
    completed_ids = set(payload.completed_task_ids)
    if not completed_ids:
        raise HTTPException(status_code=422, detail="No hay tareas marcadas para cerrar.")
    local_date = parse_local_date(payload.local_date)
    local_time = parse_local_time(payload.local_time)
    local_closed_at = f"{local_date} {local_time}"

    with connect() as conn:
        tasks = get_tasks_for_scope(conn, payload.routine_id)
        if not tasks:
            raise HTTPException(status_code=404, detail="Rutina no encontrada.")
        completed = [task for task in tasks if task["id"] in completed_ids]
        pending = [task for task in tasks if task["id"] not in completed_ids]
        if not completed:
            raise HTTPException(status_code=422, detail="No hay tareas marcadas dentro de la sección seleccionada.")

        total_count = len(tasks)
        completed_count = len(completed)
        pending_count = total_count - completed_count
        percent = round((completed_count / total_count) * 100) if total_count else 0
        routine_title = "Todas las secciones" if not payload.routine_id or payload.routine_id == "all" else completed[0]["routine_title"]
        cur = conn.execute(
            """
            INSERT INTO runs (
                user_id, routine_id, routine_title, responsible, observations,
                completed_count, pending_count, total_count, percent,
                client_closed_at, server_closed_at, local_date, local_time, local_closed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                payload.routine_id or "all",
                routine_title,
                payload.responsible.strip(),
                payload.observations.strip(),
                completed_count,
                pending_count,
                total_count,
                percent,
                local_closed_at,
                iso_now(),
                local_date,
                local_time,
                local_closed_at,
            ),
        )
        run_id = cur.lastrowid
        for task in completed:
            conn.execute(
                "INSERT INTO run_tasks (run_id, task_id, routine_title, title, zone, note, status) VALUES (?, ?, ?, ?, ?, ?, 'completed')",
                (run_id, task["id"], task["routine_title"], task["title"], task["zone"], payload.notes_by_task.get(task["id"], "").strip()),
            )
        if payload.include_pending:
            for task in pending:
                conn.execute(
                    "INSERT INTO run_tasks (run_id, task_id, routine_title, title, zone, note, status) VALUES (?, ?, ?, ?, ?, ?, 'pending')",
                    (run_id, task["id"], task["routine_title"], task["title"], task["zone"], payload.notes_by_task.get(task["id"], "").strip()),
                )
        log_activity(conn, user["id"], "run_created", "run", str(run_id), f"percent={percent}; routine={routine_title}")
    return {
        "ok": True,
        "run_id": run_id,
        "percent": percent,
        "completed_count": completed_count,
        "total_count": total_count,
        "local_closed_at": local_closed_at,
    }


@app.get("/api/runs")
def list_runs(limit: int = 20, offset: int = 0, user: dict = Depends(get_current_user)) -> dict:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    with connect() as conn:
        params: list[Any] = []
        where = ["r.deleted_at IS NULL"]
        if user["role"] != "admin":
            where.append("r.user_id = ?")
            params.append(user["id"])
        base = """
            SELECT r.*, u.username AS user_username
            FROM runs r
            JOIN users u ON u.id = r.user_id
            WHERE {where_clause}
            ORDER BY r.local_date DESC, r.local_time DESC, r.id DESC
        """.format(where_clause=" AND ".join(where))
        rows = rows_to_dicts(conn.execute(base + " LIMIT ? OFFSET ?", [*params, limit + 1, offset]).fetchall())
    has_more = len(rows) > limit
    runs = rows[:limit]
    return {"runs": runs, "next_offset": offset + limit if has_more else None, "has_more": has_more}


@app.get("/api/runs/{run_id}")
def get_run(run_id: int, user: dict = Depends(get_current_user)) -> dict:
    with connect() as conn:
        return {"run": fetch_run(conn, run_id, user)}


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: int, payload: DeleteRunIn | None = None, admin: dict = Depends(require_admin)) -> dict:
    with connect() as conn:
        cur = conn.execute(
            "UPDATE runs SET deleted_at = ?, deleted_by_user_id = ?, deleted_reason = ? WHERE id = ? AND deleted_at IS NULL",
            (iso_now(), admin["id"], (payload.reason if payload else "").strip(), run_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Cierre no encontrado.")
        log_activity(conn, admin["id"], "run_deleted", "run", str(run_id), (payload.reason if payload else "").strip())
    return {"ok": True}


@app.get("/api/reports/calendar")
def reports_calendar(month: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Usá el formato YYYY-MM.") from exc
    with connect() as conn:
        params: list[Any] = [f"{month}%"]
        query = """
            SELECT r.*, u.username AS user_username
            FROM runs r
            JOIN users u ON u.id = r.user_id
            WHERE r.deleted_at IS NULL AND r.local_date LIKE ?
        """
        if user["role"] != "admin":
            query += " AND r.user_id = ?"
            params.append(user["id"])
        query += " ORDER BY r.local_date ASC, r.local_time ASC, r.id ASC"
        runs = rows_to_dicts(conn.execute(query, params).fetchall())

    today = datetime.now().strftime("%Y-%m-%d")
    days: dict[str, dict[str, Any]] = {}
    for run in runs:
        date_key = run.get("local_date") or str(run.get("server_closed_at", ""))[:10]
        day = days.setdefault(date_key, {"date": date_key, "count": 0, "runs": [], "status": "empty"})
        day["count"] += 1
        day["runs"].append(run)
        if run["percent"] == 100 and day["status"] != "overdue":
            day["status"] = "complete"
        elif date_key < today:
            day["status"] = "overdue"
        else:
            day["status"] = "incomplete"
    return {"month": month, "days": list(days.values())}


@app.get("/api/export/runs.csv")
def export_runs_csv(user: dict = Depends(get_current_user)) -> StreamingResponse:
    with connect() as conn:
        params: list[Any] = []
        query = """
            SELECT r.id, r.local_date, r.local_time, r.local_closed_at, r.routine_title, r.responsible,
                   r.completed_count, r.pending_count, r.total_count, r.percent, u.username AS user_username
            FROM runs r
            JOIN users u ON u.id = r.user_id
            WHERE r.deleted_at IS NULL
        """
        if user["role"] != "admin":
            query += " AND r.user_id = ?"
            params.append(user["id"])
        query += " ORDER BY r.local_date DESC, r.local_time DESC, r.id DESC"
        rows = rows_to_dicts(conn.execute(query, params).fetchall())
    return csv_response(
        "historial_checklist.csv",
        rows,
        ["id", "local_date", "local_time", "local_closed_at", "routine_title", "responsible", "completed_count", "pending_count", "total_count", "percent", "user_username"],
    )


@app.get("/api/runs/{run_id}/export.csv")
def export_run_csv(run_id: int, user: dict = Depends(get_current_user)) -> StreamingResponse:
    with connect() as conn:
        run = fetch_run(conn, run_id, user)
    rows = []
    for task in run["tasks"]:
        rows.append(
            {
                "run_id": run["id"],
                "fecha_cierre": run.get("local_closed_at") or run.get("client_closed_at") or run.get("server_closed_at"),
                "responsable": run["responsible"],
                "usuario": run.get("user_username") or "",
                "rutina": run["routine_title"],
                "estado": task["status"],
                "tarea": task["title"],
                "zona": task["zone"],
                "nota": task.get("note") or "",
            }
        )
    return csv_response(
        f"cierre_{run_id}.csv",
        rows,
        ["run_id", "fecha_cierre", "responsable", "usuario", "rutina", "estado", "tarea", "zona", "nota"],
    )


@app.get("/api/runs/{run_id}/export.json")
def export_run_json(run_id: int, user: dict = Depends(get_current_user)) -> JSONResponse:
    with connect() as conn:
        run = fetch_run(conn, run_id, user)
    return JSONResponse(run, headers={"Content-Disposition": f'attachment; filename="cierre_{run_id}.json"'})


@app.get("/api/runs/{run_id}/receipt", response_class=HTMLResponse)
def receipt(run_id: int, user: dict = Depends(get_current_user)) -> HTMLResponse:
    with connect() as conn:
        run = fetch_run(conn, run_id, user)
    completed = [task for task in run["tasks"] if task["status"] == "completed"]
    pending = [task for task in run["tasks"] if task["status"] == "pending"]

    def rows(tasks: list[dict]) -> str:
        return "".join(
            f"<tr><td>{escape(task['title'])}</td><td>{escape(task['zone'])}</td><td>{escape(task.get('note') or '')}</td></tr>"
            for task in tasks
        ) or '<tr><td colspan="3">Sin registros.</td></tr>'

    closed_at = escape(run.get("local_closed_at") or run.get("client_closed_at") or run.get("server_closed_at") or "")
    observations = escape(run.get("observations") or "Sin observaciones.")
    doc = f"""
    <!doctype html>
    <html lang="es">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Comprobante de cierre #{run['id']}</title>
      <style>
        :root {{ --blue:#0b5ed7; --ink:#142033; --line:#d8e3f2; --soft:#f5f9ff; --ok:#0f9f6e; --warn:#b54708; }}
        * {{ box-sizing:border-box; }}
        body {{ margin:0; font-family:Arial, Helvetica, sans-serif; color:var(--ink); background:#f4f7fb; }}
        .page {{ max-width:900px; margin:24px auto; background:#fff; border:1px solid var(--line); border-radius:24px; padding:28px; }}
        .top {{ display:flex; justify-content:space-between; gap:16px; align-items:flex-start; border-bottom:3px solid var(--blue); padding-bottom:18px; }}
        .badge {{ background:var(--blue); color:#fff; border-radius:999px; padding:10px 16px; font-size:12px; font-weight:700; }}
        .grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:22px 0; }}
        .box {{ border:1px solid var(--line); border-radius:16px; padding:12px; background:var(--soft); }}
        .box small {{ display:block; font-size:11px; text-transform:uppercase; color:#5f7288; margin-bottom:4px; font-weight:700; }}
        .box strong {{ font-size:18px; }}
        table {{ width:100%; border-collapse:collapse; }}
        th, td {{ text-align:left; padding:10px; border-bottom:1px solid var(--line); vertical-align:top; }}
        th {{ background:var(--soft); color:var(--blue); font-size:12px; text-transform:uppercase; }}
        .obs {{ border:1px solid var(--line); border-radius:16px; padding:14px; min-height:72px; }}
        .actions {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:20px; }}
        .btn {{ display:inline-flex; align-items:center; justify-content:center; min-height:44px; padding:0 16px; border-radius:999px; background:var(--blue); color:#fff; font-weight:700; text-decoration:none; border:0; cursor:pointer; }}
        .signature {{ display:grid; grid-template-columns:1fr 1fr; gap:28px; margin-top:40px; }}
        .line {{ border-top:1px solid #374151; text-align:center; padding-top:8px; color:#6b7280; }}
        @media (max-width:760px) {{ .page {{ margin:0; border-radius:0; }} .top {{ flex-direction:column; }} .grid {{ grid-template-columns:1fr 1fr; }} }}
        @media print {{ body {{ background:#fff; }} .page {{ max-width:none; margin:0; border:0; }} .actions {{ display:none; }} }}
      </style>
    </head>
    <body>
      <main class="page">
        <section class="top">
          <div>
            <h1>Comprobante de cierre</h1>
            <p>Registro local del checklist del hogar.</p>
          </div>
          <div class="badge">Cierre #{run['id']}</div>
        </section>
        <section class="grid">
          <div class="box"><small>Fecha local</small><strong>{closed_at}</strong></div>
          <div class="box"><small>Responsable</small><strong>{escape(run['responsible'])}</strong></div>
          <div class="box"><small>Usuario</small><strong>{escape(run.get('user_username') or '')}</strong></div>
          <div class="box"><small>Resultado</small><strong>{run['completed_count']}/{run['total_count']} · {run['percent']}%</strong></div>
        </section>
        <h2>Tareas realizadas</h2>
        <table><thead><tr><th>Tarea</th><th>Zona</th><th>Nota</th></tr></thead><tbody>{rows(completed)}</tbody></table>
        <h2>Tareas pendientes</h2>
        <table><thead><tr><th>Tarea</th><th>Zona</th><th>Nota</th></tr></thead><tbody>{rows(pending)}</tbody></table>
        <h2>Observación general</h2>
        <div class="obs">{observations}</div>
        <div class="signature"><div class="line">Responsable</div><div class="line">Revisión</div></div>
        <div class="actions">
          <button class="btn" onclick="window.print()">Descargar / Imprimir</button>
          <a class="btn" href="/api/runs/{run['id']}/export.csv">Descargar CSV</a>
          <a class="btn" href="/api/runs/{run['id']}/export.json">Descargar JSON</a>
        </div>
      </main>
    </body>
    </html>
    """
    return HTMLResponse(doc)


@app.get("/api/admin/backups")
def admin_list_backups(_: dict = Depends(require_admin)) -> dict:
    return {"backups": list_backups(), "keep": BACKUP_KEEP}


@app.post("/api/admin/backups/create")
def admin_create_backup(admin: dict = Depends(require_admin)) -> dict:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    filename = backup_filename()
    plain_path = BACKUP_DIR / filename.replace(".gz", "")
    gzip_path = BACKUP_DIR / filename
    create_backup_file(plain_path)
    with plain_path.open("rb") as src, gzip.open(gzip_path, "wb") as dst:
        shutil.copyfileobj(src, dst)
    try:
        plain_path.unlink(missing_ok=True)
    except OSError:
        # The compressed backup is already valid; cleanup must not turn it into a failed operation.
        pass
    cleanup_old_backups()
    with connect() as conn:
        log_activity(conn, admin["id"], "backup_created", "backup", filename)
    return {"ok": True, "filename": filename}


@app.get("/api/admin/backups/{filename}")
def admin_download_backup(filename: str, _: dict = Depends(require_admin)) -> FileResponse:
    path = BACKUP_DIR / Path(filename).name
    if not path.exists() or path.parent != BACKUP_DIR:
        raise HTTPException(status_code=404, detail="Backup no encontrado.")
    return FileResponse(path, filename=path.name)


@app.post("/api/admin/backups/restore")
def admin_restore_backup(payload: BackupRestoreIn, admin: dict = Depends(require_admin)) -> dict:
    backup_path = BACKUP_DIR / Path(payload.filename).name
    if not backup_path.exists() or backup_path.parent != BACKUP_DIR:
        raise HTTPException(status_code=404, detail="Backup no encontrado.")
    with tempfile.TemporaryDirectory() as tmpdir:
        extracted = Path(tmpdir) / "restore.db"
        with gzip.open(backup_path, "rb") as src, extracted.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        replace_database_from_file(extracted, db_path())
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM sessions")
        log_activity(conn, admin["id"], "backup_restored", "backup", payload.filename)
    return {"ok": True}


@app.get("/api/admin/activity")
def admin_activity(limit: int = 50, _: dict = Depends(require_admin)) -> dict:
    limit = max(1, min(limit, 200))
    with connect() as conn:
        rows = rows_to_dicts(
            conn.execute(
                """
                SELECT a.*, u.username
                FROM activity_logs a
                LEFT JOIN users u ON u.id = a.user_id
                ORDER BY a.created_at DESC, a.id DESC
                LIMIT ?
                """,
                (limit,),
            )
        )
    return {"activity": rows}


def csv_response(filename: str, rows: list[dict], headers: list[str]) -> StreamingResponse:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: sanitize_csv_value(row.get(key, "")) for key in headers})
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
