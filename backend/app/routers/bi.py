"""BI integration status endpoint.

A tiny admin-only endpoint so an administrator can confirm the Power BI
reporting layer (read-only views + role) exists. The views themselves are
created by the `d4e5f6a7b8c9_bi_reporting_views` Alembic migration; this router
does NOT create or modify anything — it only reports what should be there and,
on Postgres, checks that each view is actually present.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.user import User, Role
from ..deps import require_role

router = APIRouter(prefix="/api/v1/integrations/bi", tags=["bi"])

# Must match the names created in the BI migration.
VIEWS = ["vw_daily_production", "vw_deliveries", "vw_fuel", "vw_downtime"]
READONLY_ROLE = "fmp_readonly"


@router.get("/status")
def bi_status(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.admin)),
):
    """Admin-only: confirm the BI reporting layer exists.

    Returns the view names, the read-only role, a setup note, and (on Postgres)
    which views/role are actually present in the database right now.
    """
    present_views: list[str] = []
    role_exists: bool | None = None

    if db.bind is not None and db.bind.dialect.name == "postgresql":
        rows = db.execute(
            text(
                "SELECT table_name FROM information_schema.views "
                "WHERE table_schema = 'public' AND table_name = ANY(:names)"
            ),
            {"names": VIEWS},
        ).all()
        present_views = sorted(r[0] for r in rows)
        role_exists = db.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :r"),
            {"r": READONLY_ROLE},
        ).first() is not None

    return {
        "views": VIEWS,
        "present_views": present_views,
        "readonly_role": READONLY_ROLE,
        "readonly_role_exists": role_exists,
        "note": (
            "Read-only Power BI layer. Connect Power BI's PostgreSQL connector to "
            f"the '{READONLY_ROLE}' role (LAN only) and query these views — they "
            "are the stable BI contract and exclude soft-deleted rows. The admin "
            "enables login + sets the password out-of-band: "
            f"ALTER ROLE {READONLY_ROLE} WITH LOGIN PASSWORD '...'; (see README)."
        ),
    }
