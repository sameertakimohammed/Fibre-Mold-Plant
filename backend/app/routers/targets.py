"""KPI targets — management goals compared against actuals on the dashboard.

Targets are set per (cadence, metric): daily, weekly and monthly. GET is open to
any authenticated user (the dashboard reads them to draw the "vs target"
markers). PUT/DELETE are manager+ only.

Two kinds of metric (see ``METRICS``):

  * volume — a total for one period of that length (trays, litres). Compared
             only against a window of the matching cadence; you can't measure a
             month's output against a daily target.
  * rate   — a ratio independent of period length (L/1,000 trays, downtime %,
             reject %). Comparable against any window; falls back across
             cadences so the marker still shows on a custom range.
"""
import calendar
import logging
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.target import KpiTarget
from ..models.user import User, Role
from ..schemas.operations import TargetIn, TargetOut
from ..deps import get_current_user, require_role

logger = logging.getLogger("app")

router = APIRouter(prefix="/api/v1/targets", tags=["targets"])

# The metrics a target may be set for: key -> (lower_is_better, kind).
# ``kind`` is "volume" (a period total that scales with the cadence) or "rate"
# (a ratio independent of the cadence). Keys match the analytics summary KPIs.
METRICS: dict[str, tuple[bool, str]] = {
    "prod_30":      (False, "volume"),  # 30's Trays output (pcs) — higher better
    "prod_12":      (False, "volume"),  # 12's Cartons output (pcs) — higher better
    "diesel":       (True,  "volume"),  # diesel burned (L) — lower better
    "fuel_eff":     (True,  "rate"),    # L / 1,000 trays — lower better
    "downtime_pct": (True,  "rate"),    # % of scheduled hours — lower better
    "repulp_rate":  (True,  "rate"),    # % of output re-pulped — lower better
}

# Supported cadences. Saturday is a reduced run (2 shifts) so it carries its own
# figures separate from a normal weekday. Order matters for the rate fall-back
# below (prefer the coarsest set value first — monthly is the review basis).
PERIODS: tuple[str, ...] = ("daily", "weekly", "saturday", "monthly")

# Starting targets from the supervisor's "FMP — Production & Diesel Targets"
# workbook (seeded once into an empty table by services.seed; a manager can edit
# any cell afterwards). Bases:
#   * daily    — the KPI document's normal-weekday figures (21 forming hours).
#   * weekly   — Monday–Friday, i.e. 5 normal days (5 × daily).
#   * saturday — the workbook's reduced Saturday run (2 shifts, ~14 h):
#                30's 23,200 · 12's 25,600 · diesel 490 L.
#   * monthly  — the workbook's mix-weighted plan (70/30 trays/cartons, 30 days,
#                4 Saturdays): 30's 619,150 · 12's 292,800 · diesel 21,070 L.
# Rates (fuel_eff/downtime/reject) are the same goal at every cadence.
DEFAULT_TARGETS: dict[str, dict[str, float]] = {
    "prod_30":      {"daily": 30450, "weekly": 152250, "saturday": 23200, "monthly": 619150},
    "prod_12":      {"daily": 33600, "weekly": 168000, "saturday": 25600, "monthly": 292800},
    "diesel":       {"daily": 735,   "weekly": 3675,   "saturday": 490,   "monthly": 21070},
    "fuel_eff":     {"daily": 23.1,  "weekly": 23.1,   "saturday": 23.1,  "monthly": 23.1},
    "downtime_pct": {"daily": 12.5,  "weekly": 12.5,   "saturday": 12.5,  "monthly": 12.5},
    "repulp_rate":  {"daily": 2.0,   "weekly": 2.0,    "saturday": 2.0,   "monthly": 2.0},
}


def infer_period(start: date | None, end: date | None) -> str | None:
    """Map a date window to the cadence whose targets apply to it.

    A single weekday is daily and a single Saturday is its own reduced cadence; a
    Monday–Friday span (5 days) is weekly; a full calendar month is monthly (the
    dashboard's default view). Any other span (a custom range) has no natural
    cadence and returns None — rate targets still compare, volume targets are
    omitted (a 10-day total has no daily/weekly/saturday/monthly target).
    """
    if not start and not end:
        return "monthly"  # no window given == the dashboard's whole-month default
    if not (start and end):
        return None        # one-sided window (open-ended range) has no cadence
    span = (end - start).days + 1
    if span == 1:
        return "saturday" if start.weekday() == 5 else "daily"
    if span == 5 and start.weekday() == 0 and end.weekday() == 4:
        return "weekly"   # Monday–Friday
    if (start.day == 1 and start.year == end.year and start.month == end.month
            and end.day == calendar.monthrange(end.year, end.month)[1]):
        return "monthly"
    return None


def resolve_targets(db: Session, period: str | None) -> dict[str, float]:
    """Flat ``{metric: value}`` to compare against actuals for the given cadence.

    Volume metrics need an exact cadence match. Rate metrics fall back to any
    set cadence (monthly → weekly → daily) so the marker still shows on a custom
    range where ``period`` is None.
    """
    by_metric: dict[str, dict[str, float]] = defaultdict(dict)
    for r in db.query(KpiTarget).all():
        by_metric[r.metric][r.period] = r.value

    out: dict[str, float] = {}
    for metric, (_lower, kind) in METRICS.items():
        vals = by_metric.get(metric)
        if not vals:
            continue
        if kind == "volume":
            if period and period in vals:
                out[metric] = vals[period]
        else:  # rate — exact cadence if set, else any (coarsest first)
            v = vals.get(period) if period else None
            if v is None:
                v = next((vals[p] for p in reversed(PERIODS) if p in vals), None)
            if v is not None:
                out[metric] = v
    return out


@router.get("", response_model=list[TargetOut])
def list_targets(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return (db.query(KpiTarget)
            .order_by(KpiTarget.metric, KpiTarget.period)
            .all())


@router.put("/{period}/{metric}", response_model=TargetOut)
def set_target(period: str, metric: str, body: TargetIn, db: Session = Depends(get_db),
               user: User = Depends(require_role(Role.manager))):
    if period not in PERIODS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown period '{period}'. Allowed: {', '.join(PERIODS)}",
        )
    if metric not in METRICS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown metric '{metric}'. Allowed: {', '.join(METRICS)}",
        )
    row = (db.query(KpiTarget)
           .filter(KpiTarget.metric == metric, KpiTarget.period == period)
           .first())
    if row:
        row.value = body.value
        row.updated_by = user.id
    else:
        row = KpiTarget(metric=metric, period=period, value=body.value, updated_by=user.id)
        db.add(row)
    db.commit(); db.refresh(row)
    return row


@router.delete("/{period}/{metric}", status_code=204)
def clear_target(period: str, metric: str, db: Session = Depends(get_db),
                 _: User = Depends(require_role(Role.manager))):
    row = (db.query(KpiTarget)
           .filter(KpiTarget.metric == metric, KpiTarget.period == period)
           .first())
    if row:
        db.delete(row)
        db.commit()
