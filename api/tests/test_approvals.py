"""Ingest, the Inbox listing, and the approval loop.

These are the endpoints the demo actually drives, so they are tested at the HTTP
seam rather than through the session.
"""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Comment, Outbox, ReplyDraft
from tests.factories import BRAND_RULES, a_post, build_comment

POSTED_AT = "2026-09-09T12:00:00+00:00"


async def _brand_and_account(client: AsyncClient) -> tuple[int, str]:
    created = await client.post(
        "/brands",
        json={"name": "Ridgeline Roasters", "voice_guidelines": "Warm.",
              "brand_rules_json": BRAND_RULES},
    )
    brand_id = created.json()["id"]
    await client.post(
        "/platform_accounts",
        json={"brand_id": brand_id, "platform": "instagram", "handle": "@ridgeline"},
    )
    await client.post(
        "/posts",
        json={"account_id": (await client.get("/platform_accounts",
                                              params={"brand_id": brand_id})).json()[0]["id"],
              "external_id": "post-1", "text": "hi", "posted_at": POSTED_AT, "metrics_json": {}},
    )
    return brand_id, "@ridgeline"


def _row(external_id: str = "c-1") -> dict[str, Any]:
    return {
        "external_id": external_id,
        "post_external_id": "post-1",
        "account_handle": "@ridgeline",
        "author": "@rae",
        "text": "Does this come in decaf?",
        "created_at": POSTED_AT,
    }


async def test_ingest_is_idempotent(client: AsyncClient) -> None:
    """D9: the whole point of replaying a dump twice costing nothing."""
    await _brand_and_account(client)

    first = await client.post("/ingest/comments", json=[_row(), _row("c-2")])
    second = await client.post("/ingest/comments", json=[_row(), _row("c-2")])

    assert first.json()["inserted"] == 2
    assert second.json() == {"inserted": 0, "skipped": 2, "enqueued": 0, "rejected": 0}


async def test_ingest_skips_a_comment_whose_post_is_unknown(client: AsyncClient) -> None:
    """A data problem, not a transient one — retrying would not help, so it is
    counted rather than raised."""
    await _brand_and_account(client)

    result = await client.post(
        "/ingest/comments", json=[{**_row(), "post_external_id": "does-not-exist"}]
    )

    assert result.json() == {"inserted": 0, "skipped": 1, "enqueued": 0, "rejected": 0}


async def test_ingest_rejects_a_row_with_no_timestamp(client: AsyncClient) -> None:
    """comments.created_at has no server default, so a missing value has to fail
    at the boundary rather than at insert.

    It fails as ONE ROW, not as the whole request. This test used to assert a
    422 for the batch, which is what made `make replay-full` insert nothing at
    all when it hit the dump's single deliberately-malformed row. The row is now
    dead-lettered and the rest of the payload proceeds — see tests/test_dlq.py.
    """
    await _brand_and_account(client)
    payload = {k: v for k, v in _row().items() if k != "created_at"}

    body = (await client.post("/ingest/comments", json=[payload, _row("c-2")])).json()

    assert body == {"inserted": 1, "skipped": 0, "enqueued": 1, "rejected": 1}


async def test_listing_comments_requires_a_brand(client: AsyncClient) -> None:
    assert (await client.get("/comments")).status_code == 422


async def test_comments_carry_their_draft(client: AsyncClient, session: AsyncSession) -> None:
    """One Inbox row = comment + triage + draft, joined server-side."""
    post = await a_post(session)
    comment = build_comment(post, category="question", sentiment=1, needs_reply=True,
                            urgency="low", status="drafted")
    session.add(comment)
    await session.commit()
    session.add(ReplyDraft(comment_id=comment.id, text="We do ship there."))
    await session.commit()

    account = (await session.execute(select(Comment))).scalar_one()
    assert account is not None

    from app.models import Brand

    brand = (await session.execute(select(Brand))).scalar_one()
    rows = (await client.get("/comments", params={"brand_id": brand.id})).json()

    assert len(rows) == 1
    assert rows[0]["draft"]["text"] == "We do ship there."
    assert rows[0]["category"] == "question"


