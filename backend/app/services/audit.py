"""Audit trail: generic write-capture via SQLAlchemy session events, a
tamper-evident SHA-256 hash chain, and a chain-integrity verifier.

WHY THE before_flush -> after_flush SPLIT
-----------------------------------------
We must (a) compute per-column diffs from the in-flight session and (b) persist
AuditLog rows in the SAME transaction so the trail commits atomically with the
business write. Doing both in one hook is unsafe:

  * In ``before_flush`` the ORM is mid-flush; adding new objects (AuditLog rows)
    there is fragile and can re-enter the flush machinery.
  * ``after_commit`` runs after the transaction closed — you'd need a separate
    session/transaction, so the trail could commit even if the business write
    rolled back (or vice-versa).

So we COLLECT plain-data change descriptions in ``before_flush`` (where the
dirty/new/deleted sets and attribute history are still available), stash them on
the session, then in ``after_flush`` (still inside the same transaction, ORM in
a stable state) we build the hash chain and ``session.add`` the AuditLog rows.
They flush again as part of the same commit. AuditLog itself is excluded so we
never recurse.

The hash chain makes the append-only log tamper-evident: each row stores
``row_hash = sha256(prev_hash + canonical_json(core fields))`` where prev_hash is
the previous row's row_hash. Editing or deleting any historical row breaks every
subsequent link, which the verifier reports. A Postgres BEFORE UPDATE/DELETE
trigger (created in the migration) additionally blocks mutations at the DB level.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from ..core.context import get_audit_actor, get_request_id

logger = logging.getLogger("app.audit")

# Business models whose writes we capture. AuditLog is deliberately NOT here.
_AUDITED = {
    "ProductionShift",
    "Delivery",
    "BaleReceipt",
    "FuelDip",
    "MonthlyStock",
    "User",
}

# Columns never worth diffing / never safe to log.
_SKIP_FIELDS = {"hashed_password"}

# Key set on session.info to carry collected changes from before_flush to
# after_flush.
_PENDING_KEY = "_audit_pending"


# ---------------------------------------------------------------------------
# Hash chain helpers
# ---------------------------------------------------------------------------
def _canonical(obj: dict) -> str:
    """Deterministic JSON for hashing (sorted keys, no whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def compute_row_hash(prev_hash: str | None, core: dict) -> str:
    """row_hash = sha256(prev_hash + canonical_json(core fields))."""
    payload = (prev_hash or "") + _canonical(core)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _norm_ts(ts) -> str | None:
    """Canonical timestamp string for hashing.

    Must survive a DB round-trip on BOTH backends. Postgres returns aware UTC
    datetimes; SQLite drops the tzinfo and returns naive values. So we coerce to
    UTC (treating naive as UTC), strip tzinfo, and emit a fixed microsecond ISO
    string — identical whether computed at write time or recomputed from a read.
    """
    if ts is None:
        return None
    if isinstance(ts, datetime):
        if ts.tzinfo is not None:
            ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
        return ts.isoformat(timespec="microseconds")
    return str(ts)


def _core_fields(rec: dict) -> dict:
    """The subset of an audit row that the hash commits to."""
    return {
        "ts": _norm_ts(rec["ts"]),
        "actor_id": rec.get("actor_id"),
        "actor_username": rec.get("actor_username"),
        "action": rec.get("action"),
        "entity_type": rec.get("entity_type"),
        "entity_id": rec.get("entity_id"),
        "changes": rec.get("changes"),
        "ip": rec.get("ip"),
        "request_id": rec.get("request_id"),
    }


def _latest_prev_hash(db: Session) -> str | None:
    """Most recent row_hash, used as the next row's prev_hash. Reads within the
    current transaction so a batch of rows in one flush chains correctly."""
    from ..models.audit import AuditLog
    row = (
        db.query(AuditLog.row_hash)
        .order_by(AuditLog.id.desc())
        .limit(1)
        .first()
    )
    return row[0] if row else None


def _jsonable(value):
    """Coerce ORM attribute values into JSON-serializable primitives."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    # Enums (Role, Shift) -> their .value; dates -> isoformat; fallback to str.
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


# ---------------------------------------------------------------------------
# Write a single explicit audit row (used by routers for security events)
# ---------------------------------------------------------------------------
def record_event(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    changes: dict | None = None,
    *,
    actor_id: int | None = None,
    actor_username: str | None = None,
) -> None:
    """Append one audit row immediately (its own commit-less add).

    For security events (login.success/fail, role change, deactivate) that
    aren't tied to an ORM write. The caller's commit persists it. Actor falls
    back to the context actor when not given explicitly.
    """
    from ..models.audit import AuditLog

    actor = get_audit_actor()
    if actor_id is None and actor is not None:
        actor_id = actor.user_id
    if actor_username is None and actor is not None:
        actor_username = actor.username
    ip = actor.ip if actor is not None else None

    rec = {
        "ts": datetime.now(timezone.utc),
        "actor_id": actor_id,
        "actor_username": actor_username,
        "action": action,
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id is not None else None,
        "changes": changes,
        "ip": ip,
        "request_id": get_request_id() or None,
    }
    prev = _latest_prev_hash(db)
    row_hash = compute_row_hash(prev, _core_fields(rec))
    db.add(AuditLog(**rec, prev_hash=prev, row_hash=row_hash))


# ---------------------------------------------------------------------------
# Generic capture via session events
# ---------------------------------------------------------------------------
def _describe_insert(obj) -> dict:
    """Snapshot of a newly inserted row (field -> [None, new])."""
    insp = inspect(obj)
    changes = {}
    for attr in insp.mapper.column_attrs:
        key = attr.key
        if key in _SKIP_FIELDS:
            continue
        changes[key] = [None, _jsonable(getattr(obj, key))]
    return changes


def _describe_update(obj) -> dict:
    """Per-column diffs for a modified row (only changed columns)."""
    insp = inspect(obj)
    changes = {}
    for attr in insp.mapper.column_attrs:
        key = attr.key
        if key in _SKIP_FIELDS:
            continue
        hist = insp.attrs[key].history
        if not hist.has_changes():
            continue
        old = hist.deleted[0] if hist.deleted else None
        new = hist.added[0] if hist.added else None
        changes[key] = [_jsonable(old), _jsonable(new)]
    # hashed_password changes are noteworthy but never logged verbatim.
    if "hashed_password" in {a.key for a in insp.mapper.column_attrs}:
        if insp.attrs["hashed_password"].history.has_changes():
            changes["hashed_password"] = ["***", "***"]
    return changes


def _describe_delete(obj) -> dict:
    """Snapshot of a hard-deleted row (field -> [old, None])."""
    insp = inspect(obj)
    changes = {}
    for attr in insp.mapper.column_attrs:
        key = attr.key
        if key in _SKIP_FIELDS:
            continue
        changes[key] = [_jsonable(getattr(obj, key)), None]
    return changes


def _before_flush(session: Session, flush_context, instances):
    """Collect plain-data change descriptions while the unit-of-work is intact."""
    pending = session.info.setdefault(_PENDING_KEY, [])

    for obj in session.new:
        name = type(obj).__name__
        if name not in _AUDITED:
            continue
        pending.append({"action": "create", "entity_type": name, "obj": obj,
                        "changes": _describe_insert(obj)})

    for obj in session.dirty:
        name = type(obj).__name__
        if name not in _AUDITED:
            continue
        if not session.is_modified(obj, include_collections=False):
            continue
        diffs = _describe_update(obj)
        if not diffs:
            continue
        # A soft-delete (deleted_at went from None -> a value) is logged as a
        # 'delete' action so the trail reads naturally.
        action = "update"
        if "deleted_at" in diffs and diffs["deleted_at"][0] is None and diffs["deleted_at"][1] is not None:
            action = "delete"
        pending.append({"action": action, "entity_type": name, "obj": obj,
                        "changes": diffs})

    for obj in session.deleted:
        name = type(obj).__name__
        if name not in _AUDITED:
            continue
        pending.append({"action": "delete", "entity_type": name, "obj": obj,
                        "changes": _describe_delete(obj)})


def _after_flush(session: Session, flush_context):
    """Persist collected changes as chained AuditLog rows in the same txn."""
    pending = session.info.get(_PENDING_KEY)
    if not pending:
        return
    # Clear immediately so we never double-process or recurse on the audit
    # rows we are about to add (those re-enter before_flush, but AuditLog is
    # excluded by _AUDITED, and pending is already empty).
    session.info[_PENDING_KEY] = []

    from ..models.audit import AuditLog

    # Prefer the actor stashed on the session (set by get_current_user) — it
    # survives FastAPI's threadpool hop between the auth dependency and this
    # flush, where the ContextVar does not. Fall back to the ContextVar for code
    # paths that set it in the same execution context (e.g. explicit events).
    actor = session.info.get("audit_actor") or get_audit_actor()
    actor_id = actor.user_id if actor else None
    actor_username = actor.username if actor else None
    ip = actor.ip if actor else None
    request_id = get_request_id() or None

    prev = _latest_prev_hash(session)
    new_rows = []
    for item in pending:
        obj = item["obj"]
        entity_id = None
        try:
            pk = inspect(obj).identity
            if pk:
                entity_id = str(pk[0])
            else:
                entity_id = str(getattr(obj, "id", None))
        except Exception:
            entity_id = None

        rec = {
            "ts": datetime.now(timezone.utc),
            "actor_id": actor_id,
            "actor_username": actor_username,
            "action": item["action"],
            "entity_type": item["entity_type"],
            "entity_id": entity_id,
            "changes": item["changes"] or None,
            "ip": ip,
            "request_id": request_id,
        }
        row_hash = compute_row_hash(prev, _core_fields(rec))
        new_rows.append(AuditLog(**rec, prev_hash=prev, row_hash=row_hash))
        prev = row_hash

    session.add_all(new_rows)


def register_audit_listeners() -> None:
    """Idempotently wire the session events. Safe to call once at import time."""
    if not event.contains(Session, "before_flush", _before_flush):
        event.listen(Session, "before_flush", _before_flush)
    if not event.contains(Session, "after_flush", _after_flush):
        event.listen(Session, "after_flush", _after_flush)


# ---------------------------------------------------------------------------
# Chain verification (admin only)
# ---------------------------------------------------------------------------
def verify_chain(db: Session) -> dict:
    """Walk the whole chain in id order and report the first broken link.

    Returns {"ok": bool, "checked": n, "broken_at_id": id|None, "reason": str|None}.
    """
    from ..models.audit import AuditLog

    rows = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
    prev = None
    for r in rows:
        rec = {
            "ts": r.ts,
            "actor_id": r.actor_id,
            "actor_username": r.actor_username,
            "action": r.action,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "changes": r.changes,
            "ip": r.ip,
            "request_id": r.request_id,
        }
        if (r.prev_hash or None) != (prev or None):
            return {"ok": False, "checked": len(rows), "broken_at_id": r.id,
                    "reason": "prev_hash does not match preceding row_hash"}
        expected = compute_row_hash(prev, _core_fields(rec))
        if expected != r.row_hash:
            return {"ok": False, "checked": len(rows), "broken_at_id": r.id,
                    "reason": "row_hash does not match recomputed hash (row altered)"}
        prev = r.row_hash

    return {"ok": True, "checked": len(rows), "broken_at_id": None, "reason": None}
