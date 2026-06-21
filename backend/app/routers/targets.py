"""KPI targets — management goals compared against actuals on the dashboard.

GET is open to any authenticated user (the dashboard reads them to draw the "vs
target" markers). PUT is manager+ only. Targets are stored as rates (see
models/target.KpiTarget) so they compare across any date range.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.target import KpiTarget
from ..models.user import User, Role
from ..schemas.operations import TargetIn, TargetOut
from ..deps import get_current_user, require_role

logger = logging.getLogger("app")

router = APIRouter(prefix="/api/v1/targets", tags=["targets"])

# The metrics a target may be set for, with whether lower is better (used by the
# UI to colour attainment). Keys match the analytics summary KPI block.
ALLOWED_METRICS: dict[str, bool] = {
    "avg_per_day": False,    # trays/active day — higher is better
    "fuel_eff": True,        # L/1,000 trays — lower is better
    "downtime_pct": True,    # % of scheduled — lower is better
    "repulp_rate": True,     # % of output re-pulped — lower is better
}


@router.get("", response_model=list[TargetOut])
def list_targets(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(KpiTarget).order_by(KpiTarget.metric).all()


@router.put("/{metric}", response_model=TargetOut)
def set_target(metric: str, body: TargetIn, db: Session = Depends(get_db),
               user: User = Depends(require_role(Role.manager))):
    if metric not in ALLOWED_METRICS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown metric '{metric}'. Allowed: {', '.join(ALLOWED_METRICS)}",
        )
    row = db.query(KpiTarget).filter(KpiTarget.metric == metric).first()
    if row:
        row.value = body.value
        row.updated_by = user.id
    else:
        row = KpiTarget(metric=metric, value=body.value, updated_by=user.id)
        db.add(row)
    db.commit(); db.refresh(row)
    return row


@router.delete("/{metric}", status_code=204)
def clear_target(metric: str, db: Session = Depends(get_db),
                 _: User = Depends(require_role(Role.manager))):
    row = db.query(KpiTarget).filter(KpiTarget.metric == metric).first()
    if row:
        db.delete(row)
        db.commit()
