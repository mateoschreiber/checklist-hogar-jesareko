from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Optional

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import create_token, hash_password, iso_now, session_expiry, verify_password
from .db import connect, init_db, rows_to_dicts

APP_ROOT = Path(__file__).resolve().parent
STATIC_DIR = APP_ROOT / "static"
COOKIE_NAME = "checklist_session"

app = FastAPI(title="Checklist Hogar", version="1.0.0")
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class LoginIn(BaseModel):
    email: str = Field(min_length=1, max_length=254)
    password: str


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    password: str = Field(min_length=8, max_length=200)


class UserCreateIn(RegisterIn):
    role: str = Field(default="user", pattern="^(admin|user)$")


class RunCreateIn(BaseModel):
    routine_id: Optional[str] = None
    responsible: str = Field(min_length=1, max_length=120)
    observations: str = Field(default="", max_length=3000)
    completed_task_ids: list[str] = Field(default_factory=list)
    notes_by_task: dict[str, str] = Field(default_factory=dict)
    include_pending: bool = True
    client_closed_at: Optional[str] = None


def bool_env(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def now_local_text() -> str:
    # El contenedor usa TZ si se declara en .env / compose.
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def cookie_settings() -> dict[str, Any]:
    return {
        "key": COOKIE_NAME,
        "httponly": True,
        "samesite": "lax",
        "secure": bool_env("COOKIE_SECURE", False),
        "path": "/",
        "max_age": int(os.getenv("SESSION_DAYS", "30")) * 86400,
    }


def get_current_user(checklist_session: Optional[str] = Cookie(default=None)) -> dict:
    if not checklist_session:
        raise HTTPException(status_code=401, detail="Sesión requerida.")
    hashed = token_hash(checklist_session)
    with connect() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.name, u.email, u.role, u.is_active
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.expires_at > ? AND u.is_active = 1
            """,
            (hashed, iso_now()),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Sesión inválida o vencida.")
    return dict(row)


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Permisos insuficientes.")
    return user


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "checklist-hogar"}


@app.get("/api/setup/status")
def setup_status() -> dict:
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
    return {
        "has_users": count > 0,
        "allow_registration": bool_env("ALLOW_REGISTRATION", False),
    }


@app.post("/api/auth/register")
def register(payload: RegisterIn, response: Response) -> dict:
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
def login(payload: LoginIn, request: Request, response: Response) -> dict:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, name, email, password_hash, role, is_active FROM users WHERE lower(email) = ? OR lower(name) = ?",
            (payload.email.strip().lower(), payload.email.strip().lower()),
        ).fetchone()
        if not row or not row["is_active"] or not verify_password(payload.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Usuario o contraseña inválidos.")
        token, hashed = create_token()
        conn.execute(
            """
            INSERT INTO sessions (user_id, token_hash, created_at, expires_at, user_agent, ip_address)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"], hashed, iso_now(), session_expiry(),
                request.headers.get("user-agent", ""),
                request.client.host if request.client else "",
            ),
        )
    response.set_cookie(value=token, **cookie_settings())
    return {"ok": True, "user": {"id": row["id"], "name": row["name"], "email": row["email"], "role": row["role"]}}


@app.post("/api/auth/logout")
def logout(response: Response, checklist_session: Optional[str] = Cookie(default=None)) -> dict:
    if checklist_session:
        with connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(checklist_session),))
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/users/me")
def me(user: dict = Depends(get_current_user)) -> dict:
    return {"user": user}


@app.get("/api/users")
def list_users(_: dict = Depends(require_admin)) -> dict:
    with connect() as conn:
        users = rows_to_dicts(conn.execute("SELECT id, name, email, role, is_active, created_at FROM users ORDER BY id"))
    return {"users": users}


@app.post("/api/users")
def create_user(payload: UserCreateIn, _: dict = Depends(require_admin)) -> dict:
    with connect() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO users (name, email, password_hash, role, is_active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                (payload.name.strip(), payload.email.lower(), hash_password(payload.password), payload.role, iso_now()),
            )
        except Exception:
            raise HTTPException(status_code=409, detail="El correo ya está registrado.")
    return {"ok": True, "id": cur.lastrowid}


@app.get("/api/checklist")
def get_checklist(user: dict = Depends(get_current_user)) -> dict:
    with connect() as conn:
        routines = rows_to_dicts(conn.execute("SELECT * FROM routines ORDER BY sort_order"))
        tasks = rows_to_dicts(conn.execute("SELECT * FROM tasks ORDER BY routine_id, sort_order"))
    by_routine: dict[str, list[dict]] = {}
    for task in tasks:
        by_routine.setdefault(task["routine_id"], []).append(task)
    for routine in routines:
        routine["tasks"] = by_routine.get(routine["id"], [])
    return {"routines": routines, "user": user}


