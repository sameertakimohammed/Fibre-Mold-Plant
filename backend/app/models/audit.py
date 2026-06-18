from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


# Use JSONB on Postgres (indexable, compact) but fall back to plain JSON on
# SQLite (the local/test path), so the same model works everywhere.
JSONType = JSONB().with_variant(JSON(), "sqlite")


class AuditLog(Base):
    """Append-only, tamper-evident audit trail.

    Every business write (create/update/delete) and key security events
    (logins, role changes, deactivations) land here. Rows are chained with a
    SHA-256 hash so any after-the-fact edit/delete is detectable; a Postgres
    BEFORE UPDATE/DELETE trigger (added in the migration) additionally refuses
    mutations at the DB level. NEVER soft-delete or edit these rows.
    """
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
        Index("ix_audit_log_ts", "ts"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=False
    )

    # Actor: a plain (un-constrained) reference to the user id at write time.
    # Deliberately NOT a foreign key: this table is append-only (a BEFORE
    # UPDATE/DELETE trigger blocks mutations) AND each row is hash-chained over
    # actor_id, so an ON DELETE SET NULL cascade would both (a) be blocked by the
    # trigger — making it impossible to ever delete a user who has audit rows —
    # and (b) silently break the tamper-evidence chain. actor_username is the
    # durable, human-readable record of who acted; actor_id may point at a since-
    # deleted user, which is correct for an immutable historical log.
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_username: Mapped[str | None] = mapped_column(String(50), nullable=True)

    action: Mapped[str] = mapped_column(String(40))          # create/update/delete/login.success/...
    entity_type: Mapped[str] = mapped_column(String(60))     # e.g. ProductionShift, User, Auth
    entity_id: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # Per-column diffs: {field: [old, new]} for updates; full snapshot keys for
    # create/delete. JSON-serializable values only.
    changes: Mapped[dict | None] = mapped_column(JSONType, nullable=True)

    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Hash chain: row_hash = sha256(prev_hash + canonical_json(core fields)).
    row_hash: Mapped[str] = mapped_column(String(64))
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
