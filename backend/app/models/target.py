from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class KpiTarget(Base):
    """A management target for one KPI at one cadence, compared against actuals
    on the dashboard ("vs target" on the KPI cards).

    One row per (``metric``, ``period``). ``metric`` is a stable string key (see
    routers/targets.METRICS) and ``period`` is one of daily/weekly/monthly, so
    adding a metric or a cadence needs no migration. There are two kinds of
    metric (routers/targets.METRICS records which is which):

      * volume — a *total* for one period of that length: 30's Trays output,
                 12's Cartons output, diesel litres. These scale with the
                 period, so each cadence carries its own number.
      * rate   — a ratio independent of period length: fuel efficiency
                 (L/1,000 trays), downtime %, reject %. Stored per cadence too
                 so a manager may set a stricter daily goal than the monthly one.
    """
    __tablename__ = "kpi_targets"
    __table_args__ = (
        UniqueConstraint("metric", "period", name="uq_kpi_target_metric_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    metric: Mapped[str] = mapped_column(String(40), index=True)
    period: Mapped[str] = mapped_column(String(10), index=True, default="monthly")
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
