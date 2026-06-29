from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path
from typing import Iterable

from .auth import hash_password, iso_now
from .checklist_seed import ROUTINES

DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/checklist.db")
DEFAULT_CATEGORIES = [
    "Seguridad",
    "Energía",
    "Agua",
    "Puertas/Ventanas",
    "Mascotas",
    "Limpieza",
    "Otros",
]
ROLE_ALIASES = {
    "admin": "admin",
    "user": "usuario",
    "usuario": "usuario",
    "solo_lectura": "solo_lectura",
    "readonly": "solo_lectura",
    "read_only": "solo_lectura",
}


def db_path() -> str:
    return os.getenv("DATABASE_PATH", DATABASE_PATH)


def connect() -> sqlite3.Connection:
    path = Path(db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=20, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return bool(row)


def ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    if column not in table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def normalize_role(value: str | None) -> str:
    return ROLE_ALIASES.get((value or "").strip().lower(), "usuario")


def make_unique_username(conn: sqlite3.Connection, base: str, user_id: int) -> str:
    base = (base or "usuario").strip().lower()
    base = "".join(ch for ch in base if ch.isalnum() or ch in {"-", "_", "."})
    if not base:
        base = f"usuario{user_id}"
    candidate = base
    suffix = 1
    while True:
        existing = conn.execute(
            "SELECT id FROM users WHERE lower(username) = lower(?) AND id != ?",
            (candidate, user_id),
        ).fetchone()
        if not existing:
            return candidate
        suffix += 1
        candidate = f"{base}{suffix}"


def infer_category(title: str, zone: str) -> str:
    text = f"{title} {zone}".lower()
    if any(word in text for word in ["puerta", "ventana", "cerradura", "portón", "porton"]):
        return "Puertas/Ventanas"
    if any(word in text for word in ["agua", "grifo", "lavamanos", "pileta", "ducha", "desagüe", "desague", "tanque"]):
        return "Agua"
    if any(word in text for word in ["luz", "eléctr", "electr", "enchufe", "aire acondicionado", "horno", "campana", "heladera", "lavarropas"]):
        return "Energía"
    if any(word in text for word in ["seguridad", "extintor", "botiquín", "botiquin", "emergencia", "plaga"]):
        return "Seguridad"
    if any(word in text for word in ["mascota", "perro", "gato"]):
        return "Mascotas"
    if any(word in text for word in ["limpiar", "lavar", "barrer", "trapear", "ordenar", "polvo", "basura"]):
        return "Limpieza"
    return "Otros"


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'usuario',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                last_login TEXT,
                name TEXT,
                email TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                user_agent TEXT,
                ip_address TEXT
            );

            CREATE TABLE IF NOT EXISTS routines (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                frequency TEXT NOT NULL,
                description TEXT NOT NULL,
                sort_order INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                routine_id TEXT NOT NULL REFERENCES routines(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                zone TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Otros',
                is_required INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                routine_id TEXT,
                routine_title TEXT NOT NULL,
                responsible TEXT NOT NULL,
                observations TEXT,
                completed_count INTEGER NOT NULL,
                pending_count INTEGER NOT NULL,
                total_count INTEGER NOT NULL,
                percent INTEGER NOT NULL,
                client_closed_at TEXT,
                server_closed_at TEXT NOT NULL,
                local_date TEXT,
                local_time TEXT,
                local_closed_at TEXT,
                deleted_at TEXT,
                deleted_by_user_id INTEGER REFERENCES users(id),
                deleted_reason TEXT
            );

            CREATE TABLE IF NOT EXISTS run_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                task_id TEXT,
                routine_title TEXT NOT NULL,
                title TEXT NOT NULL,
                zone TEXT NOT NULL,
                note TEXT,
                status TEXT NOT NULL CHECK(status IN ('completed', 'pending'))
            );

            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                action TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT,
                details TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
            CREATE INDEX IF NOT EXISTS idx_runs_user_date ON runs(user_id, server_closed_at DESC);
            CREATE INDEX IF NOT EXISTS idx_run_tasks_run ON run_tasks(run_id);
            CREATE INDEX IF NOT EXISTS idx_activity_logs_created_at ON activity_logs(created_at DESC);
            """
        )
        ensure_schema(conn)
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username COLLATE NOCASE)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_routine_active ON tasks(routine_id, active, sort_order)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_local_date ON runs(local_date)")
        seed_checklist(conn)
        seed_admin(conn)


def ensure_schema(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "users", "username", "TEXT")
    ensure_column(conn, "users", "last_login", "TEXT")
    ensure_column(conn, "users", "name", "TEXT")
    ensure_column(conn, "users", "email", "TEXT")
    ensure_column(conn, "tasks", "category", "TEXT NOT NULL DEFAULT 'Otros'")
    ensure_column(conn, "tasks", "is_required", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "tasks", "active", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "runs", "local_date", "TEXT")
    ensure_column(conn, "runs", "local_time", "TEXT")
    ensure_column(conn, "runs", "local_closed_at", "TEXT")
    ensure_column(conn, "runs", "deleted_at", "TEXT")
    ensure_column(conn, "runs", "deleted_by_user_id", "INTEGER")
    ensure_column(conn, "runs", "deleted_reason", "TEXT")
    if not table_exists(conn, "activity_logs"):
        conn.execute(
            """
            CREATE TABLE activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                action TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT,
                details TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
    migrate_users(conn)
    migrate_tasks(conn)
    migrate_runs(conn)


