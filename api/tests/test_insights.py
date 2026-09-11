"""What the Insights page reads, and the "Generate insights" button."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import FakeQueue
from tests.factories import a_brand, an_insight

# --- GET /insights -----------------------------------------------------


async def test_listing_insights_requires_a_brand(client: AsyncClient) -> None:
    assert (await client.get("/insights")).status_code == 422


async def test_insights_are_scoped_to_their_brand(
    client: AsyncClient, session: AsyncSession
) -> None:
    ridgeline = await a_brand(session, name="Ridgeline Roasters")
    fieldnote = await a_brand(session, name="Fieldnote")
    await an_insight(session, ridgeline, text="Roastery pattern.")
    await an_insight(session, fieldnote, text="Skincare pattern.")

    rows = (await client.get("/insights", params={"brand_id": ridgeline.id})).json()

    assert [row["text"] for row in rows] == ["Roastery pattern."]


async def test_newest_insight_first(client: AsyncClient, session: AsyncSession) -> None:
    brand = await a_brand(session)
    await an_insight(session, brand, text="First.")
    await an_insight(session, brand, text="Second.")

    rows = (await client.get("/insights", params={"brand_id": brand.id})).json()

    assert [row["text"] for row in rows] == ["Second.", "First."]


# --- POST /insights/generate --------------------------------------------


async def test_generate_enqueues_one_insight_job(
    client: AsyncClient, session: AsyncSession, queue: FakeQueue
) -> None:
    brand = await a_brand(session)

    body = (await client.post("/insights/generate", params={"brand_id": brand.id})).json()

    assert body["enqueued"] is True
    function, args = next(iter(queue.jobs.values()))
    assert function == "process_insight"
    assert args == (brand.id,)


async def test_generate_twice_enqueues_two_jobs(
    client: AsyncClient, session: AsyncSession, queue: FakeQueue
) -> None:
    brand = await a_brand(session)

    await client.post("/insights/generate", params={"brand_id": brand.id})
    await client.post("/insights/generate", params={"brand_id": brand.id})

    assert len(queue.jobs) == 2


async def test_generate_for_an_unknown_brand_is_a_404(client: AsyncClient) -> None:
    response = await client.post("/insights/generate", params={"brand_id": 4242})

    assert response.status_code == 404