async def test_approving_writes_an_outbox_row(
    client: AsyncClient, session: AsyncSession
) -> None:
    """D3: approval does not send anything directly. It queues the publish, and
    that is what makes the loop close on stage."""
    post = await a_post(session)
    comment = build_comment(post)
    session.add(comment)
    await session.commit()
    draft = ReplyDraft(comment_id=comment.id, text="Yes, we do.")
    session.add(draft)
    await session.commit()

    response = await client.patch(
        f"/reply_drafts/{draft.id}", json={"status": "approved", "approved_by": "june"}
    )

    assert response.status_code == 200
    assert response.json()["approved_by"] == "june"
    assert response.json()["approved_at"] is not None

    outbox = (await session.execute(select(Outbox))).scalars().all()
    assert len(outbox) == 1
    assert outbox[0].payload_json["text"] == "Yes, we do."


async def test_an_edit_is_recorded_as_final_text(
    client: AsyncClient, session: AsyncSession
) -> None:
    """There is no 'edited' status (D3) — a non-null final_text IS the record,
    and it is what gets published."""
    post = await a_post(session)
    comment = build_comment(post)
    session.add(comment)
    await session.commit()
    draft = ReplyDraft(comment_id=comment.id, text="Agent wording.")
    session.add(draft)
    await session.commit()

    await client.patch(
        f"/reply_drafts/{draft.id}",
        json={"status": "approved", "final_text": "Human wording.", "approved_by": "june"},
    )

    outbox = (await session.execute(select(Outbox))).scalar_one()
    assert outbox.payload_json["text"] == "Human wording."


async def test_rejecting_queues_nothing(client: AsyncClient, session: AsyncSession) -> None:
    post = await a_post(session)
    comment = build_comment(post)
    session.add(comment)
    await session.commit()
    draft = ReplyDraft(comment_id=comment.id, text="No.")
    session.add(draft)
    await session.commit()

    await client.patch(f"/reply_drafts/{draft.id}", json={"status": "rejected"})

    assert (await session.execute(select(Outbox))).scalars().all() == []


async def test_bulk_approval_queues_every_draft(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A stated demo criterion. Approving 40 rows one at a time on stage is a
    bad look, so the batch path is its own endpoint and its own test."""
    post = await a_post(session)
    ids = []
    for index in range(4):
        comment = build_comment(post, external_id=f"c-{index}")
        session.add(comment)
        await session.commit()
        draft = ReplyDraft(comment_id=comment.id, text=f"Draft {index}")
        session.add(draft)
        await session.commit()
        ids.append(draft.id)

    response = await client.patch(
        "/reply_drafts/bulk", json={"ids": ids, "status": "approved", "approved_by": "june"}
    )

    assert response.status_code == 200
    assert [row["status"] for row in response.json()] == ["approved"] * 4
    assert len((await session.execute(select(Outbox))).scalars().all()) == 4


async def test_bulk_approval_rejects_an_unknown_id(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Partial success would leave the operator unsure what was approved."""
    response = await client.patch(
        "/reply_drafts/bulk", json={"ids": [999999], "status": "approved"}
    )

    assert response.status_code == 404
    assert (await session.execute(select(Outbox))).scalars().all() == []


async def test_queue_stats_reports_the_dlq(client: AsyncClient, session: AsyncSession) -> None:
    from app.models import FailedJob

    session.add(
        FailedJob(job_type="process_comment", payload_json={"comment_id": 1},
                  error="boom", attempts=3)
    )
    await session.commit()

    stats = (await client.get("/queue/stats")).json()

    assert stats["failed"] == 1
    assert "queued" in stats and "running" in stats
