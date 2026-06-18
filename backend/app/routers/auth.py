import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.security import verify_password, create_access_token, hash_password
from ..core.config import settings
from ..core.context import AuditActor, set_audit_actor
from ..models.user import User, Role
from ..schemas.auth import Token, UserOut, PasswordChange
from ..deps import get_current_user
from ..services.audit import record_event
from ..core.ratelimit import limiter

logger = logging.getLogger("app")

# API v1. Breaking changes go to a future /api/v2; /api/v1/ingest/* is reserved
# for the future machine-data collector.
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Role precedence for resolving the HIGHEST AD-mapped role when a user is in
# several mapped groups.
_ROLE_RANK = {Role.operator: 1, Role.supervisor: 2, Role.manager: 3, Role.admin: 4}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _record_login(db: Session, ip: str | None, ok: bool, username: str,
                  user: User | None, action: str | None = None,
                  changes: dict | None = None) -> None:
    """Append a login audit row in its own commit.

    action defaults to login.success / login.fail; pass an explicit action
    (e.g. 'login.locked') to override. changes is merged with the username.
    """
    # Login runs before get_current_user, so set the actor explicitly.
    set_audit_actor(AuditActor(
        user_id=user.id if user else None,
        username=user.username if user else None,
        ip=ip,
    ))
    payload = {"username": username}
    if changes:
        payload.update(changes)
    record_event(
        db,
        action=action or ("login.success" if ok else "login.fail"),
        entity_type="Auth",
        entity_id=str(user.id) if user else None,
        changes=payload,
        actor_id=user.id if user else None,
        actor_username=user.username if user else username,
    )
    db.commit()


