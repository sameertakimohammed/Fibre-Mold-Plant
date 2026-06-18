from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..models.audit import AuditLog
from ..models.user import User, Role
from ..schemas.audit import AuditOut, AuditVerifyOut
from ..deps import require_role
from ..services.audit import verify_chain

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("", response_model=list[AuditOut])
def list_audit(
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    action: str | None = Query(None),
    actor: str | None = Query(None, description="Filter by actor username"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.admin)),
):
    """Recent audit rows (newest first), admin only."""
    q = db.query(AuditLog)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        q = q.filter(AuditLog.entity_id == entity_id)
    if action:
        q = q.filter(AuditLog.action == action)
    if actor:
        q = q.filter(AuditLog.actor_username == actor)
    return (
        q.order_by(AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/verify", response_model=AuditVerifyOut)
def verify(db: Session = Depends(get_db), _: User = Depends(require_role(Role.admin))):
    """Walk the hash chain and report integrity (admin only)."""
    return verify_chain(db)
