"""Asset and content draft schemas, including the media agent's output contract."""

from pydantic import BaseModel

from app.enums import ContentDraftStatus, Platform
from app.schemas.base import ORMModel


class BrandCheck(BaseModel):
    passes: bool
    issues: list[str]


class AssetAnalysis(BaseModel):
    """The media agent's contract (CLAUDE.md, agents section)."""

    description: str
    detected_text: list[str]
    brand_check: BrandCheck


class AssetRead(ORMModel):
    id: int
    brand_id: int
    filename: str
    storage_key: str
    mime: str
    analysis_json: AssetAnalysis | None = None


class ContentDraftRead(ORMModel):
    id: int
    asset_id: int
    platform: Platform
    text: str
    hashtags_json: list[str]
    agent_run_id: int | None = None
    status: ContentDraftStatus
    final_text: str | None = None
