import logging
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from ..core.database import get_db
from ..models.production import ProductionShift
from ..models.user import User, Role
from ..schemas.operations import ShiftCreate, ShiftUpdate, ShiftOut
from ..deps import get_current_user, require_role
from ..services.alerts import evaluate as evaluate_alerts

logger = logging.getLogger("app")

# Hard ceiling on rows returned by a single list call — bounds worst-case
# memory. The response stays a plain JSON array (frontend expects arrays); this
# only truncates, it does not switch to an {items,total} envelope.
MAX_LIMIT = 1000

router = APIRouter(prefix="/api/v1/shifts", tags=["shifts"])


@router.get("", response_model=list[ShiftOut])
def list_shifts(
    start: date | None = Query(None),
    end: date | None = Query(None),
    limit: int = Query(MAX_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(ProductionShift).filter(ProductionShift.deleted_at.is_(None))
    if start:
        q = q.filter(ProductionShift.work_date >= start)
    if end:
        q = q.filter(ProductionShift.work_date <= end)
    q = q.order_by(ProductionShift.work_date, ProductionShift.shift)
    rows = q.offset(offset).limit(limit).all()
    if len(rows) == limit:
        logger.warning("list_shifts truncated at limit=%s offset=%s", limit, offset)
    return rows


@router.post("", response_model=ShiftOut, status_code=201)
def create_shift(body: ShiftCreate, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    exists = db.query(ProductionShift).filter(
        and_(ProductionShift.work_date == body.work_date,
             ProductionShift.shift == body.shift,
             ProductionShift.deleted_at.is_(None))
    ).first()
    if exists:
        raise HTTPException(
            status_code=409,
            detail=f"A {body.shift.value} shift for {body.work_date} already exists",
        )
    shift = ProductionShift(**body.model_dump(), created_by=user.id)
    db.add(shift)
    db.commit()
    db.refresh(shift)

    # Proactive alerting: re-evaluate thresholds after the write. evaluate()
    # never raises (it catches/rolls back internally), but we still guard here
    # so a bug in alerting can NEVER turn a successful shift write into a 500.
    try:
        evaluate_alerts(db)
    except Exception:  # pragma: no cover - defensive; evaluate already suppresses
        logger.exception("post-shift alert evaluation failed (suppressed)")

    return shift


@router.put("/{shift_id}", response_model=ShiftOut)
def update_shift(shift_id: int, body: ShiftUpdate, db: Session = Depends(get_db),
                 user: User = Depends(require_role(Role.supervisor))):
    shift = db.get(ProductionShift, shift_id)
    if not shift or shift.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Shift not found")
    for k, v in body.model_dump().items():
        setattr(shift, k, v)
    db.commit()
    db.refresh(shift)
    return shift


@router.delete("/{shift_id}", status_code=204)
def delete_shift(shift_id: int, db: Session = Depends(get_db),
                 user: User = Depends(require_role(Role.manager))):
    shift = db.get(ProductionShift, shift_id)
    if not shift or shift.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Shift not found")
    # Soft delete: stamp instead of physically removing. The partial unique
    # index (work_date, shift) WHERE deleted_at IS NULL frees the slot so the
    # date+shift can be re-entered, and analytics/list queries skip the row.
    shift.deleted_at = datetime.now(timezone.utc)
    shift.deleted_by = user.id
    db.commit()
