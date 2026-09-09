"""Platform account and post schemas."""

from typing import Any

from pydantic import AwareDatetime, Field

from app.enums import Platform
from app.schemas.base import CreateModel, ORMModel


class PlatformAccountCreate(CreateModel):
    brand_id: int
    platform: Platform
    handle: str = Field(min_length=1, max_length=120)


class PlatformAccountRead(ORMModel):
    id: int
    brand_id: int
    platform: Platform
    handle: str


class PostCreate(CreateModel):
    account_id: int
    external_id: str = Field(min_length=1, max_length=128)
    text: str
    # AwareDatetime, not datetime: a naive timestamp is rejected at the boundary,
    # so the browser always receives an offset-bearing string.
    posted_at: AwareDatetime
    metrics_json: dict[str, Any] = Field(default_factory=dict)


class PostRead(ORMModel):
    id: int
    account_id: int
    external_id: str
    text: str
    posted_at: AwareDatetime
    metrics_json: dict[str, Any]
