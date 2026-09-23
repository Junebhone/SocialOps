"""The analytics numbers, computed once, in one place (ADR-0005).

Both the API (`GET /analytics`) and the worker (the weekly summary agent)
import this module, so the dashboard and the summary can never disagree about
a figure. Deliberately free of FastAPI: the worker imports it and does not have
FastAPI installed (the same boundary D24 draws for `app/storage.py`).

Every number is SQL, never a model. Days are calendar days in the brand's own
time zone.
"""

from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.analytics import (
    AnalyticsRead,
    CategoryPoint,
    ResponseTimeBucket,
    ResponseTimes,
    SentimentPoint,
)

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
# IANA zone, and the slim images need not ship tzdata to agree with it.
_TODAY_SQL = text("SELECT (now() AT TIME ZONE :tz)::date")

BUCKET_LABELS = ["< 1 min", "1-5 min", "5-15 min", "15-60 min", "1-4 h", "4-24 h", "> 1 day"]


async def today_in(session: AsyncSession, tz: str) -> date:
    """Today's calendar date in the given IANA time zone."""
    today: date = (await session.execute(_TODAY_SQL, {"tz": tz})).scalar_one()
    return today


async def compute_analytics(
    session: AsyncSession, brand_id: int, tz: str, start: date, end: date
) -> AnalyticsRead:
    """Sentiment trend, category mix and time to first response for one brand.

    `start` and `end` are inclusive calendar days in `tz`. The caller has
    already checked the brand exists and the range is sane.
    """
    params = {"brand_id": brand_id, "tz": tz, "start": start, "end": end}
    sentiment = (await session.execute(_SENTIMENT_SQL, params)).mappings().all()
    categories = (await session.execute(_CATEGORY_SQL, params)).mappings().all()
    rt = (await session.execute(_RESPONSE_SQL, params)).mappings().one()

    return AnalyticsRead(
        brand_id=brand_id,
        timezone=tz,
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
                for i, label in enumerate(BUCKET_LABELS)
            ],
        ),
    )
