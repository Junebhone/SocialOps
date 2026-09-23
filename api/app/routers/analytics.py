"""Per-brand analytics: the numbers, and the analytics agent's weekly summary.

ADR-0005: the numbers are computed live from the source tables on every
request. No rollup table and no cache (hard rule #2), and no model: a 2B model
cannot be trusted to add up. The SQL lives in `app/analytics_queries.py` so the
worker's summary agent reads exactly the same figures the dashboard shows.
"""

from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.analytics_queries import compute_analytics, today_in
from app.db import SessionDep
from app.models import AnalyticsSummary, Brand
from app.routers.params import BrandIdQuery, LimitQuery
from app.schemas.analytics import AnalyticsRead, AnalyticsSummaryRead, GenerateSummaryResult
from app.services.queue import enqueue_analytics_summary

router = APIRouter(prefix="/analytics", tags=["analytics"])

DEFAULT_DAYS = 90
MAX_DAYS = 366


async def _brand_or_404(session: SessionDep, brand_id: int) -> Brand:
    brand = await session.get(Brand, brand_id)
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


@router.get("", response_model=AnalyticsRead)
async def get_analytics(
    session: SessionDep,
    brand_id: BrandIdQuery,
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
) -> Any:
    """Everything the Analytics page draws, for one brand and one date range.

    `from` and `to` are inclusive calendar days in the brand's time zone. With
    neither given, the range is the last 90 days up to today.
    """
    brand = await _brand_or_404(session, brand_id)

    end = end or await today_in(session, brand.timezone)
    start = start or end - timedelta(days=DEFAULT_DAYS - 1)
    if start > end:
        raise HTTPException(status_code=422, detail="'from' must be on or before 'to'")
    if (end - start).days + 1 > MAX_DAYS:
        raise HTTPException(status_code=422, detail=f"Date range is limited to {MAX_DAYS} days")

    return await compute_analytics(session, brand_id, brand.timezone, start, end)


@router.get("/summaries", response_model=list[AnalyticsSummaryRead])
async def list_summaries(
    session: SessionDep, brand_id: BrandIdQuery, limit: LimitQuery = 10
) -> Any:
    """The analytics agent's weekly summaries for one brand, newest first."""
    stmt = (
        select(AnalyticsSummary)
        .where(AnalyticsSummary.brand_id == brand_id)
        .order_by(AnalyticsSummary.id.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.post("/summaries/generate", response_model=GenerateSummaryResult)
async def generate_summary(session: SessionDep, brand_id: BrandIdQuery) -> Any:
    """Enqueue a summary of the last 7 days now, rather than waiting for Monday."""
    await _brand_or_404(session, brand_id)
    return GenerateSummaryResult(enqueued=await enqueue_analytics_summary(brand_id))
