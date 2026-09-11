"""Insights: the Insight Agent's qualitative performance markers.

No numeric "predicted score" here, deliberately — a local model has no ground
truth to forecast how an unposted idea will do, and a fake precise number
would be dishonest. This table holds short pattern-observation text grounded
in real `posts.metrics_json`, the same way the Ideas page's chart is a real
computed engagement score, not a guess. Rows here feed back into the
Ideation Agent's `past_insights` context — this is the closed loop.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PrimaryKey


class Insight(Base):
    __tablename__ = "insights"
    __table_args__ = (Index(None, "brand_id"),)

    id: Mapped[PrimaryKey]
    brand_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("brands.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text())
    agent_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("agent_runs.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
