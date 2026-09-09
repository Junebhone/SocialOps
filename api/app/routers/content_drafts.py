"""Reviewing the captions the content agent wrote.

The reply-draft loop publishes through an outbox (D3). This one does not: a
content draft is copy a person takes away and posts themselves, so `approved`
is the terminal state and `ContentDraftStatus` has no `published`. Nothing here
writes an outbox row, and that is deliberate rather than unfinished.
"""

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.db import SessionDep
from app.enums import ContentDraftStatus, Platform
from app.models import Asset, ContentDraft
from app.routers.params import BrandIdQuery, LimitQuery, OffsetQuery
from app.schemas.asset import ContentDraftRead
from app.schemas.base import CreateModel

router = APIRouter(prefix="/content_drafts", tags=["content_drafts"])

PlatformFilter = Annotated[Platform | None, Query(description="Filter by platform")]
StatusFilter = Annotated[ContentDraftStatus | None, Query(description="Filter by review status")]


class ContentDraftUpdate(CreateModel):
    status: ContentDraftStatus | None = None
    # As with reply drafts (D3): a non-null final_text is what records that a
    # human edited the copy. The agent's original stays in `text`, so the
    # Agents page can still show what the model actually wrote.
    final_text: str | None = None


@router.get("", response_model=list[ContentDraftRead])
async def list_content_drafts(
    session: SessionDep,
    brand_id: BrandIdQuery,
    platform: PlatformFilter = None,
    status: StatusFilter = None,
    limit: LimitQuery = 100,
    offset: OffsetQuery = 0,
) -> Any:
    """Drafts for one brand, scoped through asset -> brand (D17).

    The Content page reads its drafts from `GET /assets`, which carries them
    already. This endpoint is for the questions that cut across assets — "every
    LinkedIn caption still waiting on review" — which a per-asset shape cannot
    answer without fetching everything.
    """
    stmt = (
        select(ContentDraft)
        .join(Asset, ContentDraft.asset_id == Asset.id)
        .where(Asset.brand_id == brand_id)
        .order_by(ContentDraft.asset_id.desc(), ContentDraft.id)
        .limit(limit)
        .offset(offset)
    )
    if platform is not None:
        stmt = stmt.where(ContentDraft.platform == platform)
    if status is not None:
        stmt = stmt.where(ContentDraft.status == status)

    return list((await session.execute(stmt)).scalars().all())


@router.patch("/{draft_id}", response_model=ContentDraftRead)
async def update_content_draft(
    draft_id: int, payload: ContentDraftUpdate, session: SessionDep
) -> Any:
    draft = await session.get(ContentDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Content draft not found")

    if payload.final_text is not None:
        draft.final_text = payload.final_text
    if payload.status is not None:
        draft.status = payload.status

    await session.commit()
    await session.refresh(draft)
    return draft
