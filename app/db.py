from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Iterable

from .auth import hash_password, iso_now
from .checklist_seed import ROUTINES

DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/checklist.db")


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


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
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
                sort_order INTEGER NOT NULL
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
                server_closed_at TEXT NOT NULL
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

            CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
            CREATE INDEX IF NOT EXISTS idx_runs_user_date ON runs(user_id, server_closed_at DESC);
            CREATE INDEX IF NOT EXISTS idx_run_tasks_run ON run_tasks(run_id);
            """
        )
        seed_checklist(conn)
        seed_admin(conn)


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
            conn.execute(
                """
                INSERT INTO tasks (id, routine_id, title, zone, sort_order)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    routine_id = excluded.routine_id,
                    title = excluded.title,
                    zone = excluded.zone,
                    sort_order = excluded.sort_order
                """,
                (task_id, routine["id"], title, zone, order),
            )


def seed_admin(conn: sqlite3.Connection) -> None:
    total_users = conn.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
    if total_users > 0:
        return

    admin_email = os.getenv("ADMIN_EMAIL", "admin@hogar.local").strip().lower()
    admin_password = os.getenv("ADMIN_PASSWORD", "Cambiar-esta-clave-123")
    admin_name = os.getenv("ADMIN_NAME", "Administrador").strip() or "Administrador"

    conn.execute(
        """
        INSERT INTO users (name, email, password_hash, role, is_active, created_at)
        VALUES (?, ?, ?, 'admin', 1, ?)
        """,
        (admin_name, admin_email, hash_password(admin_password), iso_now()),
    )


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]
