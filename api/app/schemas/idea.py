"""Content idea schemas — the Ideation Agent's proposals."""

from pydantic import AwareDatetime

from app.enums import ContentIdeaStatus
from app.schemas.base import ORMModel


class ContentIdeaRead(ORMModel):
    id: int
    brand_id: int
    text: str
    source_signal: str | None = None
    agent_run_id: int | None = None
    status: ContentIdeaStatus
    created_at: AwareDatetime
