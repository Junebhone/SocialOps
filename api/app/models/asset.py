"""Uploaded assets and the per-platform drafts generated from them."""

from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import ContentDraftStatus, Platform, sql_in
from app.models.base import Base, PrimaryKey


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (Index(None, "brand_id"),)

    id: Mapped[PrimaryKey]
    brand_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("brands.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255))
    # An opaque StorageBackend key — never a filesystem path and never a URL, so
    # the Phase 4 move to S3 needs no data migration (hard rule #9).
    storage_key: Mapped[str] = mapped_column(String(512))
    mime: Mapped[str] = mapped_column(String(128))
    # NULL until the media agent runs, and NULL is the marker both the
    # orchestrator's idempotency guard and the requeue recovery path read.
    #
# `none_as_null=True` is not decoration. SQLAlchemy's JSON types render an
# ASSIGNED Python `None` as JSON `'null'`, not SQL NULL — so `column = None`
# stores a value, and `WHERE column IS NULL` then never matches it. Measured:
# an asset written with `analysis_json=None` stored `'null'::jsonb`, and the
# recovery query for unanalysed assets silently found nothing.
#
# For both of these columns NULL means "not produced yet", and there is no such
# thing as an analysis or an output whose legitimate value is JSON null, so the
# two must not be distinguishable.
    analysis_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))


class ContentDraft(Base):
    __tablename__ = "content_drafts"
    __table_args__ = (
        CheckConstraint(sql_in("platform", Platform), name="platform_allowed"),
        CheckConstraint(sql_in("status", ContentDraftStatus), name="status_allowed"),
        Index(None, "asset_id"),
    )

    id: Mapped[PrimaryKey]
    asset_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("assets.id", ondelete="CASCADE"))
    platform: Mapped[Platform] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text())
    # Kept out of `text` so the content agent's max_hashtags rule (D16) is
    # checkable without parsing prose.
    hashtags_json: Mapped[list[str]] = mapped_column(JSONB, server_default=sql_text("'[]'::jsonb"))
    agent_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("agent_runs.id", ondelete="SET NULL")
    )
    status: Mapped[ContentDraftStatus] = mapped_column(String(16), server_default="pending")
    final_text: Mapped[str | None] = mapped_column(Text())
