"""Insight schemas — the Insight Agent's qualitative performance markers."""

from pydantic import AwareDatetime

from app.schemas.base import ORMModel


class InsightRead(ORMModel):
    id: int
    brand_id: int
    text: str
    agent_run_id: int | None = None
    created_at: AwareDatetime
