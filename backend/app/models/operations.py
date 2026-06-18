from datetime import datetime, timezone, date
from sqlalchemy import String, Integer, Float, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


# created_by / deleted_by FKs are ON DELETE SET NULL (enforced in the migration)
# so deleting a user can never orphan/break operations rows. deleted_at/deleted_by
# implement soft-delete: list/get queries filter deleted_at IS NULL.
class Delivery(Base):
    __tablename__ = "deliveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    company: Mapped[str] = mapped_column(String(120))
    tray30: Mapped[float] = mapped_column(Float, default=0)
    tray12n: Mapped[float] = mapped_column(Float, default=0)
    tray12ff: Mapped[float] = mapped_column(Float, default=0)
    pallets: Mapped[float] = mapped_column(Float, default=0)
    comment: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class BaleReceipt(Base):
    __tablename__ = "bale_receipts"
    id: Mapped[int] = mapped_column(primary_key=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    grn: Mapped[str] = mapped_column(String(60), default="")  # Goods Received Note #
    weight_kg: Mapped[float] = mapped_column(Float, default=0)
    quantity: Mapped[float] = mapped_column(Float, default=0)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class FuelDip(Base):
    __tablename__ = "fuel_dips"
    id: Mapped[int] = mapped_column(primary_key=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    shift: Mapped[str] = mapped_column(String(30))
    open_dip: Mapped[float] = mapped_column(Float, default=0)
    close_dip: Mapped[float] = mapped_column(Float, default=0)
    actual_usage: Mapped[float] = mapped_column(Float, default=0)
    received: Mapped[float] = mapped_column(Float, default=0)
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class MonthlyStock(Base):
    __tablename__ = "monthly_stock"
    id: Mapped[int] = mapped_column(primary_key=True)
    period: Mapped[str] = mapped_column(String(7), unique=True, index=True)  # YYYY-MM
    diesel_eom: Mapped[float] = mapped_column(Float, default=0)
    bal_30s: Mapped[float] = mapped_column(Float, default=0)
    bal_12n: Mapped[float] = mapped_column(Float, default=0)
    bal_12ff: Mapped[float] = mapped_column(Float, default=0)
    bal_12nl: Mapped[float] = mapped_column(Float, default=0)
    pallets_wrapped: Mapped[float] = mapped_column(Float, default=0)
    bales_used: Mapped[float] = mapped_column(Float, default=0)
    bales_purchased: Mapped[float] = mapped_column(Float, default=0)
    labels_used: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
