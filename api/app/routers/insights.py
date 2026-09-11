"""Insight markers, and the button that asks for more of them.

No PATCH here, unlike content_ideas: a marker is not reviewed or approved,
it is read. The only human action on this page is triggering a new run.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.db import SessionDep
from app.models import Brand, Insight
from app.routers.params import BrandIdQuery, LimitQuery, OffsetQuery
from app.schemas.base import CreateModel
from app.schemas.insight import InsightRead
from app.services.queue import enqueue_insight

router = APIRouter(prefix="/insights", tags=["insights"])


class GenerateResult(CreateModel):
    enqueued: bool


@router.get("", response_model=list[InsightRead])
async def list_insights(
    session: SessionDep, brand_id: BrandIdQuery, limit: LimitQuery = 100, offset: OffsetQuery = 0
) -> Any:
    stmt = (
        select(Insight)
        .where(Insight.brand_id == brand_id)
        .order_by(Insight.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.post("/generate", response_model=GenerateResult)
async def generate_insights(session: SessionDep, brand_id: BrandIdQuery) -> Any:
    """Enqueue one insight run over the brand's real post performance."""
    brand = await session.get(Brand, brand_id)
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")

    enqueued = await enqueue_insight(brand_id)
    return GenerateResult(enqueued=enqueued)
