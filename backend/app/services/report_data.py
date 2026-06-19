"""Single source of truth for report figures.

Every report format (xlsx / pdf / pptx) and the scheduled report-email job pull
their numbers from collect_report_data() so the three downloads and the emailed
copy can never disagree. Soft-deleted rows are excluded so totals match the
dashboard KPIs (which apply the same filter).
"""
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from ..models.production import ProductionShift
from ..models.operations import Delivery


@dataclass
class ReportData:
    start: date | None
    end: date | None
    period_label: str          # "Daily" | "Weekly" | "Monthly" | "Production"
    span: str                  # human-readable date span for titles
    shifts: list               # ProductionShift rows, date+shift ordered
    deliveries: list           # Delivery rows, date ordered
    metrics: dict              # pre-rounded KPI numbers (see below)


def _span_text(start: date | None, end: date | None) -> str:
    if start and end:
        return f"{start} to {end}" if start != end else f"{start}"
    if start:
        return f"from {start}"
    if end:
        return f"through {end}"
    return "All time"


def collect_report_data(
    db: Session,
    start: date | None = None,
    end: date | None = None,
    period_label: str = "Production",
) -> ReportData:
    """Load shifts + deliveries for the range and compute the KPI block once."""
    q = db.query(ProductionShift).filter(ProductionShift.deleted_at.is_(None))
    if start:
        q = q.filter(ProductionShift.work_date >= start)
    if end:
        q = q.filter(ProductionShift.work_date <= end)
    shifts = q.order_by(ProductionShift.work_date, ProductionShift.shift).all()

    dq = db.query(Delivery).filter(Delivery.deleted_at.is_(None))
    if start:
        dq = dq.filter(Delivery.work_date >= start)
    if end:
        dq = dq.filter(Delivery.work_date <= end)
    deliveries = dq.order_by(Delivery.work_date).all()

    tot_qty = sum(s.qty for s in shifts)
    tot_fuel = sum(s.fuel_use for s in shifts)
    tot_down = sum(s.downtime_min for s in shifts)
    tot_sched = sum(s.sched_hours for s in shifts) or 0
    tot_repulp = sum(s.repulped for s in shifts)
    active = len({s.work_date for s in shifts if s.qty > 0})

    metrics = {
        "total_qty": round(tot_qty),
        "active_days": active,
        "avg_per_day": round(tot_qty / active) if active else 0,
        "total_fuel": round(tot_fuel),
        "fuel_eff": round(tot_fuel / tot_qty * 1000, 1) if tot_qty else 0,
        "total_downtime_hrs": round(tot_down / 60, 1),
        "downtime_pct": round(tot_down / 60 / tot_sched * 100, 1) if tot_sched else 0,
        "total_repulped": round(tot_repulp),
        "repulp_rate": round(tot_repulp / tot_qty * 100, 1) if tot_qty else 0,
        "tray30": round(sum(d.tray30 for d in deliveries)),
        "tray12": round(sum(d.tray12n + d.tray12ff for d in deliveries)),
        "pallets": round(sum(d.pallets for d in deliveries)),
        "delivery_count": len(deliveries),
        "shift_count": len(shifts),
    }

    return ReportData(
        start=start,
        end=end,
        period_label=period_label or "Production",
        span=_span_text(start, end),
        shifts=shifts,
        deliveries=deliveries,
        metrics=metrics,
    )


def report_filename(ext: str, start: date | None, end: date | None,
                    period_label: str = "report") -> str:
    """Build a tidy download name, e.g. FMP-Monthly-2026-05-01_2026-05-31.pdf."""
    label = (period_label or "report").strip().lower().replace(" ", "")
    if start and end and start != end:
        stamp = f"{start}_{end}"
    elif start:
        stamp = f"{start}"
    elif end:
        stamp = f"{end}"
    else:
        stamp = "all"
    return f"FMP-{label}-{stamp}.{ext}"
