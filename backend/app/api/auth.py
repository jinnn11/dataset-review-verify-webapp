from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select

from app.api.deps import DbSession, clear_session_cookie, get_current_user, require_csrf, set_session_cookie
from app.core.security import create_csrf_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, db: DbSession) -> LoginResponse:
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    csrf_token = create_csrf_token()
    set_session_cookie(
        response,
        {
            "user_id": str(user.id),
            "username": user.username,
            "role": user.role.value,
            "csrf": csrf_token,
        },
    )

    return LoginResponse(username=user.username, role=user.role, csrf_token=csrf_token)


@router.post("/logout")
def logout(
    response: Response,
    _: Annotated[dict[str, str], Depends(require_csrf)],
) -> dict[str, str]:
    clear_session_cookie(response)
    return {"status": "ok"}


@router.get("/me", response_model=MeResponse)
def me(user: Annotated[User, Depends(get_current_user)], response: Response) -> MeResponse:
    csrf_token = create_csrf_token()
    set_session_cookie(
        response,
        {
            "user_id": str(user.id),
            "username": user.username,
            "role": user.role.value,
            "csrf": csrf_token,
        },
    )
    return MeResponse(username=user.username, role=user.role, csrf_token=csrf_token)
