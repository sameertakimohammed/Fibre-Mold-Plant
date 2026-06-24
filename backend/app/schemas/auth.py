from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, field_validator
from ..models.user import Role

# Minimum password length (NIST 800-63B floor). Enforced on create + change.
MIN_PASSWORD_LEN = 8


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
    full_name: str
    username: str
    must_change_password: bool


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    full_name: str
    password: Annotated[str, Field(min_length=MIN_PASSWORD_LEN)]
    role: Role = Role.operator

    @field_validator("username")
    @classmethod
    def _normalize_username(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("username must not be blank")
        return v


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: Role | None = None
    is_active: bool | None = None
    # Admin-initiated password reset. None means "leave unchanged"; when a value
    # is supplied it must meet the same 8-char floor as create / self-change.
    password: Annotated[str, Field(min_length=MIN_PASSWORD_LEN)] | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: Annotated[str, Field(min_length=MIN_PASSWORD_LEN)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    full_name: str
    role: Role
    is_active: bool
    must_change_password: bool
    auth_source: str = "local"
    created_at: datetime
    # Auth-hardening fields surfaced to the admin UI. hashed_password is NEVER
    # exposed here. password_changed_at is intentionally omitted (internal
    # revocation watermark, not useful in the UI).
    last_login_at: datetime | None = None
    locked_until: datetime | None = None
    failed_login_count: int = 0