def get_tasks_for_scope(conn, routine_id: Optional[str]) -> list[dict]:
    if routine_id and routine_id != "all":
        rows = conn.execute(
            """
            SELECT t.*, r.title AS routine_title
            FROM tasks t JOIN routines r ON r.id = t.routine_id
            WHERE t.routine_id = ?
            ORDER BY t.sort_order
            """,
            (routine_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT t.*, r.title AS routine_title
            FROM tasks t JOIN routines r ON r.id = t.routine_id
            ORDER BY r.sort_order, t.sort_order
            """
        ).fetchall()
    return rows_to_dicts(rows)


@app.post("/api/runs")
def create_run(payload: RunCreateIn, user: dict = Depends(get_current_user)) -> dict:
    completed_ids = set(payload.completed_task_ids)
    if not completed_ids:
        raise HTTPException(status_code=422, detail="No hay tareas marcadas para cerrar.")

    with connect() as conn:
        tasks = get_tasks_for_scope(conn, payload.routine_id)
        if not tasks:
            raise HTTPException(status_code=404, detail="Rutina no encontrada.")

        completed = [task for task in tasks if task["id"] in completed_ids]
        pending = [task for task in tasks if task["id"] not in completed_ids]
        if not completed:
            raise HTTPException(status_code=422, detail="No hay tareas marcadas dentro de la rutina seleccionada.")

        total_count = len(tasks)
        completed_count = len(completed)
        pending_count = total_count - completed_count
        percent = round((completed_count / total_count) * 100) if total_count else 0

        routine_title = "Todas las rutinas" if not payload.routine_id or payload.routine_id == "all" else completed[0]["routine_title"]
        cur = conn.execute(
            """
            INSERT INTO runs (
                user_id, routine_id, routine_title, responsible, observations,
                completed_count, pending_count, total_count, percent,
                client_closed_at, server_closed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"], payload.routine_id or "all", routine_title,
                payload.responsible.strip(), payload.observations.strip(),
                completed_count, pending_count, total_count, percent,
                payload.client_closed_at, iso_now(),
            ),
        )
        run_id = cur.lastrowid

        def insert_task(task: dict, status: str) -> None:
            conn.execute(
                """
                INSERT INTO run_tasks (run_id, task_id, routine_title, title, zone, note, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, task["id"], task["routine_title"], task["title"], task["zone"],
                    payload.notes_by_task.get(task["id"], "").strip(), status,
                ),
            )

        for task in completed:
            insert_task(task, "completed")
        if payload.include_pending:
            for task in pending:
                insert_task(task, "pending")

    return {"ok": True, "run_id": run_id, "percent": percent, "completed_count": completed_count, "total_count": total_count}


def fetch_run(conn, run_id: int, user: dict) -> dict:
    if user["role"] == "admin":
        run = conn.execute(
            """
            SELECT r.*, u.name AS user_name, u.email AS user_email
            FROM runs r JOIN users u ON u.id = r.user_id
            WHERE r.id = ?
            """,
            (run_id,),
        ).fetchone()
    else:
        run = conn.execute(
            """
            SELECT r.*, u.name AS user_name, u.email AS user_email
            FROM runs r JOIN users u ON u.id = r.user_id
            WHERE r.id = ? AND r.user_id = ?
            """,
            (run_id, user["id"]),
        ).fetchone()
    if not run:
        raise HTTPException(status_code=404, detail="Cierre no encontrado.")
    tasks = rows_to_dicts(conn.execute("SELECT * FROM run_tasks WHERE run_id = ? ORDER BY id", (run_id,)))
    data = dict(run)
    data["tasks"] = tasks
    return data


@app.get("/api/runs")
def list_runs(limit: int = 30, offset: int = 0, user: dict = Depends(get_current_user)) -> dict:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    with connect() as conn:
        if user["role"] == "admin":
            rows = conn.execute(
                """
                SELECT r.*, u.name AS user_name, u.email AS user_email
                FROM runs r JOIN users u ON u.id = r.user_id
                ORDER BY r.server_closed_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT r.*, u.name AS user_name, u.email AS user_email
                FROM runs r JOIN users u ON u.id = r.user_id
                WHERE r.user_id = ?
                ORDER BY r.server_closed_at DESC
                LIMIT ? OFFSET ?
                """,
                (user["id"], limit, offset),
            ).fetchall()
    return {"runs": rows_to_dicts(rows)}


@app.get("/api/reports/calendar")
def reports_calendar(month: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        start = datetime.strptime(month, "%Y-%m").replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=422, detail="Usá el formato YYYY-MM.")

    next_year = start.year + (1 if start.month == 12 else 0)
    next_month = 1 if start.month == 12 else start.month + 1
    end = start.replace(year=next_year, month=next_month, day=1)

    base_query = """
        SELECT r.*, u.name AS user_name, u.email AS user_email
        FROM runs r JOIN users u ON u.id = r.user_id
        WHERE r.server_closed_at >= ? AND r.server_closed_at < ?
    """
    params: list[Any] = [start.isoformat(), end.isoformat()]
    if user["role"] != "admin":
        base_query += " AND r.user_id = ?"
        params.append(user["id"])
    base_query += " ORDER BY r.server_closed_at ASC"

    with connect() as conn:
        runs = rows_to_dicts(conn.execute(base_query, params).fetchall())

    days: dict[str, dict[str, Any]] = {}
    for run in runs:
        date_key = str(run.get("server_closed_at", ""))[:10]
        day = days.setdefault(date_key, {"date": date_key, "count": 0, "runs": []})
        day["count"] += 1
        day["runs"].append(run)

    return {"month": month, "days": list(days.values())}


@app.get("/api/runs/{run_id}")
def get_run(run_id: int, user: dict = Depends(get_current_user)) -> dict:
    with connect() as conn:
        return {"run": fetch_run(conn, run_id, user)}


def csv_response(filename: str, rows: list[dict], headers: list[str]) -> StreamingResponse:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in headers})
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/runs/{run_id}/export.csv")
def export_run_csv(run_id: int, user: dict = Depends(get_current_user)) -> StreamingResponse:
    with connect() as conn:
        run = fetch_run(conn, run_id, user)
    rows = []
    for task in run["tasks"]:
        rows.append({
            "run_id": run["id"],
            "fecha_cierre": run["client_closed_at"] or run["server_closed_at"],
            "responsable": run["responsible"],
            "rutina": run["routine_title"],
            "estado": task["status"],
            "tarea": task["title"],
            "zona": task["zone"],
            "nota": task.get("note") or "",
        })
    return csv_response(f"cierre_{run_id}.csv", rows, ["run_id", "fecha_cierre", "responsable", "rutina", "estado", "tarea", "zona", "nota"])


@app.get("/api/runs/{run_id}/export.json")
def export_run_json(run_id: int, user: dict = Depends(get_current_user)) -> JSONResponse:
    with connect() as conn:
        run = fetch_run(conn, run_id, user)
    return JSONResponse(run, headers={"Content-Disposition": f'attachment; filename="cierre_{run_id}.json"'})


@app.get("/api/export/runs.csv")
def export_runs_csv(user: dict = Depends(get_current_user)) -> StreamingResponse:
    with connect() as conn:
        if user["role"] == "admin":
            rows = rows_to_dicts(conn.execute(
                """
                SELECT r.id, r.server_closed_at, r.client_closed_at, r.routine_title, r.responsible,
                       r.completed_count, r.pending_count, r.total_count, r.percent, u.name AS user_name, u.email AS user_email
                FROM runs r JOIN users u ON u.id = r.user_id
                ORDER BY r.server_closed_at DESC
                """
            ))
        else:
            rows = rows_to_dicts(conn.execute(
                """
                SELECT r.id, r.server_closed_at, r.client_closed_at, r.routine_title, r.responsible,
                       r.completed_count, r.pending_count, r.total_count, r.percent, u.name AS user_name, u.email AS user_email
                FROM runs r JOIN users u ON u.id = r.user_id
                WHERE r.user_id = ?
                ORDER BY r.server_closed_at DESC
                """,
                (user["id"],),
            ))
    return csv_response(
        "historial_checklist.csv", rows,
        ["id", "server_closed_at", "client_closed_at", "routine_title", "responsible", "completed_count", "pending_count", "total_count", "percent", "user_name", "user_email"],
    )


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: int, user: dict = Depends(get_current_user)) -> dict:
    with connect() as conn:
        if user["role"] == "admin":
            cur = conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        else:
            cur = conn.execute("DELETE FROM runs WHERE id = ? AND user_id = ?", (run_id, user["id"]))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Cierre no encontrado.")
    return {"ok": True}


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

    closed_at = escape(run.get("client_closed_at") or run.get("server_closed_at") or now_local_text())
    doc = f"""
    <!doctype html>
    <html lang="es">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Comprobante de rutina #{run['id']}</title>
      <style>
        :root {{ --blue:#0057D9; --ink:#111827; --muted:#6F7D95; --line:#DCE5F2; }}
        * {{ box-sizing:border-box; }}
        body {{ margin:0; font-family:Arial, Helvetica, sans-serif; color:var(--ink); background:#f8fafd; }}
        .page {{ max-width:900px; margin:30px auto; background:#fff; border:1px solid var(--line); border-radius:24px; padding:36px; box-shadow:0 16px 40px rgba(15,23,42,.08); }}
        .top {{ display:flex; justify-content:space-between; gap:20px; align-items:flex-start; border-bottom:3px solid var(--blue); padding-bottom:22px; }}
        h1 {{ margin:0; font-size:32px; letter-spacing:-.04em; }}
        .badge {{ background:var(--blue); color:#fff; border-radius:999px; padding:10px 16px; font-size:12px; font-weight:700; text-transform:uppercase; }}
        .grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:24px 0; }}
        .box {{ border:1px solid var(--line); border-radius:16px; padding:14px; }}
        .box small {{ display:block; color:var(--muted); text-transform:uppercase; font-size:11px; font-weight:700; margin-bottom:4px; }}
        .box strong {{ font-size:18px; }}
        h2 {{ margin:28px 0 12px; font-size:21px; }}
        table {{ width:100%; border-collapse:collapse; }}
        th, td {{ text-align:left; border-bottom:1px solid var(--line); padding:10px; vertical-align:top; }}
        th {{ background:#EAF3FF; color:#003DAE; font-size:12px; text-transform:uppercase; }}
        .obs {{ border:1px solid var(--line); border-radius:16px; padding:16px; min-height:70px; color:#333; }}
        .actions {{ display:flex; gap:10px; margin-top:24px; }}
        button, a.btn {{ border:0; background:var(--blue); color:#fff; border-radius:999px; padding:12px 18px; font-weight:700; text-decoration:none; cursor:pointer; }}
        .signature {{ display:grid; grid-template-columns:1fr 1fr; gap:40px; margin-top:48px; }}
        .line {{ border-top:1px solid #333; text-align:center; padding-top:8px; color:var(--muted); }}
        @media(max-width:760px) {{ .page {{ margin:0; border-radius:0; padding:22px; }} .top {{ flex-direction:column; }} .grid {{ grid-template-columns:1fr 1fr; }} }}
        @media print {{ body {{ background:#fff; }} .page {{ margin:0; max-width:none; border:0; box-shadow:none; }} .actions {{ display:none; }} }}
      </style>
    </head>
    <body>
      <main class="page">
        <section class="top">
          <div>
            <h1>Comprobante de rutina del hogar</h1>
            <p>Registro de cierre con tareas realizadas y pendientes.</p>
          </div>
          <div class="badge">Cierre #{run['id']}</div>
        </section>
        <section class="grid">
          <div class="box"><small>Fecha y hora</small><strong>{closed_at}</strong></div>
          <div class="box"><small>Responsable</small><strong>{escape(run['responsible'])}</strong></div>
          <div class="box"><small>Rutina</small><strong>{escape(run['routine_title'])}</strong></div>
          <div class="box"><small>Cumplimiento</small><strong>{run['completed_count']}/{run['total_count']} · {run['percent']}%</strong></div>
        </section>
        <h2>Tareas realizadas</h2>
        <table><thead><tr><th>Tarea</th><th>Zona</th><th>Nota</th></tr></thead><tbody>{rows(completed)}</tbody></table>
        <h2>Tareas pendientes</h2>
        <table><thead><tr><th>Tarea</th><th>Zona</th><th>Nota</th></tr></thead><tbody>{rows(pending)}</tbody></table>
        <h2>Observaciones</h2>
        <div class="obs">{escape(run.get('observations') or 'Sin observaciones.')}</div>
        <div class="signature"><div class="line">Responsable</div><div class="line">Revisión</div></div>
        <div class="actions">
          <button onclick="window.print()">Imprimir / guardar PDF</button>
          <a class="btn" href="/api/runs/{run['id']}/export.csv">Descargar CSV</a>
          <a class="btn" href="/api/runs/{run['id']}/export.json">Descargar JSON</a>
        </div>
      </main>
    </body>
    </html>
    """
    return HTMLResponse(doc)
