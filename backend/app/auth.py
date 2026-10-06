"""Token sesi untuk demo lokal.

Ini bukan autentikasi produksi. Sebelum dipakai di jaringan kantor,
ganti dengan penyedia identitas resmi dan simpan sandi memakai argon2.
"""

from __future__ import annotations

from typing import Optional

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

SECRET = os.environ.get("BI_AUTH_SECRET", "dev-only-change-me")
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return hashlib.sha256(f"bi-mvp-v1|{password}".encode()).hexdigest()


def verify_password(password: str, stored: str) -> bool:
    return hmac.compare_digest(hash_password(password), stored)


@dataclass
class CurrentUser:
    username: str
    full_name: str
    role: str


def create_token(user: User) -> str:
    exp = int((datetime.now() + timedelta(hours=12)).timestamp())
    payload = f"{user.username}|{user.role}|{exp}"
    sign = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    raw = f"{payload}|{sign}".encode()
    return base64.urlsafe_b64encode(raw).decode()


def _decode(token: str) -> CurrentUser:
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        username, role, exp, sign = raw.split("|")
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=401, detail="Sesi tidak valid") from None
    payload = f"{username}|{role}|{exp}"
    expected = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sign):
        raise HTTPException(status_code=401, detail="Sesi tidak valid")
    if int(exp) < int(datetime.now().timestamp()):
        raise HTTPException(status_code=401, detail="Sesi habis. Masuk kembali.")
    return CurrentUser(username=username, full_name="", role=role)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Masuk diperlukan")
    parsed = _decode(credentials.credentials)
    user = db.query(User).filter(User.username == parsed.username).one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Pengguna tidak ditemukan")
    parsed.full_name = user.full_name
    parsed.role = user.role
    return parsed


def require_writer(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role not in {"admin", "analis"}:
        raise HTTPException(status_code=403, detail="Peran pimpinan hanya dapat melihat data")
    return user


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Hanya admin yang dapat mengubah pengaturan ini")
    return user
