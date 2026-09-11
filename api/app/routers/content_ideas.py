"""Content ideas: the Ideation Agent's proposals, and the button that asks for
more of them.

No outbox here, same reasoning as content_drafts.py: approving an idea is
inspiration only, not a pipeline trigger. The manager still uploads a photo
through the existing Content page as always — that pipeline is untouched.
"""

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.db import SessionDep
from app.enums import ContentIdeaStatus
from app.models import Brand, ContentIdea
from app.routers.params import BrandIdQuery, LimitQuery, OffsetQuery
from app.schemas.base import CreateModel
from app.schemas.idea import ContentIdeaRead
from app.services.queue import enqueue_ideation

router = APIRouter(prefix="/content_ideas", tags=["content_ideas"])

StatusFilter = Annotated[ContentIdeaStatus | None, Query(description="Filter by review status")]


class ContentIdeaUpdate(CreateModel):
    status: ContentIdeaStatus


class GenerateResult(CreateModel):
    enqueued: bool


@router.get("", response_model=list[ContentIdeaRead])
async def list_content_ideas(
    session: SessionDep,
    brand_id: BrandIdQuery,
    status: StatusFilter = None,
    limit: LimitQuery = 100,
    offset: OffsetQuery = 0,
) -> Any:
    stmt = (
        select(ContentIdea)
        .where(ContentIdea.brand_id == brand_id)
        .order_by(ContentIdea.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if status is not None:
        stmt = stmt.where(ContentIdea.status == status)

    return list((await session.execute(stmt)).scalars().all())


@router.patch("/{idea_id}", response_model=ContentIdeaRead)
async def update_content_idea(idea_id: int, payload: ContentIdeaUpdate, session: SessionDep) -> Any:
    idea = await session.get(ContentIdea, idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Content idea not found")

    idea.status = payload.status
    await session.commit()
    await session.refresh(idea)
    return idea


@router.post("/generate", response_model=GenerateResult)
async def generate_content_ideas(session: SessionDep, brand_id: BrandIdQuery) -> Any:
    """Enqueue one ideation run. Fire-and-forget: the Ideas page polls for the
    new rows the same way the Inbox polls for triage results."""
    brand = await session.get(Brand, brand_id)
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")

    enqueued = await enqueue_ideation(brand_id)
    return GenerateResult(enqueued=enqueued)
