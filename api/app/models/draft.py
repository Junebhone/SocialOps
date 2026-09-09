"""Reply drafts and the outbox that closes the approval loop (D3)."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import DraftStatus, sql_in
from app.models.base import Base, PrimaryKey


class ReplyDraft(Base):
    __tablename__ = "reply_drafts"
    __table_args__ = (
        CheckConstraint(sql_in("status", DraftStatus), name="status_allowed"),
        Index(None, "comment_id"),
        Index(None, "status"),
    )

    id: Mapped[PrimaryKey]
    comment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("comments.id", ondelete="CASCADE")
    )
    # What the agent wrote. Never overwritten — an edit goes to final_text, so
    # the agent's original output stays auditable.
    text: Mapped[str] = mapped_column(Text())
    # Provenance, not ownership: SET NULL, because purging an audit row must
    # never delete a draft a human approved.
    agent_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("agent_runs.id", ondelete="SET NULL")
    )
    status: Mapped[DraftStatus] = mapped_column(String(16), server_default="pending")
    # D3: a non-null final_text IS the record that a human edited the draft.
    # There is no "edited" status, deliberately.
    final_text: Mapped[str | None] = mapped_column(Text())
    # Free text, never a foreign key: there is no auth in Phase 1 (hard rule #12).
    approved_by: Mapped[str | None] = mapped_column(String(120))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Outbox(Base):
    __tablename__ = "outbox"
    __table_args__ = (
        # The 30s drain cron's predicate is WHERE sent_at IS NULL.
        Index(None, "sent_at"),
    )

    id: Mapped[PrimaryKey]
    reply_draft_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("reply_drafts.id", ondelete="CASCADE")
    )
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
