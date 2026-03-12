from pydantic import BaseModel

from app.models.user import UserRole


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    username: str
    role: UserRole
    csrf_token: str


class MeResponse(BaseModel):
    username: str
    role: UserRole
    csrf_token: str
