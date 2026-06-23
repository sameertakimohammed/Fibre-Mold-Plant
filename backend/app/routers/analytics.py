from datetime import date, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..models.production import ProductionShift
from ..models.operations import Delivery, MonthlyStock
from ..models.target import KpiTarget
from ..models.user import User
from ..deps import get_current_user

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

PROD_FIELDS = [
    ("p30s", "30's Small"), ("p30l", "30's Large"), ("p20n", "20's Normal"),
    ("p12n", "12's Normal"), ("p12hf", "12's Half Face"), ("p12ff", "12's Full Face"),
    ("p4cup", "4's Cup"), ("p2cup", "2's Cup"),
]


def classify_cause(comment: str) -> str:
    c = (comment or "").lower()
    if "mold" in c and ("change" in c or "mesh" in c):
        return "Mold / Mesh Change"
    if "wash" in c or "clean" in c:
        return "Cleaning / Washing"
    if any(k in c for k in ("pmi", "maintenance", "valve", "pump", "bypass", "restart", "repair")):
        return "Maintenance / Repairs"
    return "Other" if c.strip() else "Unlogged"


def _aggregate(shifts):
    """Headline totals for a list of shifts (used for current + previous window)."""
    tot_qty = sum(s.qty for s in shifts)
    tot_fuel = sum(s.fuel_use for s in shifts)
    tot_down = sum(s.downtime_min for s in shifts)
    tot_sched = sum(s.sched_hours for s in shifts)
    tot_repulp = sum(s.repulped for s in shifts)
    active = len({s.work_date for s in shifts if s.qty > 0})
    return {
        "total_qty": tot_qty,
        "active_days": active,
        "avg_per_day": tot_qty / active if active else 0,
        "total_fuel": tot_fuel,
        "fuel_eff": (tot_fuel / tot_qty * 1000) if tot_qty else 0,
        "total_downtime_min": tot_down,
        "downtime_pct": (tot_down / 60 / tot_sched * 100) if tot_sched else 0,
        "total_repulped": tot_repulp,
        "repulp_rate": (tot_repulp / tot_qty * 100) if tot_qty else 0,
    }


def _pct(cur, prev):
    if not prev:
        return None
    return (cur - prev) / prev * 100


def _build_insights(shifts, by_day, agg, deliveries) -> list[dict]:
    out = []
    avg = agg["avg_per_day"]
    avg_eff = agg["fuel_eff"]

    # Heavy downtime days (>= 4h)
    heavy = [d for d in by_day if d["down"] >= 240]
    if heavy:
        worst = max(heavy, key=lambda d: d["down"])
        out.append({
            "level": "bad",
            "title": f"{len(heavy)} day(s) lost 4h+ to downtime",
            "detail": f"Worst: {worst['date']} — {round(worst['down'])} min stopped.",
        })

    # Overall downtime rate
    if agg["downtime_pct"] >= 12:
        out.append({
            "level": "warn",
            "title": f"Downtime running at {agg['downtime_pct']:.1f}% of scheduled",
            "detail": "Above the 12% watch line — review the Downtime page for causes.",
        })

    # Fuel efficiency outliers (worse than 1.4x the average)
    if avg_eff:
        bad_fuel = [d for d in by_day if d["qty"] > 0 and d["eff"] > avg_eff * 1.4]
        if bad_fuel:
            w = max(bad_fuel, key=lambda d: d["eff"])
            out.append({
                "level": "warn",
                "title": f"{len(bad_fuel)} day(s) with poor fuel efficiency",
                "detail": f"{w['date']} burned {w['eff']:.0f} L/1k trays vs {avg_eff:.0f} avg.",
            })

    # Low output days (< 60% of average)
    if avg:
        low = [d for d in by_day if 0 < d["qty"] < avg * 0.6]
        if low:
            out.append({
                "level": "warn",
                "title": f"{len(low)} low-output day(s)",
                "detail": f"Below 60% of the {avg:,.0f}/day average — check staffing or stoppages.",
            })

    # Re-pulp / reject rate
    if agg["repulp_rate"] >= 4:
        out.append({
            "level": "warn",
            "title": f"Reject rate at {agg['repulp_rate']:.1f}%",
            "detail": f"{round(agg['total_repulped']):,} trays re-pulped this period.",
        })

    # Positive highlight — best day
    producing = [d for d in by_day if d["qty"] > 0]
    if producing:
        best = max(producing, key=lambda d: d["qty"])
        out.append({
            "level": "good",
            "title": f"Best day: {round(best['qty']):,} trays",
            "detail": f"Achieved on {best['date']}.",
        })

    if not out:
        out.append({"level": "good", "title": "All clear", "detail": "No downtime, fuel, or output flags for this period."})
    return out


