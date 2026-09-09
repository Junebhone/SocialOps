"""Agent run and failed job schemas — the audit trail on the wire."""

from decimal import Decimal
from typing import Any

from pydantic import AwareDatetime

from app.enums import AgentName, AgentRunStatus
from app.schemas.base import ORMModel


class AgentRunRead(ORMModel):
    id: int
    agent: AgentName
    # `str`, not the EntityType Literal: D7's stated virtue is that a new agent
    # input type needs no migration, and a Literal here would reintroduce a
    # code change for exactly that case.
    entity_type: str
    entity_id: int
    brand_id: int
    output_json: dict[str, Any] | None = None
    status: AgentRunStatus
    input_tokens: int
    output_tokens: int
    # D15. Serializes as a JSON string ("0.00001234"), and None stays null.
    # Do NOT add a float serializer: float would round a sub-cent Bedrock call
    # toward zero, which is the confusion D15 exists to prevent. The client
    # renders null as an em dash, never as $0.00.
    cost_usd: Decimal | None = None
    latency_ms: int
    error: str | None = None
    created_at: AwareDatetime


class FailedJobRead(ORMModel):
    id: int
    job_type: str
    payload_json: dict[str, Any]
    error: str
    attempts: int
    created_at: AwareDatetime
