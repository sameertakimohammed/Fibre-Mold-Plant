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
