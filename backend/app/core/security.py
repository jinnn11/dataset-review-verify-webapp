from __future__ import annotations

import secrets
from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
serializer = URLSafeTimedSerializer(settings.secret_key, salt="session-token")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def create_session_token(payload: dict[str, Any]) -> str:
    return serializer.dumps(payload)


def decode_session_token(token: str) -> dict[str, Any] | None:
    try:
        return serializer.loads(token, max_age=settings.session_max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
