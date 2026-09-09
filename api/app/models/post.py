"""Posts and the comments on them.

`comments` carries the constraint the whole replay story rests on (D9) and the
ordinal sentiment check (D8).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import CommentCategory, CommentStatus, Urgency, sql_in, sql_in_or_null
from app.models.base import Base, PrimaryKey


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        # Makes `make seed` re-runnable for the same reason comments needs one.
        UniqueConstraint("account_id", "external_id"),
        Index(None, "account_id"),
    )

    id: Mapped[PrimaryKey]
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("platform_accounts.id", ondelete="CASCADE")
    )
    external_id: Mapped[str] = mapped_column(String(128))
    text: Mapped[str] = mapped_column(Text())
    # The platform's publish time, not our insert time.
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    metrics_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=sql_text("'{}'::jsonb")
    )


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        # D9. This exact pair is what step 4's POST /ingest/comments targets with
        # ON CONFLICT (post_id, external_id) DO NOTHING, which is what makes
        # replaying a 2,000-comment dump twice insert nothing the second time.
        UniqueConstraint("post_id", "external_id"),
        # D8: enforced at the database so a miscalibrated model cannot poison the
        # eval numbers with a sentiment of 7.
        CheckConstraint("sentiment BETWEEN -2 AND 2", name="sentiment_range"),
        CheckConstraint(sql_in_or_null("category", CommentCategory), name="category_allowed"),
        CheckConstraint(sql_in_or_null("urgency", Urgency), name="urgency_allowed"),
        CheckConstraint(sql_in("status", CommentStatus), name="status_allowed"),
        Index(None, "post_id"),
        Index(None, "status"),
    )

    id: Mapped[PrimaryKey]
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("posts.id", ondelete="CASCADE"))
    # NOT NULL is load-bearing: Postgres treats NULLs as distinct in a unique
    # index, so a nullable external_id would make the D9 constraint a no-op and
    # re-insert every comment on the second replay.
    external_id: Mapped[str] = mapped_column(String(128))
    author: Mapped[str] = mapped_column(String(120))
    # Text, not a bounded VARCHAR — comment bodies are unbounded in practice.
    text: Mapped[str] = mapped_column(Text())
    # The platform's comment time, supplied by ingest. No server_default: a
    # comment written now is not a comment posted now.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # The four triage outputs. All nullable: the row is inserted at ingest, and
    # triage fills these in later.
    category: Mapped[CommentCategory | None] = mapped_column(String(16))
    sentiment: Mapped[int | None] = mapped_column(SmallInteger)
    needs_reply: Mapped[bool | None] = mapped_column()
    urgency: Mapped[Urgency | None] = mapped_column(String(4))

    status: Mapped[CommentStatus] = mapped_column(String(16), server_default="new")
