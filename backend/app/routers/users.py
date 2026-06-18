import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.security import hash_password
from ..models.user import User, Role
from ..models.production import ProductionShift
from ..models.operations import Delivery, BaleReceipt, FuelDip
from ..schemas.auth import UserCreate, UserUpdate, UserOut
from ..deps import require_role

logger = logging.getLogger("app")

# See shifts.py — bounds worst-case memory; responses stay plain JSON arrays.
MAX_LIMIT = 1000

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(limit: int = Query(MAX_LIMIT, ge=1, le=MAX_LIMIT),
               offset: int = Query(0, ge=0),
               db: Session = Depends(get_db), _: User = Depends(require_role(Role.admin))):
    rows = (db.query(User)
            .order_by(User.username)
            .offset(offset)
            .limit(limit)
            .all())
    if len(rows) == limit:
        logger.warning("list_users truncated at limit=%s offset=%s", limit, offset)
    return rows


@router.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db),
                _: User = Depends(require_role(Role.admin))):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=409, detail="Username already exists")
    user = User(
        username=body.username, full_name=body.full_name,
        hashed_password=hash_password(body.password), role=body.role,
        must_change_password=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db),
                _: User = Depends(require_role(Role.admin))):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password:
        user.hashed_password = hash_password(body.password)
        user.must_change_password = True
        # Admin password reset revokes the user's older tokens (their iat now
        # predates this watermark — see deps.get_current_user).
        user.password_changed_at = datetime.now(timezone.utc)
    # NOTE: role changes (user.role) and deactivation (is_active False) are NOT
    # explicitly audited here. The generic session-event audit writer
    # (services/audit.py) has "User" in its _AUDITED set, so this ORM update is
    # already captured with per-column diffs (e.g. role: [operator, manager],
    # is_active: [true, false]). Adding explicit record_event calls here would
    # DOUBLE-LOG the same change, so we deliberately don't.
    db.commit()
    db.refresh(user)
    return user


def _authored_rows(db: Session, user_id: int) -> bool:
    """True if the user authored any business rows (created_by), so a hard
    delete would orphan history. created_by FKs are ON DELETE SET NULL, but we
    forbid hard-delete anyway and steer admins to deactivation."""
    for model in (ProductionShift, Delivery, BaleReceipt, FuelDip):
        if db.query(model.id).filter(model.created_by == user_id).first():
            return True
    return False


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db),
                admin: User = Depends(require_role(Role.admin))):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    if _authored_rows(db, user_id):
        raise HTTPException(
            status_code=400,
            detail=("This user has authored production/operations records and "
                    "cannot be deleted (it would erase that authorship history). "
                    "Deactivate the account instead (set is_active = false)."),
        )
    db.delete(user)
    db.commit()
