"""GET /analytics: the numbers the Analytics page draws (ADR-0005)."""

from datetime import timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Brand, Comment, Outbox, Post, ReplyDraft
from tests.factories import NOW, a_brand, a_post, an_account, build_comment

RANGE = {"from": "2026-09-01", "to": "2026-09-30"}


async def _post_for(session: AsyncSession, brand: Brand, handle: str = "@ridge") -> Post:
    return await a_post(session, await an_account(session, brand, handle), f"p-{handle}")


async def _comments(session: AsyncSession, post: Post, *rows: dict[str, Any]) -> list[Comment]:
    comments = [
        build_comment(post, external_id=f"{post.external_id}-c{i}", **overrides)
        for i, overrides in enumerate(rows)
    ]
    session.add_all(comments)
    await session.commit()
    return comments


async def _get(client: AsyncClient, brand_id: int, **params: str) -> dict[str, Any]:
    response = await client.get("/analytics", params={"brand_id": brand_id, **RANGE, **params})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


# --- request validation ---------------------------------------------------


async def test_analytics_requires_a_brand(client: AsyncClient) -> None:
    assert (await client.get("/analytics")).status_code == 422


async def test_unknown_brand_is_404(client: AsyncClient) -> None:
    assert (await client.get("/analytics", params={"brand_id": 999})).status_code == 404


async def test_from_after_to_is_rejected(client: AsyncClient, session: AsyncSession) -> None:
    brand = await a_brand(session)
    params: dict[str, str | int] = {"brand_id": brand.id, "from": "2026-09-30", "to": "2026-09-01"}
    assert (await client.get("/analytics", params=params)).status_code == 422


async def test_no_data_is_empty_not_an_error(client: AsyncClient, session: AsyncSession) -> None:
    brand = await a_brand(session)

    body = await _get(client, brand.id)

    assert body["sentiment"] == []
    assert body["categories"] == []
    assert body["response_times"]["published"] == 0
    assert body["response_times"]["p50_seconds"] is None


# --- sentiment and categories ---------------------------------------------


async def test_sentiment_is_a_daily_average_of_triaged_comments(
    client: AsyncClient, session: AsyncSession
) -> None:
    brand = await a_brand(session)
    post = await _post_for(session, brand)
    await _comments(
        session,
        post,
        {"sentiment": 2, "category": "praise"},
        {"sentiment": -1, "category": "complaint"},
        {},  # not triaged yet: no sentiment, no category, must not count
    )

    body = await _get(client, brand.id)

    assert body["sentiment"] == [{"day": "2026-09-09", "avg_sentiment": 0.5, "comments": 2}]
    assert {(c["category"], c["comments"]) for c in body["categories"]} == {
        ("praise", 1),
        ("complaint", 1),
    }


async def test_analytics_are_scoped_to_their_brand(
    client: AsyncClient, session: AsyncSession
) -> None:
    ridgeline = await a_brand(session, name="Ridgeline Roasters")
    fieldnote = await a_brand(session, name="Fieldnote Skin")
    await _comments(
        session,
        await _post_for(session, ridgeline, "@ridge"),
        {"sentiment": 1, "category": "question"},
    )
    await _comments(
        session,
        await _post_for(session, fieldnote, "@field"),
        {"sentiment": -2, "category": "complaint"},
    )

    body = await _get(client, ridgeline.id)

    assert [c["category"] for c in body["categories"]] == ["question"]


async def test_days_are_bucketed_in_the_brands_time_zone(
    client: AsyncClient, session: AsyncSession
) -> None:
    brand = await a_brand(session)
    brand.timezone = "America/Chicago"
    await session.commit()
    post = await _post_for(session, brand)
    # 03:00 UTC on the 9th is still the evening of the 8th in Chicago.
    late_evening = NOW.replace(hour=3)
    await _comments(
        session, post, {"sentiment": 1, "category": "praise", "created_at": late_evening}
    )

    body = await _get(client, brand.id)

    assert body["timezone"] == "America/Chicago"
    assert body["sentiment"][0]["day"] == "2026-09-08"


async def test_comments_outside_the_range_are_excluded(
    client: AsyncClient, session: AsyncSession
) -> None:
    brand = await a_brand(session)
    await _comments(
        session, await _post_for(session, brand), {"sentiment": 1, "category": "praise"}
    )

    body = await _get(client, brand.id, **{"from": "2026-10-01", "to": "2026-10-31"})

    assert body["sentiment"] == []


# --- time to first response -----------------------------------------------


async def test_response_time_counts_published_replies_only(
    client: AsyncClient, session: AsyncSession
) -> None:
    brand = await a_brand(session)
    published, pending = await _comments(
        session,
        await _post_for(session, brand),
        {"sentiment": 1, "category": "question"},
        {"sentiment": 0, "category": "question"},
    )
    for comment, sent_at in ((published, NOW + timedelta(minutes=10)), (pending, None)):
        draft = ReplyDraft(comment_id=comment.id, text="Thanks!", status="approved")
        session.add(draft)
        await session.flush()
        session.add(Outbox(reply_draft_id=draft.id, payload_json={}, sent_at=sent_at))
    await session.commit()

    rt = (await _get(client, brand.id))["response_times"]

    assert rt["published"] == 1
    assert rt["p50_seconds"] == 600
    assert {b["label"]: b["comments"] for b in rt["histogram"]}["5-15 min"] == 1
