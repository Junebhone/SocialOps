"""Content ideas: the Ideation Agent's proposals, pending human approval.

Deliberately no link to a content_draft or asset. An idea is inspiration text
shown on the Ideas page — approving one triggers nothing automatically. The
manager still uploads a photo through the existing Content page as always;
that pipeline is untouched. The Insight Agent reads raw post performance and
content_drafts text directly, not idea attribution, so there is no idea_id
anywhere downstream either.
"""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import ContentIdeaStatus, sql_in
from app.models.base import Base, PrimaryKey


class ContentIdea(Base):
    __tablename__ = "content_ideas"
    __table_args__ = (
        CheckConstraint(sql_in("status", ContentIdeaStatus), name="status_allowed"),
        Index(None, "brand_id"),
    )

    id: Mapped[PrimaryKey]
    brand_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("brands.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text())
    # Which data/trends.json entry inspired this idea. Free text, not a foreign
    # key: the trends file is not a database table (D31-style: a static seed
    # file, no admin UI, no migration to add or edit a trend).
    source_signal: Mapped[str | None] = mapped_column(String(255))
    agent_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("agent_runs.id", ondelete="SET NULL")
    )
    status: Mapped[ContentIdeaStatus] = mapped_column(String(16), server_default="proposed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
