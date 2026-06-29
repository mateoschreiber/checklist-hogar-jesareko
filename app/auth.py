from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

_APP_SECRET_CACHE: str | None = None


def _get_app_secret() -> str:
    global _APP_SECRET_CACHE
    if _APP_SECRET_CACHE is None:
        _APP_SECRET_CACHE = os.getenv("APP_SECRET", "").strip()
    if not _APP_SECRET_CACHE:
        raise RuntimeError("APP_SECRET no esta configurado en las variables de entorno.")
    return _APP_SECRET_CACHE


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def hash_password(password: str, iterations: int = 260_000, min_length: int = 8) -> str:
    if not password or len(password) < min_length:
        raise ValueError(f"La contraseña debe tener al menos {min_length} caracteres.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_hex, digest_hex = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def token_hash(token: str) -> str:
    secret = _get_app_secret()
    return hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()


def create_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(40)
    hashed = token_hash(token)
    return token, hashed


def session_expiry(days: int | None = None) -> str:
    if days is None:
        days = int(os.getenv("SESSION_DAYS", "30"))
    return (utc_now() + timedelta(days=days)).isoformat()
