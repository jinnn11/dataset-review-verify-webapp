from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_session_token, decode_session_token
from app.db.session import get_db
from app.models.user import User, UserRole

DbSession = Annotated[Session, Depends(get_db)]


def set_session_cookie(response: Response, payload: dict[str, str]) -> None:
    token = create_session_token(payload)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.session_max_age_seconds,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")


def get_session_payload(request: Request) -> dict[str, str]:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_session_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    return payload


def get_current_user(request: Request, db: DbSession) -> User:
    payload = get_session_payload(request)
    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    user = db.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_csrf(request: Request) -> dict[str, str]:
    payload = get_session_payload(request)
    csrf_expected = payload.get("csrf")
    csrf_actual = request.headers.get(settings.csrf_header_name)
    if not csrf_expected or csrf_actual != csrf_expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token invalid")
    return payload


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user
