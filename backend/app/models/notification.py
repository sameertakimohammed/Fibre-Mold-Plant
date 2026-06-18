from datetime import datetime, timezone
from sqlalchemy import String, Integer, Boolean, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class Notification(Base):
    """A proactive alert / informational message surfaced in the dashboard.

    Rows are written by services/alerts.evaluate (post-shift-write and the daily
    scheduler job). Each alert carries a stable ``dedup_key`` (e.g.
    "downtime:2026-06-17") so the SAME issue is not re-inserted on every run —
    the alert service checks for an existing row with that key inside a recent
    window before inserting.

    severity / category are stored as plain strings (not DB enums) so adding a
    new category never needs a migration. acknowledged* track who dismissed it.
    """
    __tablename__ = "notifications"
    __table_args__ = (
        # Newest-first listing is the common read path.
        Index("ix_notifications_created_at", "created_at"),
        # Dedup lookups filter on (dedup_key, created_at) within a window.
        Index("ix_notifications_dedup_key", "dedup_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    # 'info' | 'warn' | 'critical' (stored as string).
    severity: Mapped[str] = mapped_column(String(20), default="info")
    message: Mapped[str] = mapped_column(Text)
    # e.g. 'downtime' | 'fuel' | 'output' | 'missed_shift' | 'backup' | 'integration'
    category: Mapped[str] = mapped_column(String(40))
    # Stable key for de-duplication; nullable for ad-hoc notifications.
    dedup_key: Mapped[str | None] = mapped_column(String(160), nullable=True)

    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Plain int reference (no FK): mirrors audit_log.actor_id — keeps a record
    # of who acked even if that user is later deleted, with no cascade surprises.
    acknowledged_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
