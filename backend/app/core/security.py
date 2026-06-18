import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt  # PyJWT (replaces python-jose)
from passlib.context import CryptContext
from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, role: str, expires_minutes: Optional[int] = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload = {
        "sub": subject,
        "role": role,
        # iat: when the token was issued. Used for revocation — a token whose
        # iat predates the user's password_changed_at is rejected (see deps.py).
        "iat": now,
        # jti: unique token id (uuid4 hex), enabling future per-token blocklists.
        "jti": uuid.uuid4().hex,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> Optional[dict]:
    """Decode + verify a JWT. Returns None on ANY failure (expired signature,
    bad signature, malformed token, wrong claims) so callers can treat a falsy
    result as 'invalid credentials' without leaking the failure reason."""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except (jwt.PyJWTError, ValueError):
        return None
