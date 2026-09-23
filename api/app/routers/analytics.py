"""Per-brand analytics: sentiment trend, category mix, time to first response.

ADR-0005: computed live from the source tables on every request. No rollup
table and no cache (hard rule #2), and no model: a 2B model cannot be trusted
to add up. Days are bucketed in the brand's own time zone (`brands.timezone`),
so "Monday" is the brand's Monday, not UTC's.
"""

from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from app.db import SessionDep
from app.models import Brand
from app.routers.params import BrandIdQuery
from app.schemas.analytics import (
    AnalyticsRead,
    CategoryPoint,
    ResponseTimeBucket,
    ResponseTimes,
    SentimentPoint,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])

DEFAULT_DAYS = 90
MAX_DAYS = 366

# The brand join and the date-range filter every query shares. `local_day` is
# the comment's calendar day in the brand's time zone.
_BRAND_COMMENTS = """
    FROM comments c
    JOIN posts p ON p.id = c.post_id
    JOIN platform_accounts a ON a.id = p.account_id
    WHERE a.brand_id = :brand_id
      AND (c.created_at AT TIME ZONE :tz)::date BETWEEN :start AND :end
"""

_SENTIMENT_SQL = text(
    f"""
    SELECT (c.created_at AT TIME ZONE :tz)::date AS day,
           AVG(c.sentiment)::float AS avg_sentiment,
           COUNT(*) AS comments
    {_BRAND_COMMENTS}
      AND c.sentiment IS NOT NULL
    GROUP BY day
    ORDER BY day
    """
)

_CATEGORY_SQL = text(
    f"""
    SELECT (c.created_at AT TIME ZONE :tz)::date AS day,
           c.category AS category,
           COUNT(*) AS comments
    {_BRAND_COMMENTS}
      AND c.category IS NOT NULL
    GROUP BY day, c.category
    ORDER BY day, c.category
    """
)

# Buckets are fixed, not computed from the data, so two date ranges are
# comparable at a glance. GREATEST(0, ...) guards a comment whose platform
# timestamp is slightly ahead of our clock.
_RESPONSE_SQL = text(
    """
    WITH rt AS (
        SELECT GREATEST(0, EXTRACT(EPOCH FROM (o.sent_at - c.created_at)))::float8 AS s
        FROM outbox o
        JOIN reply_drafts d ON d.id = o.reply_draft_id
        JOIN comments c ON c.id = d.comment_id
        JOIN posts p ON p.id = c.post_id
        JOIN platform_accounts a ON a.id = p.account_id
        WHERE a.brand_id = :brand_id
          AND (c.created_at AT TIME ZONE :tz)::date BETWEEN :start AND :end
          AND o.sent_at IS NOT NULL
    )
    SELECT COUNT(*) AS published,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY s) AS p50,
           percentile_cont(0.95) WITHIN GROUP (ORDER BY s) AS p95,
           COUNT(*) FILTER (WHERE s < 60) AS b0,
           COUNT(*) FILTER (WHERE s >= 60 AND s < 300) AS b1,
           COUNT(*) FILTER (WHERE s >= 300 AND s < 900) AS b2,
           COUNT(*) FILTER (WHERE s >= 900 AND s < 3600) AS b3,
           COUNT(*) FILTER (WHERE s >= 3600 AND s < 14400) AS b4,
           COUNT(*) FILTER (WHERE s >= 14400 AND s < 86400) AS b5,
           COUNT(*) FILTER (WHERE s >= 86400) AS b6
    FROM rt
    """
)

# "Today" comes from Postgres, not Python: the database already knows every
# IANA zone, and the slim API image need not ship tzdata to agree with it.
_TODAY_SQL = text("SELECT (now() AT TIME ZONE :tz)::date")

_BUCKET_LABELS = ["< 1 min", "1-5 min", "5-15 min", "15-60 min", "1-4 h", "4-24 h", "> 1 day"]


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
    brand = await session.get(Brand, brand_id)
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")

    today = (await session.execute(_TODAY_SQL, {"tz": brand.timezone})).scalar_one()
    end = end or today
    start = start or end - timedelta(days=DEFAULT_DAYS - 1)
    if start > end:
        raise HTTPException(status_code=422, detail="'from' must be on or before 'to'")
    if (end - start).days + 1 > MAX_DAYS:
        raise HTTPException(status_code=422, detail=f"Date range is limited to {MAX_DAYS} days")

    params = {"brand_id": brand_id, "tz": brand.timezone, "start": start, "end": end}
    sentiment = (await session.execute(_SENTIMENT_SQL, params)).mappings().all()
    categories = (await session.execute(_CATEGORY_SQL, params)).mappings().all()
    rt = (await session.execute(_RESPONSE_SQL, params)).mappings().one()

    return AnalyticsRead(
        brand_id=brand_id,
        timezone=brand.timezone,
        start=start,
        end=end,
        sentiment=[SentimentPoint(**row) for row in sentiment],
        categories=[CategoryPoint(**row) for row in categories],
        response_times=ResponseTimes(
            published=rt["published"],
            p50_seconds=rt["p50"],
            p95_seconds=rt["p95"],
            histogram=[
                ResponseTimeBucket(label=label, comments=rt[f"b{i}"])
                for i, label in enumerate(_BUCKET_LABELS)
            ],
        ),
    )
