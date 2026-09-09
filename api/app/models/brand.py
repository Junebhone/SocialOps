"""Brands and the platform accounts they own."""

from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import Platform, sql_in
from app.models.base import Base, PrimaryKey


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[PrimaryKey]
    name: Mapped[str] = mapped_column(String(120))
    voice_guidelines: Mapped[str] = mapped_column(Text())
    # D16: one shape, three consumers. Media reads prohibited_content and
    # required_elements, content reads max_hashtags and tone, response reads
    # tone.avoid_words. The column is JSONB; the shape is enforced by the
    # BrandRules schema at the API boundary.
    brand_rules_json: Mapped[dict[str, Any]] = mapped_column(JSONB)


class PlatformAccount(Base):
    __tablename__ = "platform_accounts"
    __table_args__ = (
        CheckConstraint(sql_in("platform", Platform), name="platform_allowed"),
        # Postgres does not index foreign key columns automatically, and every
        # brand-scoped list endpoint (D17) filters on this one.
        Index(None, "brand_id"),
    )

    id: Mapped[PrimaryKey]
    brand_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("brands.id", ondelete="CASCADE"))
    platform: Mapped[Platform] = mapped_column(String(16))
    handle: Mapped[str] = mapped_column(String(120))
