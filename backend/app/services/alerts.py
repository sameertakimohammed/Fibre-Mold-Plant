"""Proactive threshold alerting.

Reuses the analytics KPI logic (_aggregate, per-day rollups) so dashboard
insights and proactive alerts agree, and turns threshold breaches into
``Notification`` rows. Thresholds come from settings (defaults mirror
analytics._build_insights).

DEDUP STRATEGY
--------------
Every alert has a stable ``dedup_key`` of the form ``"<category>:<scope>"`` —
usually ``"<category>:<date>"`` for a specific day, or ``"<category>:<period>"``
for a whole-window rate. Before inserting, we check whether a Notification with
that key already exists within a recent lookback window; if so we skip. So the
SAME issue is not re-inserted on every post-write / daily run.

RESILIENCE
----------
evaluate() catches everything and never raises, so it is safe to call from the
shift-create path (a failed alert pass must never break the write) and from the
scheduler. It opens nothing — the caller passes the Session. For the scheduler
job that owns its own session, see scheduler.py.

Categories produced: 'downtime' (heavy-day + rate), 'fuel', 'output',
'missed_shift'. ('backup' and 'integration' are reserved for other producers.)
"""
import logging
from collections import defaultdict
from datetime import date, datetime, timezone, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.production import ProductionShift
from ..models.notification import Notification
from ..routers.analytics import _aggregate
from .email import send_email

logger = logging.getLogger("app.alerts")


# Severity ranking used to decide which alerts trigger an email.
_EMAILABLE = {"warn", "critical"}


def _recent_dedup_exists(db: Session, dedup_key: str, since: datetime) -> bool:
    """True if a notification with this dedup_key was created at/after `since`."""
    return (
        db.query(Notification.id)
        .filter(
            Notification.dedup_key == dedup_key,
            Notification.created_at >= since,
        )
        .first()
        is not None
    )


def _maybe_add(db, created, severity, category, message, dedup_key, dedup_since):
    """Append a Notification if no recent row shares its dedup_key.

    Mutates `created` (the list of newly-added Notification objects) and returns
    nothing. Caller commits.
    """
    if dedup_key and _recent_dedup_exists(db, dedup_key, dedup_since):
        return
    n = Notification(
        severity=severity,
        category=category,
        message=message,
        dedup_key=dedup_key,
    )
    db.add(n)
    created.append(n)


def _per_day(shifts):
    """Per-day rollup mirroring analytics.summary by_day (qty/fuel/down/eff)."""
    day_map = defaultdict(lambda: {"qty": 0.0, "fuel": 0.0, "down": 0.0})
    for s in shifts:
        d = day_map[s.work_date.isoformat()]
        d["qty"] += s.qty
        d["fuel"] += s.fuel_use
        d["down"] += s.downtime_min
    return [
        {"date": k, "qty": v["qty"], "fuel": v["fuel"], "down": v["down"],
         "eff": (v["fuel"] / v["qty"] * 1000) if v["qty"] else 0}
        for k, v in sorted(day_map.items())
    ]


