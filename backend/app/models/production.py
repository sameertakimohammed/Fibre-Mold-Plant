import enum
from datetime import datetime, timezone, date
from sqlalchemy import String, Integer, Float, Date, DateTime, Enum as SAEnum, ForeignKey, Index, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class Shift(str, enum.Enum):
    day = "Day"
    afternoon = "Afternoon"
    night = "Night"


class ProductionShift(Base):
    """One row per shift — mirrors the Fiber Mold Tracker."""
    __tablename__ = "production_shifts"
    # Duplicate protection is a PARTIAL unique index (work_date, shift) WHERE
    # deleted_at IS NULL — defined in the migration. That lets a soft-deleted
    # shift be re-entered for the same date+shift without colliding. (The old
    # plain uq_date_shift UniqueConstraint is dropped in the same migration.)
    __table_args__ = (
        Index(
            "uq_date_shift_active", "work_date", "shift",
            unique=True, postgresql_where=Text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    shift: Mapped[Shift] = mapped_column(SAEnum(Shift), index=True)

    # Output
    qty: Mapped[float] = mapped_column(Float, default=0)
    p30s: Mapped[float] = mapped_column(Float, default=0)   # 30's Small
    p30l: Mapped[float] = mapped_column(Float, default=0)   # 30's Large
    p20n: Mapped[float] = mapped_column(Float, default=0)   # 20's Normal
    p12n: Mapped[float] = mapped_column(Float, default=0)   # 12's Normal
    p12hf: Mapped[float] = mapped_column(Float, default=0)  # 12's Half Face
    p12ff: Mapped[float] = mapped_column(Float, default=0)  # 12's Full Face
    p4cup: Mapped[float] = mapped_column(Float, default=0)  # 4's Cup Holder
    p2cup: Mapped[float] = mapped_column(Float, default=0)  # 2's Cup Holder

    # Hot presses 1-6
    hp1: Mapped[float] = mapped_column(Float, default=0)
    hp2: Mapped[float] = mapped_column(Float, default=0)
    hp3: Mapped[float] = mapped_column(Float, default=0)
    hp4: Mapped[float] = mapped_column(Float, default=0)
    hp5: Mapped[float] = mapped_column(Float, default=0)
    hp6: Mapped[float] = mapped_column(Float, default=0)

    # Utilities & rate
    labelling: Mapped[float] = mapped_column(Float, default=0)
    water_meter: Mapped[float] = mapped_column(Float, default=0)
    carton_bales: Mapped[float] = mapped_column(Float, default=0)
    speed: Mapped[float] = mapped_column(Float, default=0)

    # Fuel
    fuel_open: Mapped[float] = mapped_column(Float, default=0)
    fuel_close: Mapped[float] = mapped_column(Float, default=0)
    fuel_use: Mapped[float] = mapped_column(Float, default=0)

    # Hours & downtime
    prod_hours: Mapped[float] = mapped_column(Float, default=0)
    downtime_min: Mapped[float] = mapped_column(Float, default=0)
    sched_hours: Mapped[float] = mapped_column(Float, default=8)
    clean_min: Mapped[float] = mapped_column(Float, default=0)
    mold_min: Mapped[float] = mapped_column(Float, default=0)
    other_min: Mapped[float] = mapped_column(Float, default=0)
    repulped: Mapped[float] = mapped_column(Float, default=0)

    comment: Mapped[str] = mapped_column(Text, default="")

    # --- End-of-shift report sheet (the Team Leader's log) ---
    # Captures the rest of the paper sheet so it can be rendered + emailed
    # automatically at shift end. Quantities stay in the typed columns above
    # (qty, hp1..hp6, labelling), so analytics is unaffected; `machines` only
    # holds the extra per-machine attributes (hours/targets/operators/detail).
    supervisor: Mapped[str] = mapped_column(String(120), default="")
    staff_count: Mapped[int] = mapped_column(Integer, default=0)
    casual_count: Mapped[int] = mapped_column(Integer, default=0)
    absenteeism: Mapped[str] = mapped_column(Text, default="")
    stock_notes: Mapped[str] = mapped_column(Text, default="")
    delivery_notes: Mapped[str] = mapped_column(Text, default="")
    # Per-machine grid keyed by code (HGHY, HT1..HT6, LABEL). JSON mirrors the
    # MonthlyStock.detail pattern. Nullable: pre-existing rows read as {}.
    machines: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)

    # Audit. created_by FK is ON DELETE SET NULL (set in the migration) so
    # deleting a user can never orphan/break production rows.
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Soft-delete: rows are never physically removed; the delete endpoint stamps
    # these instead, and all list/get/analytics queries filter deleted_at IS NULL.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
