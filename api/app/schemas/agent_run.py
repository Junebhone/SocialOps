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
    # For a row written by ingest this is 1 and stays 1: it failed at the
    # boundary and arq never saw it. For a real job it is how many times arq
    # tried. It is not, and must not become, a count of button presses.
    attempts: int
    created_at: AwareDatetime
    # Whether this row can be put back on the queue. Sent by the API rather
    # than derived in the browser, so there is one definition of the rule.
    retryable: bool = False


class AgentTotals(ORMModel):
    """One row of the per-agent summary.

    Computed over every run matching the filters, NOT over the page. A totals
    row that silently summed page one would answer "what has this cost" with a
    number that changes when you paginate, which is worse than not showing it.
    """

    agent: AgentName
    runs: int
    errors: int
    input_tokens: int
    output_tokens: int
    # D15's three states, aggregated. This is the sum of the runs that HAD a
    # price; `unpriced` counts the ones that did not. SUM() skips NULLs
    # silently, so without that companion count a Phase 4 dashboard would
    # confidently under-report spend and look like a bargain.
    cost_usd: Decimal | None = None
    unpriced: int
    # Step 9 records per-agent p50/p95 in the README. Measuring it here rather
    # than in a one-off script means the number on the page and the number in
    # the README come from the same query.
    p50_latency_ms: int
    p95_latency_ms: int


class AgentRunPage(ORMModel):
    """Rows plus the summary, in one response.

    Together because they must agree: two endpoints would let the table and the
    totals be filtered differently, and the first person to notice would be
    someone asking why the numbers do not add up.
    """

    runs: list[AgentRunRead]
    totals: list[AgentTotals]
    total_runs: int
    # The window the matching runs span. Wall time for a replay is derivable
    # from the audit trail itself, so measuring it does not depend on a stopwatch
    # in a script surviving the whole drain — which, on an unattended two-hour
    # `measure-full`, is not a safe assumption.
    first_run_at: AwareDatetime | None = None
    last_run_at: AwareDatetime | None = None
