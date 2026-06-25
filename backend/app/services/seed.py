import json
import logging
import os
from datetime import datetime
from sqlalchemy.orm import Session
from ..core.security import hash_password
from ..core.config import settings
from ..models.user import User, Role
from ..models.production import ProductionShift, Shift
from ..models.operations import Delivery, MonthlyStock
from ..models.target import KpiTarget

logger = logging.getLogger("app.seed")

def _find_data_dir():
    here = os.path.dirname(__file__)
    candidates = [
        os.path.join(here, "..", "..", "data"),        # backend/data (local + Docker WORKDIR /app)
        os.path.join(here, "..", "..", "..", "data"),  # repo-root/data (alt layout)
        "/app/data",                                     # Docker absolute
    ]
    for c in candidates:
        if os.path.isdir(c):
            return os.path.normpath(c)
    return os.path.normpath(candidates[0])


DATA_DIR = _find_data_dir()

SHIFT_MAP = {"day": Shift.day, "afternoon": Shift.afternoon, "night": Shift.night}


def _shift_enum(s: str) -> Shift:
    l = (s or "").lower()
    if l.startswith("day"):
        return Shift.day
    if l.startswith("afternoon"):
        return Shift.afternoon
    return Shift.night


def ensure_admin(db: Session):
    if db.query(User).filter(User.username == settings.first_admin_username).first():
        return
    admin = User(
        username=settings.first_admin_username,
        full_name=settings.first_admin_name,
        hashed_password=hash_password(settings.first_admin_password),
        role=Role.admin,
        must_change_password=True,
    )
    db.add(admin)
    db.commit()
    logger.info(f"[seed] created admin user '{settings.first_admin_username}'")


def import_may_data(db: Session):
    """Import the original May 2026 records once, if the DB is empty."""
    if db.query(ProductionShift).count() > 0:
        return

    tracker_path = os.path.join(DATA_DIR, "tracker.json")
    support_path = os.path.join(DATA_DIR, "support.json")
    if not os.path.exists(tracker_path):
        logger.info("[seed] no tracker.json found, skipping import")
        return

    with open(tracker_path) as f:
        tracker = json.load(f)
    admin = db.query(User).filter(User.role == Role.admin).first()
    admin_id = admin.id if admin else None

    count = 0
    seen = set()
    for r in tracker:
        if not r.get("date"):
            continue
        try:
            wd = datetime.strptime(r["date"], "%Y-%m-%d").date()
        except ValueError:
            continue
        sh = _shift_enum(r.get("shift", ""))
        key = (wd, sh)
        if key in seen:
            # original sheet had a duplicate date+shift row; keep first, skip rest
            continue
        seen.add(key)
        hp = r.get("hp", [0] * 6) + [0] * 6
        ps = ProductionShift(
            work_date=wd, shift=sh,
            qty=r.get("qty", 0),
            p30s=r.get("p30s", 0), p30l=r.get("p30l", 0), p20n=r.get("p20n", 0),
            p12n=r.get("p12n", 0), p12hf=r.get("p12hf", 0), p12ff=r.get("p12ff", 0),
            p4cup=r.get("p4cup", 0), p2cup=r.get("p2cup", 0),
            hp1=hp[0], hp2=hp[1], hp3=hp[2], hp4=hp[3], hp5=hp[4], hp6=hp[5],
            labelling=r.get("label", 0), water_meter=r.get("water", 0),
            carton_bales=r.get("bales", 0), speed=r.get("speed", 0),
            fuel_open=r.get("fuel_open", 0), fuel_close=r.get("fuel_close", 0),
            fuel_use=r.get("fuel_use", 0),
            prod_hours=r.get("prod_hrs", 0), downtime_min=r.get("down_min", 0),
            sched_hours=r.get("tot_hrs", 8) or 8,
            clean_min=r.get("clean", 0), mold_min=r.get("mold", 0), other_min=r.get("other", 0),
            repulped=r.get("repulp", 0), comment=r.get("comment", ""),
            created_by=admin_id,
        )
        db.add(ps)
        count += 1
    db.commit()
    logger.info(f"[seed] imported {count} production shifts")

    # Deliveries + monthly stock
    if os.path.exists(support_path):
        with open(support_path) as f:
            support = json.load(f)
        dcount = 0
        for d in support.get("deliveries", []):
            if not d.get("date"):
                continue
            try:
                wd = datetime.strptime(d["date"], "%Y-%m-%d").date()
            except ValueError:
                continue
            db.add(Delivery(
                work_date=wd, company=d.get("company", ""),
                tray30=d.get("t30", 0), tray12n=d.get("t12n", 0),
                tray12ff=d.get("t12ff", 0), pallets=d.get("pallets", 0),
                created_by=admin_id,
            ))
            dcount += 1
        stk = support.get("stock")
        if stk and not db.query(MonthlyStock).filter(MonthlyStock.period == "2026-05").first():
            bal = stk.get("balance", {})
            db.add(MonthlyStock(
                period="2026-05",
                diesel_eom=stk.get("diesel_eom", 0),
                bal_30s=bal.get("30s", 0), bal_12n=bal.get("12n", 0),
                bal_12ff=bal.get("12ff", 0), bal_12nl=bal.get("12nl", 0),
                pallets_wrapped=stk.get("pallets_wrapped", 0),
                bales_used=stk.get("bales_used", 0),
                labels_used=stk.get("labels_used", 0),
            ))
        db.commit()
        logger.info(f"[seed] imported {dcount} deliveries + monthly stock")


def ensure_default_targets(db: Session):
    """Seed the supervisor's daily/weekly/monthly targets into an EMPTY table.

    Gated on the table being completely empty (mirrors import_may_data): a fresh
    install gets the full set, while an existing install is left untouched so a
    manager's edits — or a deliberately cleared target — are never clobbered or
    resurrected on the next boot. Values live in routers.targets.DEFAULT_TARGETS.
    """
    if db.query(KpiTarget).count() > 0:
        return
    from ..routers.targets import DEFAULT_TARGETS
    n = 0
    for metric, by_period in DEFAULT_TARGETS.items():
        for period, value in by_period.items():
            db.add(KpiTarget(metric=metric, period=period, value=value))
            n += 1
    db.commit()
    logger.info(f"[seed] seeded {n} default KPI targets")


def run_seed(db: Session):
    ensure_admin(db)
    ensure_default_targets(db)
    # Full historical bundle (Aug 2024 → May 2026) parsed from the plant's
    # monthly emails into data/history.json. Idempotent — safe on every boot.
    # Disabled in the test suite (SEED_HISTORY=false) which seeds its own data.
    if settings.seed_history:
        try:
            from .import_history import import_history
            import_history(db)
        except Exception:
            logger.exception("[seed] history import failed; falling back to May seed")
    # Fallback for installs without history.json: the original curated May data.
    import_may_data(db)
