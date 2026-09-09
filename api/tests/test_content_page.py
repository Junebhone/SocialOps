"""What the Content page reads and writes.

Step 7's endpoints: the asset list that becomes one card per photo, the
cross-asset draft query, and the approve/edit/reject patch.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import ANALYSIS, a_brand, an_asset, content_drafts

# --- GET /assets -----------------------------------------------------------


async def test_listing_assets_requires_a_brand(client: AsyncClient) -> None:
    """D17: brand_id is required on every list endpoint, not optional."""
    assert (await client.get("/assets")).status_code == 422


async def test_an_asset_carries_its_three_drafts(
    client: AsyncClient, session: AsyncSession
) -> None:
    """One card = image + analysis + three captions, joined server-side. The
    browser making a request per asset would be an N+1 on every page load."""
    brand = await a_brand(session)
    asset = await an_asset(session, brand, analysis=ANALYSIS)
    await content_drafts(session, asset)

    rows = (await client.get("/assets", params={"brand_id": brand.id})).json()

    assert len(rows) == 1
    assert rows[0]["analysis_json"]["brand_check"]["passes"] is True
    assert sorted(d["platform"] for d in rows[0]["drafts"]) == ["instagram", "linkedin", "x"]


async def test_an_asset_still_being_analysed_is_listed(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The join has to be OUTER. An asset with no drafts yet is the 'analysing'
    card — dropping it would make an upload vanish for 30 seconds and reappear.
    """
    brand = await a_brand(session)
    await an_asset(session, brand, analysis=None)

    rows = (await client.get("/assets", params={"brand_id": brand.id})).json()

    assert len(rows) == 1
    assert rows[0]["analysis_json"] is None
    assert rows[0]["drafts"] == []


async def test_assets_are_scoped_to_their_brand(
    client: AsyncClient, session: AsyncSession
) -> None:
    """An unscoped query returning another brand's photos would be the demo's
    worst moment (D17)."""
    ridgeline = await a_brand(session, name="Ridgeline Roasters")
    fieldnote = await a_brand(session, name="Fieldnote")
    await an_asset(session, ridgeline, filename="beans.png", analysis=ANALYSIS)
    await an_asset(session, fieldnote, filename="serum.png", analysis=ANALYSIS)

    rows = (await client.get("/assets", params={"brand_id": ridgeline.id})).json()

    assert [row["filename"] for row in rows] == ["beans.png"]


async def test_paging_does_not_cut_an_asset_in_half(
    client: AsyncClient, session: AsyncSession
) -> None:
    """LIMIT on the joined rows would slice through one asset's drafts and show
    a card with two captions. Paging happens after grouping."""
    brand = await a_brand(session)
    for index in range(3):
        asset = await an_asset(session, brand, filename=f"a{index}.png", analysis=ANALYSIS)
        await content_drafts(session, asset)

    rows = (await client.get("/assets", params={"brand_id": brand.id, "limit": 2})).json()

    assert len(rows) == 2
    assert all(len(row["drafts"]) == 3 for row in rows)


async def test_newest_asset_first(client: AsyncClient, session: AsyncSession) -> None:
    """The photo you just dropped is the one you want to look at."""
    brand = await a_brand(session)
    await an_asset(session, brand, filename="first.png", analysis=ANALYSIS)
    await an_asset(session, brand, filename="second.png", analysis=ANALYSIS)

    rows = (await client.get("/assets", params={"brand_id": brand.id})).json()

    assert [row["filename"] for row in rows] == ["second.png", "first.png"]


# --- GET /content_drafts ---------------------------------------------------


async def test_listing_content_drafts_requires_a_brand(client: AsyncClient) -> None:
    assert (await client.get("/content_drafts")).status_code == 422


async def test_content_drafts_can_be_filtered_across_assets(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The question a per-asset shape cannot answer: every LinkedIn caption
    still waiting on review, across every photo."""
    brand = await a_brand(session)
    for index in range(2):
        asset = await an_asset(session, brand, filename=f"a{index}.png", analysis=ANALYSIS)
        await content_drafts(session, asset)

    rows = (
        await client.get(
            "/content_drafts",
            params={"brand_id": brand.id, "platform": "linkedin", "status": "pending"},
        )
    ).json()

    assert len(rows) == 2
    assert {row["platform"] for row in rows} == {"linkedin"}


async def test_content_drafts_are_scoped_through_the_asset(
    client: AsyncClient, session: AsyncSession
) -> None:
    """content_drafts has no brand_id of its own — the scope is asset -> brand,
    and getting that join wrong leaks copy between clients."""
    ridgeline = await a_brand(session, name="Ridgeline Roasters")
    fieldnote = await a_brand(session, name="Fieldnote")
    await content_drafts(session, await an_asset(session, ridgeline, analysis=ANALYSIS))
    await content_drafts(session, await an_asset(session, fieldnote, analysis=ANALYSIS))

    rows = (await client.get("/content_drafts", params={"brand_id": ridgeline.id})).json()

    assert len(rows) == 3


# --- PATCH /content_drafts/{id} --------------------------------------------


async def test_approving_a_caption(client: AsyncClient, session: AsyncSession) -> None:
    drafts = await content_drafts(session, await an_asset(session, analysis=ANALYSIS))

    body = (
        await client.patch(f"/content_drafts/{drafts[0].id}", json={"status": "approved"})
    ).json()

    assert body["status"] == "approved"
    assert body["final_text"] is None


async def test_editing_records_final_text_and_keeps_the_original(
    client: AsyncClient, session: AsyncSession
) -> None:
    """As with reply drafts (D3): a non-null final_text is the record that a
    human changed it. The agent's own words stay in `text` so the Agents page
    can still show what the model wrote."""
    drafts = await content_drafts(session, await an_asset(session, analysis=ANALYSIS))
    original = drafts[0].text

    body = (
        await client.patch(
            f"/content_drafts/{drafts[0].id}",
            json={"status": "approved", "final_text": "Roasted Tuesday. Out now."},
        )
    ).json()

    assert body["final_text"] == "Roasted Tuesday. Out now."
    assert body["text"] == original


async def test_rejecting_a_caption(client: AsyncClient, session: AsyncSession) -> None:
    drafts = await content_drafts(session, await an_asset(session, analysis=ANALYSIS))

    body = (
        await client.patch(f"/content_drafts/{drafts[0].id}", json={"status": "rejected"})
    ).json()

    assert body["status"] == "rejected"


async def test_a_content_draft_cannot_be_published(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The outbox drains reply drafts only. A caption is copy someone takes away
    and posts themselves, so `approved` is terminal and `published` is not a
    value this table accepts."""
    drafts = await content_drafts(session, await an_asset(session, analysis=ANALYSIS))

    response = await client.patch(
        f"/content_drafts/{drafts[0].id}", json={"status": "published"}
    )

    assert response.status_code == 422


async def test_patching_an_unknown_draft_is_a_404(client: AsyncClient) -> None:
    response = await client.patch("/content_drafts/4242", json={"status": "approved"})

    assert response.status_code == 404