def migrate_users(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT id, username, name, email, role FROM users ORDER BY id").fetchall()
    for row in rows:
        source = row["username"] or row["name"] or (row["email"] or "").split("@", 1)[0] or f"usuario{row['id']}"
        username = make_unique_username(conn, source, row["id"])
        conn.execute(
            "UPDATE users SET username = ?, role = ? WHERE id = ?",
            (username, normalize_role(row["role"]), row["id"]),
        )


def migrate_tasks(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT id, title, zone, category, is_required, active FROM tasks").fetchall()
    for row in rows:
        category = row["category"] if row["category"] in DEFAULT_CATEGORIES else infer_category(row["title"], row["zone"])
        is_required = 1 if row["is_required"] not in (0, None) else 0
        active = 0 if row["active"] == 0 else 1
        conn.execute(
            "UPDATE tasks SET category = ?, is_required = ?, active = ? WHERE id = ?",
            (category, is_required, active, row["id"]),
        )


def migrate_runs(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT id, client_closed_at, server_closed_at, local_date, local_time, local_closed_at FROM runs"
    ).fetchall()
    for row in rows:
        local_date = row["local_date"]
        local_time = row["local_time"]
        local_closed_at = row["local_closed_at"]
        raw = row["client_closed_at"] or row["server_closed_at"] or ""
        if not local_date:
            local_date = str(raw)[:10] if len(str(raw)) >= 10 else None
        if not local_time and len(str(raw)) >= 16:
            local_time = str(raw)[11:16]
        if not local_closed_at and local_date:
            local_closed_at = f"{local_date} {local_time}".strip()
        conn.execute(
            "UPDATE runs SET local_date = ?, local_time = ?, local_closed_at = ? WHERE id = ?",
            (local_date, local_time, local_closed_at, row["id"]),
        )


def seed_checklist(conn: sqlite3.Connection) -> None:
    for routine in ROUTINES:
        conn.execute(
            """
            INSERT INTO routines (id, title, frequency, description, sort_order)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                frequency = excluded.frequency,
                description = excluded.description,
                sort_order = excluded.sort_order
            """,
            (routine["id"], routine["title"], routine["frequency"], routine["description"], routine["sort_order"]),
        )
        for order, (task_id, title, zone) in enumerate(routine["tasks"], start=1):
            category = infer_category(title, zone)
            conn.execute(
                """
                INSERT INTO tasks (id, routine_id, title, zone, category, is_required, sort_order, active)
                VALUES (?, ?, ?, ?, ?, 1, ?, 1)
                ON CONFLICT(id) DO UPDATE SET
                    routine_id = excluded.routine_id,
                    title = excluded.title,
                    zone = excluded.zone,
                    sort_order = excluded.sort_order
                """,
                (task_id, routine["id"], title, zone, category, order),
            )


def seed_admin(conn: sqlite3.Connection) -> None:
    total_users = conn.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
    if total_users > 0:
        return

    admin_user = (os.getenv("ADMIN_USER", "admin").strip().lower() or "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin")
    created_at = iso_now()
    conn.execute(
        """
        INSERT INTO users (username, password_hash, role, is_active, created_at, name)
        VALUES (?, ?, 'admin', 1, ?, ?)
        """,
        (admin_user, hash_password(admin_password, min_length=1), created_at, admin_user),
    )


def create_backup_file(destination: Path, source: str | None = None) -> Path:
    source_path = Path(source or db_path())
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source_path) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)
    return destination


def replace_database_from_file(source: Path, destination: str | None = None) -> None:
    target = Path(destination or db_path())
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_target = target.with_suffix(".restore.tmp")
    shutil.copyfile(source, temp_target)
    temp_target.replace(target)


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]
