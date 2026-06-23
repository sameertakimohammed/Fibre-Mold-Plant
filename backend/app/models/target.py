from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class KpiTarget(Base):
    """A management target for a single KPI, compared against actuals on the
    dashboard ("vs target" on the KPI cards).

    One row per metric. ``metric`` is a stable string key (see
    routers/targets.ALLOWED_METRICS) rather than a DB enum, so adding a new
    target needs no migration. All targets are stored as RATES so they compare
    cleanly across any date range:

      * avg_per_day  — trays per active day (higher is better)
      * fuel_eff     — litres per 1,000 trays (lower is better)
      * downtime_pct — downtime as % of scheduled hours (lower is better)
      * repulp_rate  — re-pulped trays as % of output (lower is better)
    """
    __tablename__ = "kpi_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    metric: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    value: Mapped[float] = mapped_column(Float, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    # Plain int reference (no FK), mirroring audit_log.actor_id / notification
    # acknowledged_by — keeps a record of who set it even if that user is later
    # deleted, with no cascade surprises.
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
