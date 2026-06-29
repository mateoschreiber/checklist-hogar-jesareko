import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.auth import create_token, hash_password, token_hash, verify_password


def test_hash_and_verify_password():
    password = "test-password-123"
    hashed = hash_password(password)
    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_password(password, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_hash_password_rejects_short():
    with pytest.raises(ValueError):
        hash_password("abc")


def test_token_hash_requires_secret():
    old = os.environ.get("APP_SECRET")
    os.environ.pop("APP_SECRET", None)
    try:
        import app.auth as auth_mod
        auth_mod._APP_SECRET_CACHE = None
        with pytest.raises(RuntimeError, match="APP_SECRET"):
            token_hash("any-token")
    finally:
        if old is not None:
            os.environ["APP_SECRET"] = old
        auth_mod._APP_SECRET_CACHE = None


def test_token_creation_and_verification():
    os.environ["APP_SECRET"] = "test-secret-for-token"
    import app.auth as auth_mod
    auth_mod._APP_SECRET_CACHE = None

    token, hashed = create_token()
    assert isinstance(token, str)
    assert len(token) > 0
    assert isinstance(hashed, str)
    assert len(hashed) == 64

    verified_hash = token_hash(token)
    assert verified_hash == hashed

    different_hash = token_hash("different-token")
    assert different_hash != hashed


def test_verify_password_edge_cases():
    assert verify_password("anything", "bad-format") is False
    assert verify_password("anything", "x$y$z$w") is False
    hashed = hash_password("valid-pwd-123")
    assert verify_password("valid-pwd-123", hashed) is True
    assert verify_password("Valid-Pwd-123", hashed) is False
