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
    # Not a column: whatever `StorageBackend.url()` returns for the key. It is
    # the API route today and a presigned S3 URL in Phase 4, and the web app is
    # never told which — that is the whole point of hard rule #9's interface.
    url: str


class ContentDraftRead(ORMModel):
    id: int
    asset_id: int
    platform: Platform
    text: str
    hashtags_json: list[str]
    agent_run_id: int | None = None
    status: ContentDraftStatus
    final_text: str | None = None


class AssetWithDrafts(AssetRead):
    """One Content page card: the image, what the media agent saw, and the three
    captions written from it.

    Joined server-side for the same reason `CommentWithDraft` is: the card is
    the unit a person acts on, and making the browser fetch drafts per asset
    would be an N+1 over a list that is already scoped to one brand.
    """

    drafts: list[ContentDraftRead] = []