def evaluate(db: Session, today: date | None = None) -> list[Notification]:
    """Run all alert checks over the recent window; insert deduped Notifications.

    Returns the list of newly-created Notification rows (may be empty). Never
    raises — any error is logged and an empty list is returned so callers (shift
    create, scheduler) are never broken by alerting.
    """
    try:
        today = today or datetime.now(timezone.utc).date()
        window_days = settings.alert_window_days
        start = today - timedelta(days=window_days)

        shifts = (
            db.query(ProductionShift)
            .filter(
                ProductionShift.deleted_at.is_(None),
                ProductionShift.work_date >= start,
                ProductionShift.work_date <= today,
            )
            .order_by(ProductionShift.work_date, ProductionShift.shift)
            .all()
        )

        created: list[Notification] = []
        if not shifts:
            return created

        agg = _aggregate(shifts)
        by_day = _per_day(shifts)
        avg = agg["avg_per_day"]
        avg_eff = agg["fuel_eff"]

        # Dedup lookback: a per-day key is unique to its date, so a generous
        # window (2x the scan window) just means "don't re-raise the same day".
        dedup_since = datetime.now(timezone.utc) - timedelta(days=window_days * 2)
        # Rate alerts are scoped to the current period end-date so they re-raise
        # at most once per day rather than every post-write run.
        period_scope = today.isoformat()

        # --- Heavy downtime day(s) ---
        for d in by_day:
            if d["down"] >= settings.alert_heavy_downtime_min:
                _maybe_add(
                    db, created, "critical", "downtime",
                    f"Heavy downtime on {d['date']}: {round(d['down'])} min stopped "
                    f"(>= {round(settings.alert_heavy_downtime_min)} min).",
                    f"downtime:{d['date']}", dedup_since,
                )

        # --- Overall downtime rate ---
        if agg["downtime_pct"] >= settings.alert_downtime_pct:
            _maybe_add(
                db, created, "warn", "downtime",
                f"Downtime running at {agg['downtime_pct']:.1f}% of scheduled over the "
                f"last {window_days} days — above the {settings.alert_downtime_pct:.0f}% watch line.",
                f"downtime_rate:{period_scope}", dedup_since,
            )

        # --- Fuel efficiency outliers (worse than mult x average) ---
        if avg_eff:
            for d in by_day:
                if d["qty"] > 0 and d["eff"] > avg_eff * settings.alert_fuel_eff_mult:
                    _maybe_add(
                        db, created, "warn", "fuel",
                        f"Poor fuel efficiency on {d['date']}: {d['eff']:.0f} L/1k trays "
                        f"vs {avg_eff:.0f} avg.",
                        f"fuel:{d['date']}", dedup_since,
                    )

        # --- Low-output days (< frac of average) ---
        if avg:
            for d in by_day:
                if 0 < d["qty"] < avg * settings.alert_low_output_frac:
                    _maybe_add(
                        db, created, "warn", "output",
                        f"Low output on {d['date']}: {round(d['qty']):,} trays — below "
                        f"{settings.alert_low_output_frac*100:.0f}% of the {avg:,.0f}/day average.",
                        f"output:{d['date']}", dedup_since,
                    )

        # --- Re-pulp / reject rate ---
        if agg["repulp_rate"] >= settings.alert_reject_pct:
            _maybe_add(
                db, created, "warn", "output",
                f"Reject rate at {agg['repulp_rate']:.1f}% over the last {window_days} days "
                f"({round(agg['total_repulped']):,} trays re-pulped).",
                f"reject_rate:{period_scope}", dedup_since,
            )

        # --- Missed shift (best-effort) ---
        # Intent: "the plant has been logging daily, but a recent day was
        # skipped." We anchor on the most-recent shift overall (not just the
        # window). If the latest data is OLDER than the scan window, the plant is
        # not in active daily-logging mode (historical import, shutdown, seasonal
        # gap) and flagging every empty day would be pure noise — so we skip
        # missed-shift detection entirely. Otherwise we only check days AFTER the
        # last logged day up to the grace cutoff, so we never nag about the long
        # void before logging started.
        grace = settings.alert_missed_shift_grace_days
        expected = settings.alert_expected_shifts_per_day
        last_shift_date = (
            db.query(func.max(ProductionShift.work_date))
            .filter(ProductionShift.deleted_at.is_(None))
            .scalar()
        )
        if last_shift_date is not None and (today - last_shift_date).days <= window_days:
            counts: dict[date, int] = defaultdict(int)
            for s in shifts:
                counts[s.work_date] += 1
            check_start = last_shift_date + timedelta(days=1)
            check_end = today - timedelta(days=grace)
            d = check_start
            while d <= check_end:
                if counts.get(d, 0) < expected:
                    _maybe_add(
                        db, created, "warn", "missed_shift",
                        f"No production shift logged for {d.isoformat()} "
                        f"(expected at least {expected}).",
                        f"missed_shift:{d.isoformat()}", dedup_since,
                    )
                d += timedelta(days=1)

        if created:
            db.commit()
            for n in created:
                db.refresh(n)
            logger.info("alerts: created %d notification(s)", len(created))
            _email_alerts(db, created)
        return created
    except Exception:
        logger.exception("alert evaluation failed (suppressed)")
        try:
            db.rollback()
        except Exception:
            pass
        return []


def _email_alerts(db: Session, created: list[Notification]) -> None:
    """Email warn/critical alerts to alert_email_to with per-key cooldown.

    Reuses the dedup_key concept: an email is only sent if no email-dedup row
    ("email:<dedup_key>") was created within the cooldown window. We record the
    send as an 'integration'/info Notification so the cooldown is durable across
    process restarts. Wrapped so email never breaks alerting.
    """
    try:
        emailable = [n for n in created if n.severity in _EMAILABLE]
        if not emailable:
            return
        from .email import email_configured
        if not email_configured() or not settings.alert_email_to:
            return

        cooldown_since = datetime.now(timezone.utc) - timedelta(
            minutes=settings.alert_email_cooldown_min
        )
        to_send = []
        for n in emailable:
            email_key = f"email:{n.dedup_key}" if n.dedup_key else None
            if email_key and _recent_dedup_exists(db, email_key, cooldown_since):
                continue
            to_send.append(n)

        if not to_send:
            return

        lines = [f"[{n.severity.upper()}] {n.message}" for n in to_send]
        body = (
            "Fibre Mold Plant — automated alert(s):\n\n"
            + "\n".join(lines)
            + "\n\nThis is an automated message from the plant dashboard."
        )
        subject = f"Fibre Mold Plant: {len(to_send)} alert(s)"
        sent = send_email(subject, body, settings.alert_email_to)

        if sent:
            # Record cooldown markers so repeats are suppressed across runs.
            for n in to_send:
                if n.dedup_key:
                    db.add(Notification(
                        severity="info",
                        category="integration",
                        message=f"Alert email sent for: {n.message}",
                        dedup_key=f"email:{n.dedup_key}",
                    ))
            db.commit()
    except Exception:
        logger.exception("alert email step failed (suppressed)")
        try:
            db.rollback()
        except Exception:
            pass
