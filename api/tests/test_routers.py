"""The HTTP seam: what a client can actually observe.

These read as a specification of the API. They deliberately go through the
routers rather than the session, so they survive a model refactor.
"""

from typing import Any

from httpx import AsyncClient

from tests.factories import BRAND_RULES

POSTED_AT = "2026-09-09T12:00:00+00:00"


def _brand_body(name: str = "Ridgeline Roasters") -> dict[str, Any]:
    return {
        "name": name,
        "voice_guidelines": "Warm, plain-spoken.",
        "brand_rules_json": BRAND_RULES,
    }


async def _create_brand(client: AsyncClient, name: str = "Ridgeline Roasters") -> int:
    response = await client.post("/brands", json=_brand_body(name))
    assert response.status_code == 201
    return int(response.json()["id"])


async def _create_account(client: AsyncClient, brand_id: int, handle: str = "@r") -> int:
    response = await client.post(
        "/platform_accounts",
        json={"brand_id": brand_id, "platform": "instagram", "handle": handle},
    )
    assert response.status_code == 201
    return int(response.json()["id"])


async def test_create_brand_returns_201_and_persists(client: AsyncClient) -> None:
    """Proves the route commits — the session dependency deliberately does not."""
    created = await client.post("/brands", json=_brand_body())

    assert created.status_code == 201
    brand_id = created.json()["id"]
    assert brand_id

    fetched = await client.get(f"/brands/{brand_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Ridgeline Roasters"
    assert fetched.json()["brand_rules_json"]["max_hashtags"] == 5


async def test_list_brands_is_empty_not_an_error(client: AsyncClient) -> None:
    """The UI brief requires an empty state for every list; it is a 200 with []."""
    response = await client.get("/brands")

    assert response.status_code == 200
    assert response.json() == []


async def test_get_brand_returns_404_for_a_missing_id(client: AsyncClient) -> None:
    """A None must not leak into response_model and surface as a 500."""
    response = await client.get("/brands/999999")

    assert response.status_code == 404


async def test_create_brand_rejects_malformed_rules_with_422(client: AsyncClient) -> None:
    """D16's shape is rejected before it can reach JSONB as a shapeless blob."""
    response = await client.post(
        "/brands", json=_brand_body() | {"brand_rules_json": {"nonsense": True}}
    )

    assert response.status_code == 422


async def test_listing_accounts_without_brand_id_is_422(client: AsyncClient) -> None:
    """D17: required, not optional. The alternative failure mode is an unscoped
    query quietly returning another brand's rows."""
    response = await client.get("/platform_accounts")

    assert response.status_code == 422


async def test_accounts_are_scoped_to_the_requested_brand(client: AsyncClient) -> None:
    """Cross-brand leakage would be the demo's worst moment, so it is named."""
    first = await _create_brand(client, "Ridgeline Roasters")
    second = await _create_brand(client, "Fell & Fern")
    await _create_account(client, first, "@ridgeline")
    await _create_account(client, second, "@fellandfern")

    response = await client.get("/platform_accounts", params={"brand_id": first})

    assert response.status_code == 200
    handles = [row["handle"] for row in response.json()]
    assert handles == ["@ridgeline"]


async def test_create_account_returns_404_for_an_unknown_brand(client: AsyncClient) -> None:
    """A bad foreign key is a clean 404, not an unhandled IntegrityError 500."""
    response = await client.post(
        "/platform_accounts",
        json={"brand_id": 999999, "platform": "x", "handle": "@nope"},
    )

    assert response.status_code == 404


async def test_listing_posts_without_brand_id_is_422(client: AsyncClient) -> None:
    response = await client.get("/posts")

    assert response.status_code == 422


async def test_posts_scope_through_the_account_to_the_brand(client: AsyncClient) -> None:
    """The two-hop join is the evidence backing the decision not to denormalize
    brand_id onto posts."""
    first = await _create_brand(client, "Ridgeline Roasters")
    second = await _create_brand(client, "Fell & Fern")
    first_account = await _create_account(client, first, "@ridgeline")
    second_account = await _create_account(client, second, "@fellandfern")

    for account_id, external_id in ((first_account, "p-a"), (second_account, "p-b")):
        created = await client.post(
            "/posts",
            json={
                "account_id": account_id,
                "external_id": external_id,
                "text": "hello",
                "posted_at": POSTED_AT,
                "metrics_json": {},
            },
        )
        assert created.status_code == 201

    response = await client.get("/posts", params={"brand_id": second})

    assert [row["external_id"] for row in response.json()] == ["p-b"]


async def test_posts_paginate_deterministically(client: AsyncClient) -> None:
    """A partial ORDER BY would make page 2 overlap page 1 non-reproducibly."""
    brand_id = await _create_brand(client)
    account_id = await _create_account(client, brand_id)
    for index in range(5):
        await client.post(
            "/posts",
            json={
                "account_id": account_id,
                "external_id": f"p-{index}",
                "text": "hello",
                "posted_at": POSTED_AT,
                "metrics_json": {},
            },
        )

    params = {"brand_id": brand_id, "limit": 2, "offset": 2}
    first_call = await client.get("/posts", params=params)
    second_call = await client.get("/posts", params=params)

    assert [row["external_id"] for row in first_call.json()] == ["p-2", "p-3"]
    assert first_call.json() == second_call.json()


async def test_create_post_round_trips_nested_metrics(client: AsyncClient) -> None:
    """JSONB plus dict[str, Any] needs no custom serializer."""
    brand_id = await _create_brand(client)
    account_id = await _create_account(client, brand_id)
    metrics = {"likes": 120, "by_day": [{"d": "2026-09-01", "n": 4}], "nested": {"a": {"b": 1}}}

    created = await client.post(
        "/posts",
        json={
            "account_id": account_id,
            "external_id": "p-1",
            "text": "hello",
            "posted_at": POSTED_AT,
            "metrics_json": metrics,
        },
    )

    assert created.status_code == 201
    assert created.json()["metrics_json"] == metrics


async def test_get_post_returns_404_for_a_missing_id(client: AsyncClient) -> None:
    response = await client.get("/posts/999999")

    assert response.status_code == 404


async def test_a_naive_posted_at_is_rejected(client: AsyncClient) -> None:
    """AwareDatetime at the boundary means the browser always gets an offset."""
    brand_id = await _create_brand(client)
    account_id = await _create_account(client, brand_id)

    response = await client.post(
        "/posts",
        json={
            "account_id": account_id,
            "external_id": "p-1",
            "text": "hello",
            "posted_at": "2026-09-09T12:00:00",
            "metrics_json": {},
        },
    )

    assert response.status_code == 422