@router.get("/summary")
def summary(
    start: date | None = Query(None),
    end: date | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    # Soft-deleted rows must not count toward any KPI.
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

    agg = _aggregate(shifts)

    prod_totals = {k: sum(getattr(s, k) for s in shifts) for k, _ in PROD_FIELDS}
    hp_totals = [sum(getattr(s, f"hp{i}") for s in shifts) for i in range(1, 7)]

    # By day
    day_map = defaultdict(lambda: {"qty": 0.0, "fuel": 0.0, "down": 0.0, "prods": defaultdict(float)})
    for s in shifts:
        d = day_map[s.work_date.isoformat()]
        d["qty"] += s.qty
        d["fuel"] += s.fuel_use
        d["down"] += s.downtime_min
        for k, _ in PROD_FIELDS:
            d["prods"][k] += getattr(s, k)
    by_day = [
        {"date": k, "qty": v["qty"], "fuel": v["fuel"], "down": v["down"],
         "prods": dict(v["prods"]),
         "eff": (v["fuel"] / v["qty"] * 1000) if v["qty"] else 0}
        for k, v in sorted(day_map.items())
    ]

    # By shift
    shift_map = defaultdict(lambda: {"q": 0.0, "d": 0.0, "sched": 0.0, "n": 0})
    for s in shifts:
        m = shift_map[s.shift.value]
        m["q"] += s.qty; m["d"] += s.downtime_min; m["sched"] += s.sched_hours; m["n"] += 1
    by_shift = {k: {**v, "down_pct": (v["d"] / 60 / v["sched"] * 100) if v["sched"] else 0}
                for k, v in shift_map.items()}

    # Downtime causes
    cause_map = defaultdict(float)
    for s in shifts:
        if s.downtime_min > 0:
            cause_map[classify_cause(s.comment)] += s.downtime_min

    # Speed by day
    speed_map = defaultdict(list)
    for s in shifts:
        if s.speed > 0:
            speed_map[s.work_date.isoformat()].append(s.speed)
    speed_by_day = [{"date": k, "speed": sum(v) / len(v)} for k, v in sorted(speed_map.items())]

    # Deliveries
    deliv_30 = sum(d.tray30 for d in deliveries)
    deliv_12 = sum(d.tray12n + d.tray12ff for d in deliveries)
    deliv_pallets = sum(d.pallets for d in deliveries)
    cust_map = defaultdict(float)
    deliv_by_day = defaultdict(float)
    for d in deliveries:
        cust_map[d.company] += d.tray30 + d.tray12n + d.tray12ff
        deliv_by_day[d.work_date.isoformat()] += d.tray30

    # ---- Previous equal-length window → deltas ----
    deltas = None
    if start and end:
        span = (end - start).days + 1
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=span - 1)
        prev_shifts = (db.query(ProductionShift)
                       .filter(ProductionShift.deleted_at.is_(None),
                               ProductionShift.work_date >= prev_start,
                               ProductionShift.work_date <= prev_end)
                       .all())
        if prev_shifts:
            p = _aggregate(prev_shifts)
            deltas = {
                "total_qty": _pct(agg["total_qty"], p["total_qty"]),
                "avg_per_day": _pct(agg["avg_per_day"], p["avg_per_day"]),
                "total_fuel": _pct(agg["total_fuel"], p["total_fuel"]),
                "fuel_eff": _pct(agg["fuel_eff"], p["fuel_eff"]),
                "downtime_pct": (agg["downtime_pct"] - p["downtime_pct"]),  # percentage points
                "total_repulped": _pct(agg["total_repulped"], p["total_repulped"]),
                "prev_label": f"{prev_start.isoformat()} → {prev_end.isoformat()}",
            }

    insights = _build_insights(shifts, by_day, agg, deliveries)

    # ---- Management targets (rates, comparable across any range) ----
    targets = {t.metric: t.value for t in db.query(KpiTarget).all()}

    # ---- Run-rate forecast for an in-progress range (e.g. the current month) ----
    # Projects period output linearly from the elapsed-vs-total calendar days.
    # Only meaningful while the window is still open (today falls inside it).
    forecast = None
    if start and end:
        today = date.today()
        total_days = (end - start).days + 1
        elapsed = (min(end, today) - start).days + 1
        if 0 < elapsed < total_days and agg["total_qty"] > 0:
            forecast = {
                "projected_qty": agg["total_qty"] * total_days / elapsed,
                "elapsed_days": elapsed,
                "total_days": total_days,
                "as_of": min(end, today).isoformat(),
            }

    kpis = {**agg,
            "deliv_30": deliv_30, "deliv_12": deliv_12, "deliv_pallets": deliv_pallets}

    return {
        "kpis": kpis,
        "deltas": deltas,
        "targets": targets,
        "forecast": forecast,
        "insights": insights,
        "prod_totals": prod_totals,
        "prod_labels": {k: n for k, n in PROD_FIELDS},
        "hp_totals": hp_totals,
        "by_day": by_day,
        "by_shift": by_shift,
        "downtime_causes": dict(cause_map),
        "speed_by_day": speed_by_day,
        "deliveries_by_customer": dict(sorted(cust_map.items(), key=lambda x: -x[1])),
        "deliveries_by_day": dict(deliv_by_day),
        "shift_count": len(shifts),
    }


@router.get("/periods")
def periods(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Distinct YYYY-MM periods that have shift data."""
    rows = (db.query(ProductionShift.work_date)
            .filter(ProductionShift.deleted_at.is_(None))
            .all())
    months = sorted({r[0].strftime("%Y-%m") for r in rows}, reverse=True)
    return {"periods": months}
