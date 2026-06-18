from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.notification import Notification
from ..models.user import User
from ..deps import get_current_user

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

# Cap on rows returned by the recent-list path.
MAX_LIMIT = 100


def _serialize(n: Notification) -> dict:
    return {
        "id": n.id,
        "severity": n.severity,
        "message": n.message,
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "acknowledged": n.acknowledged,
    }


@router.get("")
def list_notifications(
    unacknowledged: bool = Query(False),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List notifications, newest first.

    - ?unacknowledged=true -> only rows that have NOT been acknowledged.
    - without the param     -> recent rows (acked + not), capped at 100.

    Returns a JSON array of {id, severity, message, created_at, acknowledged}.
    """
    q = db.query(Notification)
    if unacknowledged:
        q = q.filter(Notification.acknowledged.is_(False))
    rows = q.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(MAX_LIMIT).all()
    return [_serialize(n) for n in rows]


@router.post("/{notification_id}/ack", status_code=204)
def acknowledge(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Acknowledge a notification (any logged-in user). Returns 204."""
    n = db.get(Notification, notification_id)
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    if not n.acknowledged:
        n.acknowledged = True
        n.acknowledged_by = user.id
        n.acknowledged_at = datetime.now(timezone.utc)
        db.commit()
    return Response(status_code=204)
