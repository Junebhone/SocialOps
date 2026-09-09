"""The dead-letter queue (hard rule #7) and the way back out of it.

The first test here is the one that matters: it is the bug that would have made
step 9's unattended two-hour run finish in the first second.
"""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Comment, FailedJob
from tests.conftest import FakeQueue
from tests.factories import BRAND_RULES

POSTED_AT = "2026-09-09T12:00:00+00:00"


async def _brand_and_post(client: AsyncClient) -> None:
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
    accounts = (await client.get("/platform_accounts", params={"brand_id": brand_id})).json()
    await client.post(
        "/posts",
        json={"account_id": accounts[0]["id"], "external_id": "post-1", "text": "hi",
              "posted_at": POSTED_AT, "metrics_json": {}},
    )


def _row(external_id: str = "c-1", **overrides: Any) -> dict[str, Any]:
    return {
        "external_id": external_id,
        "post_external_id": "post-1",
        "account_handle": "@ridgeline",
        "author": "@rae",
        "text": "Does this come in decaf?",
        "created_at": POSTED_AT,
        **overrides,
    }


# --- one bad row must not reject the batch ---------------------------------


async def test_one_malformed_row_does_not_reject_the_others(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The bug this exists for.

    data/viral_post_dump.json carries exactly one row with
    `created_at: "not-a-timestamp"`, and the generator that made it says the
    other 1,999 must still process. They did not: validation ran inside a single
    try, so one bad row returned 422 for the whole payload. `make replay-full`
    inserted nothing, enqueued nothing, and dead-lettered nothing — step 9's
    unattended run would have been over in a second with an empty database.
    """
    await _brand_and_post(client)

    body = (
        await client.post(
            "/ingest/comments",
            json=[_row("good-1"), _row("bad-1", created_at="not-a-timestamp"), _row("good-2")],
        )
    ).json()

    assert body["inserted"] == 2
    assert body["rejected"] == 1
    assert body["enqueued"] == 2


async def test_a_rejected_row_lands_in_the_dlq_with_its_payload(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Never swallow errors (hard rule #7). The payload is what makes the row
    actionable — someone reads the bad field off the panel and fixes the source.
    """
    await _brand_and_post(client)

    await client.post(
        "/ingest/comments", json=[_row("bad-1", created_at="not-a-timestamp")]
    )

    job = (await session.execute(select(FailedJob))).scalar_one()
    assert job.job_type == "ingest_comment"
    assert job.payload_json["external_id"] == "bad-1"
    assert "created_at" in job.error
    # It failed at the boundary, before arq saw it. A date that is not a date is
    # a permanent failure, so the three retries in hard rule #7 have nothing to do.
    assert job.attempts == 1


async def test_the_dlq_count_and_the_ingest_count_agree(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _brand_and_post(client)

    body = (
        await client.post(
            "/ingest/comments",
            json=[
                _row("bad-1", created_at="nope"),
                # Empty external_id: min_length=1 on the field rejects it.
                _row("", text="also bad"),
                _row("good-1"),
            ],
        )
    ).json()

    jobs = (await session.execute(select(FailedJob))).scalars().all()
    assert body["rejected"] == len(jobs) == 2


async def test_a_structurally_wrong_body_is_still_a_400_class_error(
    client: AsyncClient,
) -> None:
    """Per-row tolerance is not blanket tolerance. A payload that is not a list
    of objects is a bad request, not 2,000 dead letters."""
    assert (await client.post("/ingest/comments", json={"not": "a list"})).status_code == 422
    assert (await client.post("/ingest/comments", json=["just a string"])).status_code == 422


async def test_a_good_row_after_a_bad_one_still_reaches_the_queue(
    client: AsyncClient, session: AsyncSession, queue: FakeQueue
) -> None:
    """Ordering matters: the bad row came first in the real dump too."""
    await _brand_and_post(client)

    await client.post(
        "/ingest/comments", json=[_row("bad-1", created_at="nope"), _row("good-1")]
    )

    comments = (await session.execute(select(Comment))).scalars().all()
    assert [c.external_id for c in comments] == ["good-1"]
    assert len(queue.jobs) == 1


# --- listing and retrying --------------------------------------------------


async def test_listing_failed_jobs_is_not_brand_scoped(client: AsyncClient) -> None:
    """The one list endpoint D17 does not cover. failed_jobs has no brand_id —
    a row lands here precisely because its payload could not be resolved — so it
    sits with /queue/stats as operational data, and the panel says 'all brands'.
    """
    assert (await client.get("/failed_jobs")).status_code == 200


async def test_retrying_a_comment_job_requeues_it_and_clears_the_row(
    client: AsyncClient, session: AsyncSession, queue: FakeQueue
) -> None:
    session.add(
        FailedJob(
            job_type="process_comment",
            payload_json={"comment_id": 41},
            error="LookupError: boom",
            attempts=3,
        )
    )
    await session.commit()
    job = (await session.execute(select(FailedJob))).scalar_one()

    body = (await client.post(f"/failed_jobs/{job.id}/retry")).json()

    assert body["requeued"] is True
    assert [args for _fn, args in queue.jobs.values()] == [(41,)]
    assert (await session.execute(select(FailedJob))).scalars().all() == []


async def test_a_retry_uses_a_fresh_job_key(
    client: AsyncClient, session: AsyncSession, queue: FakeQueue
) -> None:
    """arq keeps a finished job's key for an hour (D9). Without a fresh attempt
    suffix the retry inside that hour is silently refused and the button looks
    like it did nothing."""
    session.add(
        FailedJob(job_type="process_comment", payload_json={"comment_id": 41},
                  error="boom", attempts=3)
    )
    await session.commit()
    job = (await session.execute(select(FailedJob))).scalar_one()

    await client.post(f"/failed_jobs/{job.id}/retry")

    assert list(queue.jobs) != ["comment-41"]
    assert list(queue.jobs)[0].startswith("comment-41-retry-")


async def test_retrying_an_asset_job(
    client: AsyncClient, session: AsyncSession, queue: FakeQueue
) -> None:
    session.add(
        FailedJob(job_type="process_asset", payload_json={"asset_id": 7},
                  error="ImageError: nope", attempts=3)
    )
    await session.commit()
    job = (await session.execute(select(FailedJob))).scalar_one()

    body = (await client.post(f"/failed_jobs/{job.id}/retry")).json()

    assert body["requeued"] is True
    assert [fn for fn, _args in queue.jobs.values()] == ["process_asset"]


async def test_retrying_a_still_malformed_row_says_so_and_keeps_the_row(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Retry re-runs the same operation and reports the same reason, rather than
    pretending. Nothing about the row changed, so it fails again — and the row
    stays in the DLQ with its attempt count bumped."""
    await _brand_and_post(client)
    await client.post("/ingest/comments", json=[_row("bad-1", created_at="nope")])
    job = (await session.execute(select(FailedJob))).scalar_one()

    response = await client.post(f"/failed_jobs/{job.id}/retry")

    assert response.status_code == 422
    assert "Still invalid" in response.json()["detail"]
    await session.refresh(job)
    assert job.attempts == 2


async def test_retrying_an_unknown_job_is_a_404(client: AsyncClient) -> None:
    assert (await client.post("/failed_jobs/4242/retry")).status_code == 404


async def test_an_unretryable_job_type_says_so(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Better a clear 422 than a button that silently does nothing."""
    session.add(
        FailedJob(job_type="something_else", payload_json={}, error="?", attempts=3)
    )
    await session.commit()
    job = (await session.execute(select(FailedJob))).scalar_one()

    response = await client.post(f"/failed_jobs/{job.id}/retry")

    assert response.status_code == 422
    assert "Cannot retry" in response.json()["detail"]


# --- batching must not change the contract ---------------------------------


async def test_a_duplicate_inside_one_payload_is_inserted_once(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The insert is one statement now, not one per row. Within a single
    statement only the first insert is visible to a later row's ON CONFLICT
    check, so an in-batch duplicate would slip past the unique constraint —
    deduplicated before the statement is built instead."""
    await _brand_and_post(client)

    body = (await client.post("/ingest/comments", json=[_row("c-1"), _row("c-1")])).json()

    assert body["inserted"] == 1
    assert body["skipped"] == 1
    assert len((await session.execute(select(Comment))).scalars().all()) == 1


async def test_a_large_payload_still_reports_honest_counts(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Chunked at 1,000 rows because Postgres caps a statement at 65,535 bind
    parameters and each row uses five. The counts must not care."""
    await _brand_and_post(client)
    rows = [_row(f"c-{n}") for n in range(1200)]

    first = (await client.post("/ingest/comments", json=rows)).json()
    second = (await client.post("/ingest/comments", json=rows)).json()

    assert first == {"inserted": 1200, "skipped": 0, "enqueued": 1200, "rejected": 0}
    assert second == {"inserted": 0, "skipped": 1200, "enqueued": 0, "rejected": 0}


async def test_an_unanalysed_asset_can_be_recovered(
    client: AsyncClient, session: AsyncSession, queue: FakeQueue
) -> None:
    """The asset row is committed before its job is enqueued — it has to be, or
    the worker beats its own row to the database. A Redis blip in between left a
    row with no job and no DLQ entry, because no job ever existed, and the card
    read "Analysing the photo…" forever."""
    from tests.factories import a_brand, an_asset

    brand = await a_brand(session)
    asset = await an_asset(session, brand, analysis=None)

    body = (await client.post("/queue/requeue")).json()

    assert body["requeued"] == 1
    assert [fn for fn, _args in queue.jobs.values()] == ["process_asset"]
    assert [args for _fn, args in queue.jobs.values()] == [(asset.id,)]
