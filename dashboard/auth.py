"""
auth.py — HTTP Basic Auth from users.json.

users.json format: {"username": "<bcrypt_hash>", ...}
On first run, if users.json is missing, we fall back to a single user "admin"
with password = SHARED_SECRET env var.
"""
from __future__ import annotations

import base64
import json
import os
from functools import wraps
from pathlib import Path
from typing import Optional

import bcrypt
from flask import Response, request

USERS_FILE = Path(__file__).parent / "users.json"


def _load_users() -> dict[str, str]:
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text())
        except Exception:
            return {}
    return {}


def _check_password(username: str, password: str) -> bool:
    users = _load_users()
    if username in users:
        try:
            return bcrypt.checkpw(password.encode(), users[username].encode())
        except Exception:
            return False
    # Fallback admin user via SHARED_SECRET
    shared = os.environ.get("SHARED_SECRET", "")
    if shared and username == "admin" and password == shared:
        return True
    return False


def _auth_failed() -> Response:
    return Response(
        "Auth required",
        401,
        {"WWW-Authenticate": 'Basic realm="Dashboard"'},
    )


def requires_auth(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        auth = request.authorization
        if not auth or not _check_password(auth.username or "", auth.password or ""):
            return _auth_failed()
        return fn(*args, **kwargs)
    return wrapped


def current_user() -> Optional[str]:
    a = request.authorization
    return a.username if a else None


def hash_password(plaintext: str) -> str:
    """Helper: python -c 'import auth; print(auth.hash_password(\"...\"))'"""
    return bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt()).decode()
