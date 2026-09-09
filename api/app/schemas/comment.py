"""Comment schemas. Read-only in step 1 — comments arrive via ingest (step 4)."""

from pydantic import AwareDatetime

from app.enums import CommentCategory, CommentStatus, Sentiment, Urgency
from app.schemas.base import ORMModel


class CommentRead(ORMModel):
    id: int
    post_id: int
    external_id: str
    author: str
    text: str
    created_at: AwareDatetime
    # The four triage outputs, absent until triage has run.
    category: CommentCategory | None = None
    sentiment: Sentiment | None = None
    needs_reply: bool | None = None
    urgency: Urgency | None = None
    status: CommentStatus
