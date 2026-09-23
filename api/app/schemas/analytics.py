"""Analytics response shapes (ADR-0005).

Every number here is computed by SQL in `app/analytics_queries.py`, never by a
model. Days are calendar days in the brand's own time zone.
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.base import ORMModel


class SentimentPoint(BaseModel):
    day: date
    # Mean of the -2..2 ordinal (D8), so it is itself between -2 and 2.
    avg_sentiment: float
    comments: int


class CategoryPoint(BaseModel):
    day: date
    category: str
    comments: int


class ResponseTimeBucket(BaseModel):
    label: str
    comments: int


class ResponseTimes(BaseModel):
    """Comment posted -> reply published (`outbox.sent_at`), published replies only."""

    published: int
    # None when nothing was published in the range: there is no median of zero rows.
    p50_seconds: float | None
    p95_seconds: float | None
    histogram: list[ResponseTimeBucket]


class AnalyticsRead(BaseModel):
    brand_id: int
    timezone: str
    start: date
    end: date
    sentiment: list[SentimentPoint]
    categories: list[CategoryPoint]
    response_times: ResponseTimes


class AnalyticsSummaryRead(ORMModel):
    """One weekly summary. `stats_json` is exactly what the agent was given."""

    id: int
    brand_id: int
    period_start: date
    period_end: date
    text: str
    stats_json: dict[str, Any]
    agent_run_id: int | None
    created_at: datetime


class GenerateSummaryResult(BaseModel):
    enqueued: bool
