"""Weekly analytics summaries: the analytics agent's plain-English digest.

The numbers are computed by SQL (ADR-0005, `app/analytics_queries.py`) and
stored alongside the text in `stats_json`, so every sentence the model wrote can
be checked against the exact figures it was given.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PrimaryKey


class AnalyticsSummary(Base):
    __tablename__ = "analytics_summaries"
    __table_args__ = (Index(None, "brand_id"),)

    id: Mapped[PrimaryKey]
    brand_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("brands.id", ondelete="CASCADE"))
    # Inclusive calendar days in the brand's own time zone.
    period_start: Mapped[date] = mapped_column(Date())
    period_end: Mapped[date] = mapped_column(Date())
    text: Mapped[str] = mapped_column(Text())
    # The exact figures the text was written from — the audit trail for the prose.
    stats_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # NULL when no model ran: a week with no comments gets a fixed sentence
    # rather than asking a model to describe nothing.
    agent_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("agent_runs.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
