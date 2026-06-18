from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .core.database import get_db
from .core.security import decode_token
from .core.context import AuditActor, set_audit_actor
from .models.user import User, Role

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

ROLE_RANK = {Role.operator: 1, Role.supervisor: 2, Role.manager: 3, Role.admin: 4}


def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise cred_exc
    user = db.query(User).filter(User.username == payload["sub"]).first()
    # is_active check: disabling a user kills their sessions on the next request.
    if not user or not user.is_active:
        raise cred_exc

    # --- Token revocation watermark ---
    # Reject any token issued (iat) BEFORE the user's password_changed_at, so a
    # password change / admin reset invalidates ALL older tokens immediately.
    # iat is a NumericDate (epoch seconds) per RFC 7519; PyJWT returns it as an
    # int. Missing iat (only possible for tokens minted before this change) is
    # treated as not-revoked so we don't lock out mid-shift operators.
    if user.password_changed_at is not None:
        iat = payload.get("iat")
        if iat is not None:
            issued_at = datetime.fromtimestamp(int(iat), tz=timezone.utc)
            pwd_changed = user.password_changed_at
            # DB may return a naive datetime (SQLite); treat naive as UTC.
            if pwd_changed.tzinfo is None:
                pwd_changed = pwd_changed.replace(tzinfo=timezone.utc)
            if issued_at < pwd_changed:
                raise cred_exc
    # Stamp the audit actor for this request so any write captured by the
    # session-event audit writer is attributed to this user (with their IP).
    # IMPORTANT: also stash it on the SESSION (db.info), not only the contextvar.
    # FastAPI runs sync dependencies and the sync endpoint in *separate* threadpool
    # jobs, each with its own copied context — so a ContextVar set here does NOT
    # reach the flush that happens inside the endpoint. The db Session, however, is
    # the same object across the whole request, so session.info is a reliable
    # carrier. (request_id still works via ContextVar because it's set in ASGI
    # middleware, whose context anyio copies into every threadpool job.)
    client_ip = request.client.host if request.client else None
    actor = AuditActor(user_id=user.id, username=user.username, ip=client_ip)
    set_audit_actor(actor)
    db.info["audit_actor"] = actor
    return user


def require_role(min_role: Role):
    def checker(user: User = Depends(get_current_user)) -> User:
        if ROLE_RANK[user.role] < ROLE_RANK[min_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {min_role.value} access or higher",
            )
        return user
    return checker
