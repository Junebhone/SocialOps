"""What the Ideas page reads and writes, and the "Generate Ideas" button."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import FakeQueue
from tests.factories import a_brand, a_content_idea

# --- GET /content_ideas -----------------------------------------------------


async def test_listing_ideas_requires_a_brand(client: AsyncClient) -> None:
    """D17: brand_id is required on every list endpoint, not optional."""
    assert (await client.get("/content_ideas")).status_code == 422


async def test_ideas_are_scoped_to_their_brand(client: AsyncClient, session: AsyncSession) -> None:
    ridgeline = await a_brand(session, name="Ridgeline Roasters")
    fieldnote = await a_brand(session, name="Fieldnote")
    await a_content_idea(session, ridgeline, text="Roastery behind-the-scenes.")
    await a_content_idea(session, fieldnote, text="Ingredient deep-dive.")

    rows = (await client.get("/content_ideas", params={"brand_id": ridgeline.id})).json()

    assert [row["text"] for row in rows] == ["Roastery behind-the-scenes."]


async def test_newest_idea_first(client: AsyncClient, session: AsyncSession) -> None:
    brand = await a_brand(session)
    await a_content_idea(session, brand, text="First idea.")
    await a_content_idea(session, brand, text="Second idea.")

    rows = (await client.get("/content_ideas", params={"brand_id": brand.id})).json()

    assert [row["text"] for row in rows] == ["Second idea.", "First idea."]


async def test_ideas_can_be_filtered_by_status(client: AsyncClient, session: AsyncSession) -> None:
    brand = await a_brand(session)
    await a_content_idea(session, brand, text="Proposed one.", status="proposed")
    await a_content_idea(session, brand, text="Approved one.", status="approved")

    rows = (
        await client.get("/content_ideas", params={"brand_id": brand.id, "status": "proposed"})
    ).json()

    assert [row["text"] for row in rows] == ["Proposed one."]


# --- PATCH /content_ideas/{id} ----------------------------------------------


async def test_approving_an_idea(client: AsyncClient, session: AsyncSession) -> None:
    idea = await a_content_idea(session)

    body = (await client.patch(f"/content_ideas/{idea.id}", json={"status": "approved"})).json()

    assert body["status"] == "approved"


async def test_rejecting_an_idea(client: AsyncClient, session: AsyncSession) -> None:
    idea = await a_content_idea(session)

    body = (await client.patch(f"/content_ideas/{idea.id}", json={"status": "rejected"})).json()

    assert body["status"] == "rejected"


async def test_patching_an_unknown_idea_is_a_404(client: AsyncClient) -> None:
    response = await client.patch("/content_ideas/4242", json={"status": "approved"})

    assert response.status_code == 404


async def test_patching_an_idea_requires_a_status(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Unlike content_drafts, there is no final_text — an idea is not edited in
    place, only accepted or rejected."""
    idea = await a_content_idea(session)

    response = await client.patch(f"/content_ideas/{idea.id}", json={})

    assert response.status_code == 422


# --- POST /content_ideas/generate -------------------------------------------


async def test_generate_enqueues_one_ideation_job(
    client: AsyncClient, session: AsyncSession, queue: FakeQueue
) -> None:
    brand = await a_brand(session)

    body = (await client.post("/content_ideas/generate", params={"brand_id": brand.id})).json()

    assert body["enqueued"] is True
    assert len(queue.jobs) == 1
    function, args = next(iter(queue.jobs.values()))
    assert function == "process_ideation"
    assert args == (brand.id,)


async def test_generate_twice_enqueues_two_jobs(
    client: AsyncClient, session: AsyncSession, queue: FakeQueue
) -> None:
    """Unlike comments/assets, a second click is a second real request for more
    ideas, not a duplicate of the first — the job key must not collide."""
    brand = await a_brand(session)

    await client.post("/content_ideas/generate", params={"brand_id": brand.id})
    await client.post("/content_ideas/generate", params={"brand_id": brand.id})

    assert len(queue.jobs) == 2


async def test_generate_for_an_unknown_brand_is_a_404(client: AsyncClient) -> None:
    response = await client.post("/content_ideas/generate", params={"brand_id": 4242})

    assert response.status_code == 404
