"""Approval. This is where the human is in the loop (D3).

Approving does not "send" anything directly. It writes an `outbox` row, and the
worker drains that on a timer. There is no real platform in Phase 1, so the
outbox IS the publish step — and it is the seam a live integration would plug
into if the stretch goal is ever attempted.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.db import SessionDep
from app.enums import DraftStatus
from app.models import Outbox, ReplyDraft
from app.schemas.base import CreateModel
from app.schemas.draft import ReplyDraftRead

router = APIRouter(prefix="/reply_drafts", tags=["reply_drafts"])


class ReplyDraftUpdate(CreateModel):
    status: DraftStatus | None = None
    # A non-null final_text IS the record that a human edited the draft — there
    # is no "edited" status, deliberately (D3).
    final_text: str | None = None
    # Free text: there is no auth in Phase 1 (hard rule #12).
    approved_by: str | None = None


class BulkUpdate(CreateModel):
    ids: list[int]
    status: DraftStatus
    approved_by: str | None = None


def _apply(draft: ReplyDraft, update: ReplyDraftUpdate, session: SessionDep) -> None:
    """Move one draft, and queue it for publishing if it was approved."""
    if update.final_text is not None:
        draft.final_text = update.final_text

    if update.status is None:
        return

    draft.status = update.status
    if update.status != "approved":
        return

    draft.approved_by = update.approved_by or "demo-user"
    draft.approved_at = datetime.now(UTC)
    session.add(
        Outbox(
            reply_draft_id=draft.id,
            # Everything a publisher would need, captured at approval time so a
            # later edit cannot change what was already sent.
            payload_json={
                "reply_draft_id": draft.id,
                "comment_id": draft.comment_id,
                "text": draft.final_text or draft.text,
                "approved_by": draft.approved_by,
            },
        )
    )


@router.patch("/bulk", response_model=list[ReplyDraftRead])
async def bulk_update(payload: BulkUpdate, session: SessionDep) -> Any:
    """Batch approval. A stated demo criterion — approving 40 rows one at a
    time on stage is a bad look.

    Declared BEFORE /{draft_id} so "bulk" is not captured as an id.
    """
    if not payload.ids:
        raise HTTPException(status_code=422, detail="No draft ids supplied")

    drafts = list(
        (await session.execute(select(ReplyDraft).where(ReplyDraft.id.in_(payload.ids))))
        .scalars()
        .all()
    )
    if len(drafts) != len(set(payload.ids)):
        raise HTTPException(status_code=404, detail="One or more drafts not found")

    update = ReplyDraftUpdate(status=payload.status, approved_by=payload.approved_by)
    for draft in drafts:
        _apply(draft, update, session)

    await session.commit()
    for draft in drafts:
        await session.refresh(draft)
    return drafts


@router.patch("/{draft_id}", response_model=ReplyDraftRead)
async def update_reply_draft(
    draft_id: int, payload: ReplyDraftUpdate, session: SessionDep
) -> Any:
    draft = await session.get(ReplyDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Reply draft not found")

    _apply(draft, payload, session)
    await session.commit()
    await session.refresh(draft)
    return draft


@router.get("/{draft_id}", response_model=ReplyDraftRead)
async def get_reply_draft(draft_id: int, session: SessionDep) -> Any:
    draft = await session.get(ReplyDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Reply draft not found")
    return draft
