from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ts: datetime
    actor_id: int | None = None
    actor_username: str | None = None
    action: str
    entity_type: str
    entity_id: str | None = None
    changes: dict[str, Any] | None = None
    ip: str | None = None
    request_id: str | None = None
    row_hash: str
    prev_hash: str | None = None


class AuditVerifyOut(BaseModel):
    ok: bool
    checked: int
    broken_at_id: int | None = None
    reason: str | None = None
