"""In-process job scheduler (APScheduler BackgroundScheduler).

Single-host, single-replica design: NO Celery/Redis. The scheduler is started
in the FastAPI lifespan and shut down cleanly on app stop.

IMPORTANT — MULTI-WORKER SAFETY
-------------------------------
This works because the app runs uvicorn with workers=1 (see entrypoint.sh), so
exactly ONE scheduler exists. If you ever scale to multiple uvicorn workers or
multiple app replicas, EACH process would start its own scheduler and the daily
jobs would run N times. To avoid that, run the scheduler in only ONE process:
set SCHEDULER_ENABLED=false on every worker/replica except one (or front it with
a leader-election / single dedicated worker). The `scheduler_enabled` setting is
the env flag for exactly this.

Each job is wrapped by _job_wrapper so one job's exception can never kill the
scheduler thread; every run logs its outcome via the "app.scheduler" logger.
Jobs open their OWN SessionLocal() and always close it (the request-scoped
get_db dependency is not available in a background thread).
"""
import logging
from datetime import date, datetime, timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from ..core.config import settings
from ..core.database import SessionLocal

logger = logging.getLogger("app.scheduler")

_scheduler: BackgroundScheduler | None = None


def _job_wrapper(func):
    """Wrap a job so an exception is logged, not propagated (which would let
    APScheduler keep running but pollute logs / and, for misjobs, could stop
    that job). Logs start + outcome of every run."""
    name = func.__name__

    def wrapped():
        logger.info("scheduler job start", extra={"job": name})
        try:
            func()
            logger.info("scheduler job ok", extra={"job": name})
        except Exception:
            logger.exception("scheduler job failed", extra={"job": name})

    wrapped.__name__ = name
    return wrapped


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------
def _daily_alert_scan() -> None:
    """Run the proactive alert evaluation over the recent window."""
    from .alerts import evaluate

    db = SessionLocal()
    try:
        created = evaluate(db)
        logger.info("daily alert scan complete", extra={"created": len(created)})
    finally:
        db.close()


def _report_period(cadence: str, today: date) -> tuple[date, date] | None:
    """Return (start, end) for the report covering the PRIOR period."""
    if cadence == "weekly":
        # Prior 7 days ending yesterday.
        end = today - timedelta(days=1)
        start = end - timedelta(days=6)
        return start, end
    if cadence == "monthly":
        # The whole previous calendar month.
        first_this_month = today.replace(day=1)
        end = first_this_month - timedelta(days=1)
        start = end.replace(day=1)
        return start, end
    return None


def _scheduled_report_email() -> None:
    """Build last period's report and email it to report_email_to."""
    from .report_build import build_report_xlsx
    from .email import send_email, email_configured

    cadence = settings.report_email_cadence.strip().lower()
    if cadence == "off":
        logger.info("report email skipped: cadence=off")
        return
    if not email_configured() or not settings.report_email_to:
        logger.info("report email skipped: email disabled/unconfigured or no recipients")
        return

    period = _report_period(cadence, datetime.now(timezone.utc).date())
    if period is None:
        logger.warning("report email skipped: unknown cadence %r", cadence)
        return
    start, end = period

    db = SessionLocal()
    try:
        data, fname = build_report_xlsx(db, start, end)
    finally:
        db.close()

    subject = f"Fibre Mold Plant report: {start} to {end}"
    body = (
        f"Attached is the {cadence} Fibre Mold Plant production report for "
        f"{start} to {end}.\n\nThis is an automated message from the plant dashboard."
    )
    send_email(subject, body, settings.report_email_to, attachments=[(fname, data)])
    logger.info("report email job done", extra={"period": f"{start}..{end}"})


