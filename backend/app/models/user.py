import enum
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Integer, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class Role(str, enum.Enum):
    operator = "operator"      # log shifts only
    supervisor = "supervisor"  # log + edit recent + view all
    manager = "manager"        # view all analytics, no destructive edits
    admin = "admin"            # full control incl. user management


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(SAEnum(Role), default=Role.operator)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    auth_source: Mapped[str] = mapped_column(String(20), default="local")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # --- Auth hardening (wave 3) ---
    # Consecutive failed login attempts; reset to 0 on a successful login.
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # When set and in the future, login is blocked (HTTP 429) until this UTC
    # instant — guards against brute force AND shields the real AD account from
    # repeated bad binds.
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Last successful login (for the admin UI / audit).
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Token-revocation watermark: any access token whose iat is BEFORE this
    # instant is rejected by get_current_user. Set on password change / admin
    # password reset so older tokens stop working. Backfilled to created_at by
    # the migration so existing tokens aren't invalidated when this goes live.
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
