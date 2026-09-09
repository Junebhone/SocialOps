"""Comment schemas. Read-only in step 1 — comments arrive via ingest (step 4)."""

from pydantic import AwareDatetime

from app.enums import CommentCategory, CommentStatus, DraftStatus, Sentiment, Urgency
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


class ReplyDraftSummary(ORMModel):
    """The draft as the Inbox needs it, flattened onto its comment."""

    id: int
    text: str
    status: DraftStatus
    final_text: str | None = None
    approved_by: str | None = None
    approved_at: AwareDatetime | None = None


class CommentWithDraft(CommentRead):
    """One Inbox row: the comment, its triage, and the draft awaiting a human.

    Joined server-side rather than fetched per row — the Inbox lists 50 at a
    time and 50 extra round-trips is the difference between a table that appears
    and one that fills in.
    """

    draft: ReplyDraftSummary | None = None
