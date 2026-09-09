"""The audit trail endpoint (hard rule #5).

The table is easy. The totals are where this can be quietly wrong: summed over
the wrong rows, or summed over a NULL cost and reported as free.
"""

from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import a_brand, agent_run


async def test_listing_runs_requires_a_brand(client: AsyncClient) -> None:
    assert (await client.get("/agent_runs")).status_code == 422


async def test_runs_are_scoped_to_their_brand(
    client: AsyncClient, session: AsyncSession
) -> None:
    """brand_id is a real column here, not a join — D7 denormalized it so the
    page that reports per-brand cost does not need a four-table join."""
    ridgeline = await a_brand(session, name="Ridgeline Roasters")
    fieldnote = await a_brand(session, name="Fieldnote")
    await agent_run(session, ridgeline)
    await agent_run(session, fieldnote)
    await agent_run(session, fieldnote)

    body = (await client.get("/agent_runs", params={"brand_id": ridgeline.id})).json()

    assert body["total_runs"] == 1


async def test_everything_a_comment_cost_is_one_lookup(
    client: AsyncClient, session: AsyncSession
) -> None:
    """D7's whole reason for existing: entity_type + entity_id, indexed
    together, so "what did this one comment cost end to end" is a query rather
    than a reconstruction."""
    brand = await a_brand(session)
    await agent_run(session, brand, "triage", entity_id=41)
    await agent_run(session, brand, "response", entity_id=41)
    await agent_run(session, brand, "triage", entity_id=42)
    await agent_run(session, brand, "media", entity_type="asset", entity_id=41)

    body = (
        await client.get(
            "/agent_runs",
            params={"brand_id": brand.id, "entity_type": "comment", "entity_id": 41},
        )
    ).json()

    assert body["total_runs"] == 2
    assert sorted(run["agent"] for run in body["runs"]) == ["response", "triage"]


async def test_filtering_by_agent_and_status(
    client: AsyncClient, session: AsyncSession
) -> None:
    brand = await a_brand(session)
    await agent_run(session, brand, "triage")
    await agent_run(session, brand, "triage", status="error", error="boom")
    await agent_run(session, brand, "response")

    ok_triage = (
        await client.get(
            "/agent_runs", params={"brand_id": brand.id, "agent": "triage", "status": "ok"}
        )
    ).json()

    assert ok_triage["total_runs"] == 1


async def test_totals_cover_every_matching_run_not_just_the_page(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The bug this guards. A totals row summed over page one answers "what has
    this cost" with a number that changes when you paginate — which is worse
    than showing no total at all.
    """
    brand = await a_brand(session)
    for _ in range(5):
        await agent_run(session, brand, "triage", input_tokens=100, output_tokens=10)

    body = (await client.get("/agent_runs", params={"brand_id": brand.id, "limit": 2})).json()

    assert len(body["runs"]) == 2
    assert body["total_runs"] == 5
    triage = next(row for row in body["totals"] if row["agent"] == "triage")
    assert triage["runs"] == 5
    assert triage["input_tokens"] == 500


async def test_totals_are_per_agent(client: AsyncClient, session: AsyncSession) -> None:
    brand = await a_brand(session)
    await agent_run(session, brand, "triage", input_tokens=10)
    await agent_run(session, brand, "triage", input_tokens=20)
    await agent_run(session, brand, "response", input_tokens=100)

    body = (await client.get("/agent_runs", params={"brand_id": brand.id})).json()

    totals = {row["agent"]: row for row in body["totals"]}
    assert totals["triage"]["input_tokens"] == 30
    assert totals["response"]["input_tokens"] == 100


async def test_errors_are_counted_separately(
    client: AsyncClient, session: AsyncSession
) -> None:
    brand = await a_brand(session)
    await agent_run(session, brand, "triage")
    await agent_run(session, brand, "triage", status="error", error="ValidationError: nope")

    body = (await client.get("/agent_runs", params={"brand_id": brand.id})).json()

    triage = next(row for row in body["totals"] if row["agent"] == "triage")
    assert triage["runs"] == 2
    assert triage["errors"] == 1


# --- D15: three states, all the way through the aggregate ------------------


async def test_an_ollama_run_costs_zero_not_null(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Free because we own the hardware. That is a fact, and it is a different
    fact from "we could not price this"."""
    brand = await a_brand(session)
    await agent_run(session, brand, cost_usd=Decimal(0))

    body = (await client.get("/agent_runs", params={"brand_id": brand.id})).json()

    assert Decimal(body["runs"][0]["cost_usd"]) == 0
    assert body["totals"][0]["unpriced"] == 0


async def test_an_agent_with_no_priceable_run_totals_to_null(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Not zero. The page renders null as an em dash, and reporting a paid
    provider as free is exactly the failure D15 exists to prevent."""
    brand = await a_brand(session)
    await agent_run(session, brand, "triage", cost_usd=None)
    await agent_run(session, brand, "triage", cost_usd=None)

    body = (await client.get("/agent_runs", params={"brand_id": brand.id})).json()

    triage = next(row for row in body["totals"] if row["agent"] == "triage")
    assert triage["cost_usd"] is None
    assert triage["unpriced"] == 2


async def test_a_mixed_total_reports_both_the_sum_and_what_it_missed(
    client: AsyncClient, session: AsyncSession
) -> None:
    """SUM() skips NULLs silently. Without the companion count, a dashboard with
    one unpriced call in ten confidently under-reports spend and looks cheap."""
    brand = await a_brand(session)
    await agent_run(session, brand, "response", cost_usd=Decimal("0.00012300"))
    await agent_run(session, brand, "response", cost_usd=Decimal("0.00004500"))
    await agent_run(session, brand, "response", cost_usd=None)

    body = (await client.get("/agent_runs", params={"brand_id": brand.id})).json()

    response = next(row for row in body["totals"] if row["agent"] == "response")
    assert Decimal(response["cost_usd"]) == Decimal("0.00016800")
    assert response["unpriced"] == 1
    assert response["runs"] == 3


async def test_a_sub_cent_cost_survives_the_round_trip(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Serialized as a string, never a float. A float would round a real Bedrock
    call toward zero on the way to the browser."""
    brand = await a_brand(session)
    await agent_run(session, brand, cost_usd=Decimal("0.00000123"))

    body = (await client.get("/agent_runs", params={"brand_id": brand.id})).json()

    assert isinstance(body["runs"][0]["cost_usd"], str)
    assert Decimal(body["runs"][0]["cost_usd"]) == Decimal("0.00000123")


# --- latency percentiles (step 9 reads these) ------------------------------


async def test_p50_and_p95_come_from_the_same_query_the_page_uses(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Step 9 records per-agent p50/p95 in the README. Computing it here rather
    than in a one-off script means the README and the page cannot disagree."""
    brand = await a_brand(session)
    for latency in range(1, 101):
        await agent_run(session, brand, "triage", latency_ms=latency)

    body = (await client.get("/agent_runs", params={"brand_id": brand.id})).json()

    triage = next(row for row in body["totals"] if row["agent"] == "triage")
    # percentile_cont interpolates; 1..100 puts p50 at 50.5 and p95 at 95.05.
    assert triage["p50_latency_ms"] in (50, 51)
    assert triage["p95_latency_ms"] == 95


async def test_newest_run_first(client: AsyncClient, session: AsyncSession) -> None:
    brand = await a_brand(session)
    first = await agent_run(session, brand, "triage")
    second = await agent_run(session, brand, "response")

    body = (await client.get("/agent_runs", params={"brand_id": brand.id})).json()

    assert [run["id"] for run in body["runs"]] == [second.id, first.id]
