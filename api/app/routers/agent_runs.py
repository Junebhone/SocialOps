"""The audit trail, on a page (hard rule #5).

One row per agent invocation is what makes two questions answerable: what did
this one comment cost end to end, and which runs failed. Both are joins on
D7's (entity_type, entity_id) index, which is why that index exists.

D1 cut the analytics agent and the charts. This is a table, deliberately — the
value here is that every number is real and traceable to a row, not that it is
plotted.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import Select, case, func, select

from app.db import SessionDep
from app.enums import AgentName, AgentRunStatus
from app.models import AgentRun
from app.routers.params import BrandIdQuery, LimitQuery, OffsetQuery
from app.schemas.agent_run import AgentRunPage

router = APIRouter(prefix="/agent_runs", tags=["agent_runs"])

AgentFilter = Annotated[AgentName | None, Query(description="Filter by agent")]
StatusFilter = Annotated[AgentRunStatus | None, Query(description="Filter by run status")]
EntityTypeFilter = Annotated[str | None, Query(description="Filter by entity type")]
EntityIdFilter = Annotated[
    int | None,
    Query(description="Filter by entity id. With entity_type, this is the D7 index lookup."),
]


def _filtered[T: tuple[Any, ...]](
    stmt: Select[T],
    brand_id: int,
    agent: AgentName | None,
    status: AgentRunStatus | None,
    entity_type: str | None,
    entity_id: int | None,
) -> Select[T]:
    """One predicate builder for both the page and the totals.

    Shared rather than written twice: the totals exist to describe exactly the
    rows in the table, and two copies of this would eventually disagree.
    """
    stmt = stmt.where(AgentRun.brand_id == brand_id)
    if agent is not None:
        stmt = stmt.where(AgentRun.agent == agent)
    if status is not None:
        stmt = stmt.where(AgentRun.status == status)
    if entity_type is not None:
        stmt = stmt.where(AgentRun.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AgentRun.entity_id == entity_id)
    return stmt


@router.get("", response_model=AgentRunPage)
async def list_agent_runs(
    session: SessionDep,
    brand_id: BrandIdQuery,
    agent: AgentFilter = None,
    status: StatusFilter = None,
    entity_type: EntityTypeFilter = None,
    entity_id: EntityIdFilter = None,
    limit: LimitQuery = 100,
    offset: OffsetQuery = 0,
) -> Any:
    """Runs for one brand, newest first, with a per-agent summary.

    `brand_id` is required (D17), and it is a real column here rather than a
    join: D7 denormalized it precisely so per-brand cost does not need a
    four-table join on the page that reports cost.
    """
    rows = (
        await session.execute(
            _filtered(select(AgentRun), brand_id, agent, status, entity_type, entity_id)
            .order_by(AgentRun.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()

    totals = (
        await session.execute(
            _filtered(
                select(
                    AgentRun.agent,
                    func.count().label("runs"),
                    func.count(case((AgentRun.status == "error", 1))).label("errors"),
                    func.coalesce(func.sum(AgentRun.input_tokens), 0).label("input_tokens"),
                    func.coalesce(func.sum(AgentRun.output_tokens), 0).label("output_tokens"),
                    # No coalesce to 0: an agent whose every run is unpriced must
                    # report NULL, so the page renders an em dash rather than
                    # claiming it was free (D15).
                    func.sum(AgentRun.cost_usd).label("cost_usd"),
                    func.count(case((AgentRun.cost_usd.is_(None), 1))).label("unpriced"),
                    # percentile_cont interpolates, so it needs rounding back to
                    # the integer milliseconds the column stores.
                    func.round(
                        func.percentile_cont(0.5).within_group(AgentRun.latency_ms)
                    ).label("p50_latency_ms"),
                    func.round(
                        func.percentile_cont(0.95).within_group(AgentRun.latency_ms)
                    ).label("p95_latency_ms"),
                ),
                brand_id,
                agent,
                status,
                entity_type,
                entity_id,
            )
            .group_by(AgentRun.agent)
            .order_by(AgentRun.agent)
        )
    ).all()

    return AgentRunPage(
        runs=list(rows),
        totals=list(totals),
        # The number the table is a page OF, so "showing 100 of 485" is honest.
        total_runs=sum(row.runs for row in totals),
    )
