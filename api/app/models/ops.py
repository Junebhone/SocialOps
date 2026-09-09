"""The audit trail (hard rule #5) and the dead-letter queue (hard rule #7)."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import AgentName, AgentRunStatus, sql_in
from app.models.base import Base, PrimaryKey


class AgentRun(Base):
    """One row per agent invocation. The cost dashboard and the audit trail."""

    __tablename__ = "agent_runs"
    __table_args__ = (
        # D7: one composite index, so "what did this comment cost end to end" is
        # a single index lookup. Named explicitly because it spans two columns.
        Index("ix_agent_runs_entity", "entity_type", "entity_id"),
        Index(None, "brand_id"),
        CheckConstraint(sql_in("agent", AgentName), name="agent_allowed"),
        CheckConstraint(sql_in("status", AgentRunStatus), name="status_allowed"),
        # Deliberately NO check on entity_type — see the column comment.
    )

    id: Mapped[PrimaryKey]
    agent: Mapped[AgentName] = mapped_column(String(32))
    # D7: entity_type + entity_id replace an opaque input_ref so the run is
    # joinable back to what caused it. Unconstrained on purpose: a new agent
    # input type must not require a migration, which is the whole point.
    entity_type: Mapped[str] = mapped_column(String(32))
    # No ForeignKey: this is polymorphic — a comment id or an asset id.
    entity_id: Mapped[int] = mapped_column(BigInteger)
    # Denormalized (D7): per-brand cost otherwise needs a four-table join.
    brand_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("brands.id", ondelete="CASCADE"))
    # NULL on a failed run — there is no output to record. See the note on
    # assets.analysis_json: without none_as_null a failed run would store JSON
    # `'null'` and "which runs produced no output" would never match it.
    output_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    status: Mapped[AgentRunStatus] = mapped_column(String(16))
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    # D15: three states. 0 when the provider is Ollama, the priced value when
    # genai-prices knows the model, NULL when it cannot be priced. Numeric(12, 8)
    # because a sub-cent Bedrock call must not round to zero — that would report
    # a paid provider as free, which is exactly what D15 exists to prevent.
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    # Measured in worker/llm.py; Pydantic AI does not provide it.
    latency_ms: Mapped[int] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FailedJob(Base):
    """The DLQ. arq owns the retries that lead here (hard rule #7)."""

    __tablename__ = "failed_jobs"

    id: Mapped[PrimaryKey]
    job_type: Mapped[str] = mapped_column(String(64))
    # Must be sufficient to re-enqueue: step 9 adds a Retry button.
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    error: Mapped[str] = mapped_column(Text())
    attempts: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
