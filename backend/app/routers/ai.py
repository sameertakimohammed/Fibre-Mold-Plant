"""AI assistant endpoints (Anthropic Claude) — report commentary + Q&A.

All routes are gated by services.ai.ai_available(); when AI is off or
unconfigured they return 503 (except /status, which reports the flag so the UI
can hide the controls). /ask is rate-limited because each call costs money.
"""
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import get_db
from ..core.ratelimit import limiter
from ..deps import get_current_user
from ..models.user import User
from ..services import ai
from ..services.report_monthend import collect_monthend

logger = logging.getLogger("app.ai")

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class AskResponse(BaseModel):
    answer: str


class CommentaryResponse(BaseModel):
    commentary: str


@router.get("/status")
def ai_status(_: User = Depends(get_current_user)):
    """Whether the AI features are usable (drives showing/hiding the UI)."""
    available = ai.ai_available()
    return {"enabled": available, "model": settings.ai_model if available else None}


@router.post("/ask", response_model=AskResponse)
@limiter.limit("20/minute")
def ai_ask(
    body: AskRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if not ai.ai_available():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="AI assistant is not enabled.")
    try:
        return AskResponse(answer=ai.answer_question(body.question, db))
    except Exception as exc:
        logger.exception("[ai] /ask failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="The AI assistant could not be reached. Try again shortly.") from exc


@router.get("/commentary", response_model=CommentaryResponse)
def ai_commentary(
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """The Plant Manager's Commentary for a month (same text embedded in the
    Month End Report). Returns 503 when AI is off."""
    if not ai.ai_available():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="AI assistant is not enabled.")
    data = collect_monthend(db, start, end)
    return CommentaryResponse(commentary=ai.generate_commentary(data))
