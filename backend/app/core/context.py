"""Per-request context.

Holds the current request id in a contextvar so any module (logging,
exception handlers, services) can stamp log lines / responses with it
without having to thread the value through every call.

Also holds the resolved "audit actor" (the authenticated user behind the
current request) plus their IP, so the audit-trail writer can attribute every
write without threading the user through every call site. These are empty/None
when there is no active request (startup seed, background jobs) — the audit
writer treats that as a system action with a null actor.
"""
from contextvars import ContextVar
from typing import NamedTuple, Optional

# Empty string when there is no active request (e.g. startup, background jobs).
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


class AuditActor(NamedTuple):
    """Who is performing the current request, for audit attribution."""
    user_id: Optional[int]
    username: Optional[str]
    ip: Optional[str]


# None when there is no authenticated actor (startup seed, unauthenticated
# requests, background jobs). The audit writer records actor as NULL in that case.
audit_actor_ctx: ContextVar[Optional[AuditActor]] = ContextVar("audit_actor", default=None)


def get_request_id() -> str:
    return request_id_ctx.get()


def set_request_id(request_id: str) -> None:
    request_id_ctx.set(request_id)


def get_audit_actor() -> Optional[AuditActor]:
    return audit_actor_ctx.get()


def set_audit_actor(actor: Optional[AuditActor]) -> None:
    audit_actor_ctx.set(actor)