def _email_shift_report(shift_value: str, day_offsets: list[int]) -> None:
    """Email the PDF log sheet for the just-ended shift.

    ``day_offsets`` are days-before-today (plant tz) to look for the shift,
    tried in order — the Night job checks yesterday (its start date) then today,
    so it works whichever date the shift was logged under.
    """
    from zoneinfo import ZoneInfo
    from ..models.production import ProductionShift, Shift
    from .report_shift_pdf import build_shift_report_pdf
    from .email import send_email, email_configured

    if not settings.shift_report_enabled:
        logger.info("shift report skipped: disabled")
        return
    if not email_configured() or not settings.shift_report_email_to:
        logger.info("shift report skipped: email disabled/unconfigured or no recipients")
        return

    try:
        base = datetime.now(ZoneInfo(settings.plant_tz)).date()
    except Exception:
        logger.exception("shift report: bad plant_tz %r", settings.plant_tz)
        return
    dates = [base - timedelta(days=o) for o in day_offsets]

    db = SessionLocal()
    try:
        row = None
        for d in dates:
            row = (db.query(ProductionShift)
                   .filter(ProductionShift.deleted_at.is_(None),
                           ProductionShift.work_date == d,
                           ProductionShift.shift == Shift(shift_value))
                   .first())
            if row:
                break
        if not row:
            logger.info("shift report: no %s shift logged for %s — nothing to send",
                        shift_value, [d.isoformat() for d in dates])
            return
        data, fname = build_shift_report_pdf(row)
        work_date = row.work_date.isoformat()
    finally:
        db.close()

    subject = f"Shift Report — {work_date} · {shift_value}"
    body = (
        f"Attached is the {shift_value} shift production report for {work_date}.\n\n"
        "This is an automated message from the Fibre Mold Plant dashboard."
    )
    send_email(subject, body, settings.shift_report_email_to, attachments=[(fname, data)])
    logger.info("shift report email sent", extra={"shift": shift_value, "date": work_date})


def _shift_report_day() -> None:
    _email_shift_report("Day", [0])


def _shift_report_afternoon() -> None:
    _email_shift_report("Afternoon", [0])


def _shift_report_night() -> None:
    # Night spans midnight; prefer yesterday (its start date), fall back to today.
    _email_shift_report("Night", [1, 0])


def _parse_hhmm(raw: str) -> tuple[int, int] | None:
    try:
        hh, mm = (int(x) for x in str(raw).strip().split(":"))
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return hh, mm
    except (ValueError, TypeError):
        pass
    logger.warning("shift report: bad shift end time %r", raw)
    return None


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
def start_scheduler() -> BackgroundScheduler | None:
    """Create, register jobs on, and start the BackgroundScheduler.

    Returns the scheduler (or None when disabled). Safe to call once at startup.
    """
    global _scheduler
    if not settings.scheduler_enabled:
        logger.info("scheduler disabled (SCHEDULER_ENABLED=false) — no jobs started")
        return None
    if _scheduler is not None:
        return _scheduler

    sched = BackgroundScheduler(timezone="UTC")

    # Daily alert scan.
    sched.add_job(
        _job_wrapper(_daily_alert_scan),
        trigger="cron",
        hour=settings.alert_scan_hour,
        minute=0,
        id="daily_alert_scan",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )

    # Scheduled report email (monthly or weekly, per config).
    cadence = settings.report_email_cadence.strip().lower()
    if cadence == "monthly":
        sched.add_job(
            _job_wrapper(_scheduled_report_email),
            trigger="cron",
            day=settings.report_email_day_of_month,
            hour=settings.report_email_hour,
            minute=0,
            id="report_email",
            replace_existing=True,
            misfire_grace_time=6 * 3600,
            coalesce=True,
        )
    elif cadence == "weekly":
        sched.add_job(
            _job_wrapper(_scheduled_report_email),
            trigger="cron",
            day_of_week="mon",
            hour=settings.report_email_hour,
            minute=0,
            id="report_email",
            replace_existing=True,
            misfire_grace_time=6 * 3600,
            coalesce=True,
        )
    else:
        logger.info("report email job not scheduled (cadence=%r)", cadence)

    # Per-shift report email — one job per shift, firing at its end time in the
    # plant timezone. Registered even when shift_report_enabled is False so the
    # cadence is visible; each run no-ops early until enabled + configured.
    shift_jobs = [
        ("shift_report_day", settings.shift_end_day, _shift_report_day),
        ("shift_report_afternoon", settings.shift_end_afternoon, _shift_report_afternoon),
        ("shift_report_night", settings.shift_end_night, _shift_report_night),
    ]
    for job_id, hhmm, fn in shift_jobs:
        parsed = _parse_hhmm(hhmm)
        if parsed is None:
            continue
        hh, mm = parsed
        sched.add_job(
            _job_wrapper(fn),
            trigger="cron", hour=hh, minute=mm, timezone=settings.plant_tz,
            id=job_id, replace_existing=True, misfire_grace_time=3600, coalesce=True,
        )

    sched.start()
    _scheduler = sched
    jobs = [j.id for j in sched.get_jobs()]
    logger.info("scheduler started", extra={"jobs": jobs})
    return sched


def shutdown_scheduler() -> None:
    """Stop the scheduler cleanly (called from the FastAPI lifespan)."""
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
            logger.info("scheduler stopped")
        except Exception:
            logger.exception("scheduler shutdown failed")
        finally:
            _scheduler = None