def _locked_remaining_minutes(user: User) -> int | None:
    """Minutes until the lock expires, or None if not currently locked."""
    if user.locked_until is None:
        return None
    locked_until = user.locked_until
    if locked_until.tzinfo is None:          # SQLite returns naive UTC
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    delta = locked_until - _now()
    if delta.total_seconds() <= 0:
        return None
    # Round up so "try again in N minutes" never under-promises.
    return max(1, int(delta.total_seconds() // 60) + 1)


def _register_failure(db: Session, user: User) -> bool:
    """Increment a KNOWN user's failure counter and lock when the threshold
    trips. Returns True if this failure caused a lockout. Caller commits via
    _record_login."""
    user.failed_login_count = (user.failed_login_count or 0) + 1
    locked = False
    if user.failed_login_count >= settings.lockout_threshold:
        user.locked_until = _now() + timedelta(minutes=settings.lockout_minutes)
        locked = True
    return locked


def _register_success(user: User) -> None:
    """Reset lockout state and stamp last_login_at on a successful login."""
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = _now()


def _ldap_bind(username: str, password: str) -> bool:
    """Try authenticating username/password against the configured AD server."""
    try:
        from ldap3 import Server, Connection, ALL
        server = Server(settings.ad_server, get_info=ALL, connect_timeout=5)
        upn = f"{username}@{settings.ad_domain}"
        conn = Connection(server, user=upn, password=password, auto_bind=True, receive_timeout=5)
        conn.unbind()
        return True
    except Exception:
        return False


def _parse_group_role_map() -> dict[str, Role]:
    """Parse AD_GROUP_ROLE_MAP ("GroupCN=role,...") into {cn_lower: Role}.
    Unknown role names are skipped (logged once) so a typo can't crash login."""
    mapping: dict[str, Role] = {}
    raw = settings.ad_group_role_map or ""
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        cn, _, role_name = pair.partition("=")
        cn = cn.strip().lower()
        role_name = role_name.strip().lower()
        if not cn:
            continue
        try:
            mapping[cn] = Role(role_name)
        except ValueError:
            logger.warning("[ad] AD_GROUP_ROLE_MAP has unknown role '%s' for group '%s' — ignored",
                           role_name, cn)
    return mapping


def _ad_member_group_cns(username: str, password: str) -> list[str]:
    """Bind as the user and read their memberOf group CNs under ad_base_dn.

    Best-effort: returns [] on ANY failure so an LDAP hiccup never breaks login
    for a user who has already bound successfully. Re-binds with the user's own
    credentials (no service account needed)."""
    cns: list[str] = []
    try:
        from ldap3 import Server, Connection, ALL, SUBTREE
        server = Server(settings.ad_server, get_info=ALL, connect_timeout=5)
        upn = f"{username}@{settings.ad_domain}"
        conn = Connection(server, user=upn, password=password,
                          auto_bind=True, receive_timeout=5)
        try:
            # sAMAccountName match is the most reliable across AD setups.
            conn.search(
                search_base=settings.ad_base_dn,
                search_filter=f"(sAMAccountName={username})",
                search_scope=SUBTREE,
                attributes=["memberOf"],
            )
            for entry in conn.entries:
                member_of = entry.memberOf.values if "memberOf" in entry else []
                for dn in member_of:
                    # dn looks like "CN=Fibre-Admins,OU=Groups,DC=golden,DC=com,DC=fj"
                    first = dn.split(",", 1)[0]
                    if first.upper().startswith("CN="):
                        cns.append(first[3:].strip().lower())
        finally:
            conn.unbind()
    except Exception as exc:  # noqa: BLE001 — resilience is the point
        logger.warning("[ad] group lookup failed for '%s' (login still allowed): %s",
                       username, exc)
    return cns


def _resolve_ad_role(group_cns: list[str], mapping: dict[str, Role]) -> Role | None:
    """Highest mapped role among the user's groups, or None if none match."""
    matched = [mapping[cn] for cn in group_cns if cn in mapping]
    if not matched:
        return None
    return max(matched, key=lambda r: _ROLE_RANK[r])


def _sync_ad_role(db: Session, user: User, username: str, password: str,
                  ip: str | None) -> bool:
    """Re-sync role (and strict-mode access) from AD groups on every login.

    Returns True if the user is allowed to proceed, False if strict-mode denied
    them (caller then raises 403). No-op (returns True) when AD_GROUP_ROLE_MAP
    is empty — legacy behaviour (role stays app-managed). Audits role changes
    and strict-mode deactivation. Wrapped defensively so an LDAP hiccup never
    blocks a user who already bound."""
    mapping = _parse_group_role_map()
    if not mapping:
        return True  # group mapping not configured -> keep legacy behaviour

    group_cns = _ad_member_group_cns(username, password)
    resolved = _resolve_ad_role(group_cns, mapping)

    if resolved is None:
        if settings.ad_group_strict:
            if user.is_active:
                user.is_active = False
                record_event(
                    db, action="user.deactivate", entity_type="User",
                    entity_id=str(user.id),
                    changes={"reason": "ad_group_strict: user in no mapped group"},
                    actor_id=None, actor_username=username,
                )
                logger.warning("[ad] strict mode disabled '%s' (no mapped group)", username)
            return False
        # Non-strict: leave role/access as-is.
        return True

    # Re-sync the role if AD says it changed.
    if user.role != resolved:
        old = user.role.value
        user.role = resolved
        record_event(
            db, action="user.role_change", entity_type="User",
            entity_id=str(user.id),
            changes={"role": [old, resolved.value], "source": "ad_group_sync"},
            actor_id=None, actor_username=username,
        )
        logger.info("[ad] re-synced role for '%s': %s -> %s", username, old, resolved.value)
    # A previously strict-denied user who is now in a mapped group is re-enabled.
    if not user.is_active and settings.ad_group_strict:
        user.is_active = True
    return True


def _is_local_bypass(username: str) -> bool:
    bypassed = {u.strip().lower() for u in settings.ad_local_bypass.split(",") if u.strip()}
    return username.lower() in bypassed


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(),
          db: Session = Depends(get_db)):
    username = form.username.strip()
    ip = request.client.host if request.client else None

    # Resolve the user up front (case-sensitive, matching existing behaviour) so
    # we can enforce lockout BEFORE any AD bind. Lockout tracking applies only to
    # KNOWN users; unknown usernames keep returning the generic 401 with no row
    # created (so we never leak existence and never grow junk rows).
    user = db.query(User).filter(User.username == username).first()

    # --- LOCKOUT GATE (runs BEFORE the AD/LDAP bind) ---
    # Checking this first means repeated failures never hammer or lock out the
    # real Windows domain account: once locked here, we short-circuit and never
    # reach _ldap_bind. Auto-unlocks once locked_until passes.
    if user is not None:
        remaining = _locked_remaining_minutes(user)
        if remaining is not None:
            _record_login(db, ip, ok=False, username=username, user=user,
                          action="login.locked",
                          changes={"locked_minutes_remaining": remaining})
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account temporarily locked, try again in {remaining} minutes",
            )

    use_ad = settings.ad_enabled and not _is_local_bypass(username)

    if use_ad:
        # --- Active Directory path ---
        if not _ldap_bind(username, form.password):
            # Track failures only for KNOWN users (don't auto-create rows for
            # unknown usernames, and don't reveal existence beyond the 401).
            locked = _register_failure(db, user) if user is not None else False
            _record_login(
                db, ip, ok=False, username=username, user=user,
                changes={"locked": True, "lockout_minutes": settings.lockout_minutes}
                if locked else None,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
            )
        # Bind OK. Auto-provision the AD user on first login.
        if not user:
            user = User(
                username=username,
                full_name=username,          # admin can update the display name later
                hashed_password="",          # not used for AD accounts
                role=Role.operator,
                auth_source="ad",
                must_change_password=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        # Re-sync role / strict-mode access from AD groups (no-op if map unset).
        allowed = _sync_ad_role(db, user, username, form.password, ip)
        if not allowed:
            db.commit()  # persist the strict-mode deactivation + its audit row
            _record_login(db, ip, ok=False, username=username, user=user)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
        if not user.is_active:
            _record_login(db, ip, ok=False, username=username, user=user)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    else:
        # --- Local password path (also the AD_LOCAL_BYPASS break-glass admin) ---
        if not user or not verify_password(form.password, user.hashed_password):
            locked = _register_failure(db, user) if user is not None else False
            _record_login(
                db, ip, ok=False, username=username, user=user,
                changes={"locked": True, "lockout_minutes": settings.lockout_minutes}
                if locked else None,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
            )
        if not user.is_active:
            _record_login(db, ip, ok=False, username=username, user=user)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    # --- SUCCESS: reset lockout state, stamp last_login_at ---
    _register_success(user)
    _record_login(db, ip, ok=True, username=username, user=user)
    token = create_access_token(subject=user.username, role=user.role.value)
    return Token(
        access_token=token, role=user.role, full_name=user.full_name,
        username=user.username, must_change_password=user.must_change_password,
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password")
def change_password(body: PasswordChange, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if user.auth_source == "ad":
        raise HTTPException(
            status_code=400,
            detail="Password is managed by Active Directory. Change it via Windows or contact IT.",
        )
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    user.hashed_password = hash_password(body.new_password)
    user.must_change_password = False
    # Revoke all tokens issued before now (their iat predates this instant).
    user.password_changed_at = _now()
    db.commit()
    return {"detail": "Password updated"}
