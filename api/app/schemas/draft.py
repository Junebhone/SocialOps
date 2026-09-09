"""Reply draft and outbox schemas (D3)."""

from typing import Any

from pydantic import AwareDatetime

from app.enums import DraftStatus
from app.schemas.base import ORMModel


class ReplyDraftRead(ORMModel):
    id: int
    comment_id: int
    text: str
    agent_run_id: int | None = None
    status: DraftStatus
    # Non-null means a human edited the draft. There is no "edited" status.
    final_text: str | None = None
    approved_by: str | None = None
    approved_at: AwareDatetime | None = None


class OutboxRead(ORMModel):
    id: int
    reply_draft_id: int
    payload_json: dict[str, Any]
    created_at: AwareDatetime
    sent_at: AwareDatetime | None = None
