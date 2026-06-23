"""Per-month aggregation for the multi-month PowerPoint deck.

Splits a date range into the calendar months it covers and computes, for each
month, the headline metrics + the series the slides chart (daily output, daily
diesel, downtime by category, product mix), plus cross-month trend arrays so the
summary slides can show how the plant is tracking over the period.

Soft-deleted rows are excluded, matching the dashboard KPIs and the other
report builders.
"""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from ..models.production import ProductionShift
from ..models.operations import Delivery
from ..models.target import KpiTarget

MONTHS = ["", "January", "February", "March", "April", "May", "June",
         "July", "August", "September", "October", "November", "December"]


# Downtime cause classifier — same rules as the Downtime dashboard
# (routers/analytics.classify_cause), kept here so the report builder doesn't
# depend on the API layer. Keep the two in sync if the keywords change.
def classify_cause(comment: str) -> str:
    c = (comment or "").lower()
    if "mold" in c and ("change" in c or "mesh" in c):
        return "Mold / Mesh Change"
    if "wash" in c or "clean" in c:
        return "Cleaning / Washing"
    if any(k in c for k in ("pmi", "maintenance", "valve", "pump", "bypass", "restart", "repair")):
        return "Maintenance / Repairs"
    return "Other" if c.strip() else "Unlogged"


CAUSE_ORDER = ["Cleaning / Washing", "Mold / Mesh Change",
               "Maintenance / Repairs", "Other", "Unlogged"]


@dataclass
class MonthData:
    key: str                       # "YYYY-MM"
    label: str                     # "January 2026"
    metrics: dict
    by_day: list                   # [{"day": "01", "qty": .., "fuel": ..}]
    causes: dict                   # {cause: minutes}
    mix: dict                      # {"30's": .., "12's": .., "Hot pressed": .., "Labelled": ..}


@dataclass
class TrendData:
    span: str
    months: list = field(default_factory=list)        # list[MonthData]
    targets: dict = field(default_factory=dict)        # {metric: value}

    @property
    def multi(self) -> bool:
        return len(self.months) > 1


def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _metrics(shifts, deliveries) -> dict:
    tot_qty = sum(s.qty for s in shifts)
    tot_fuel = sum(s.fuel_use for s in shifts)
    tot_down = sum(s.downtime_min for s in shifts)
    tot_sched = sum(s.sched_hours for s in shifts) or 0
    tot_repulp = sum(s.repulped for s in shifts)
    active = len({s.work_date for s in shifts if s.qty > 0})
    speeds = [s.speed for s in shifts if s.speed > 0]
    return {
        "total_qty": round(tot_qty),
        "active_days": active,
        "avg_per_day": round(tot_qty / active) if active else 0,
        "total_fuel": round(tot_fuel),
        "fuel_eff": round(tot_fuel / tot_qty * 1000, 1) if tot_qty else 0,
        "total_downtime_hrs": round(tot_down / 60, 1),
        "downtime_pct": round(tot_down / 60 / tot_sched * 100, 1) if tot_sched else 0,
        "total_repulped": round(tot_repulp),
        "repulp_rate": round(tot_repulp / tot_qty * 100, 1) if tot_qty else 0,
        "avg_speed": round(sum(speeds) / len(speeds)) if speeds else 0,
        "tray30": round(sum(d.tray30 for d in deliveries)),
        "tray12": round(sum(d.tray12n + d.tray12ff for d in deliveries)),
        "pallets": round(sum(d.pallets for d in deliveries)),
        "delivery_count": len(deliveries),
    }


def collect_trend_data(db: Session, start: date | None, end: date | None) -> TrendData:
    """Bucket the range by calendar month and compute per-month detail + trends."""
    sq = db.query(ProductionShift).filter(ProductionShift.deleted_at.is_(None))
    dq = db.query(Delivery).filter(Delivery.deleted_at.is_(None))
    if start:
        sq = sq.filter(ProductionShift.work_date >= start)
        dq = dq.filter(Delivery.work_date >= start)
    if end:
        sq = sq.filter(ProductionShift.work_date <= end)
        dq = dq.filter(Delivery.work_date <= end)
    shifts = sq.order_by(ProductionShift.work_date, ProductionShift.shift).all()
    deliveries = dq.order_by(Delivery.work_date).all()

    # Bucket by month.
    shift_buckets: dict[str, list] = {}
    deliv_buckets: dict[str, list] = {}
    for s in shifts:
        shift_buckets.setdefault(_month_key(s.work_date), []).append(s)
    for d in deliveries:
        deliv_buckets.setdefault(_month_key(d.work_date), []).append(d)

    months: list[MonthData] = []
    for key in sorted(shift_buckets):
        ms = shift_buckets[key]
        md = deliv_buckets.get(key, [])
        y, mn = (int(x) for x in key.split("-"))

        # Daily series (output + diesel), ordered by date.
        day_map: dict[str, dict] = {}
        for s in ms:
            d = day_map.setdefault(s.work_date.isoformat(), {"qty": 0.0, "fuel": 0.0})
            d["qty"] += s.qty
            d["fuel"] += s.fuel_use
        by_day = [{"day": iso[-2:], "qty": v["qty"], "fuel": v["fuel"]}
                  for iso, v in sorted(day_map.items())]

        # Downtime by cause.
        causes: dict[str, float] = {}
        for s in ms:
            if s.downtime_min > 0:
                causes[classify_cause(s.comment)] = causes.get(classify_cause(s.comment), 0) + s.downtime_min

        mix = {
            "30's trays": round(sum(s.p30s + s.p30l for s in ms)),
            "12's cartons": round(sum(s.p12n + s.p12hf + s.p12ff for s in ms)),
            "Hot pressed": round(sum(s.hp1 + s.hp2 + s.hp3 + s.hp4 + s.hp5 + s.hp6 for s in ms)),
            "Labelled": round(sum(s.labelling for s in ms)),
        }

        months.append(MonthData(
            key=key, label=f"{MONTHS[mn]} {y}",
            metrics=_metrics(ms, md), by_day=by_day, causes=causes, mix=mix,
        ))

    targets = {t.metric: t.value for t in db.query(KpiTarget).all()}

    if start and end:
        span = f"{start} to {end}" if start != end else f"{start}"
    elif months:
        span = f"{months[0].label} – {months[-1].label}"
    else:
        span = "All time"

    return TrendData(span=span, months=months, targets=targets)
