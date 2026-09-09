"""The dead-letter queue (hard rule #7), and the way back out of it.

`failed_jobs` is deliberately global rather than brand-scoped, unlike every
list endpoint D17 covers. It has no `brand_id`, and giving it one would mean
resolving a payload back to a brand for a row that exists precisely because its
payload could not be resolved. It is operational data, and it sits alongside
`/queue/stats`, which is global for the same reason — the Failed Jobs panel
says "all brands" on its face so the scope is never in question.
"""

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.db import SessionDep
from app.models import FailedJob
from app.routers.ingest import dead_letter_rows
from app.routers.params import LimitQuery, OffsetQuery
from app.schemas.agent_run import FailedJobRead
from app.services.queue import enqueue_asset, enqueue_comments

router = APIRouter(prefix="/failed_jobs", tags=["failed_jobs"])


# Job types that can be put back on the queue. A row written by ingest is not
# one of them: it never became a job, and its payload is stored and immutable,
# so re-running it produces the identical failure forever. The remedy for a
# malformed input row is to fix the source data and re-ingest, which happens
# nowhere near this panel.
RETRYABLE = frozenset({"process_comment", "process_asset"})


class RetryResult(BaseModel):
    requeued: bool
    detail: str


class DiscardResult(BaseModel):
    discarded: bool
    detail: str


@router.get("", response_model=list[FailedJobRead])
async def list_failed_jobs(
    session: SessionDep, limit: LimitQuery = 50, offset: OffsetQuery = 0
) -> Any:
    """Newest first: the failure you are debugging is the one that just happened."""
    rows = (
        (
            await session.execute(
                select(FailedJob).order_by(FailedJob.id.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return [
        FailedJobRead.model_validate(
            {
                **{c.name: getattr(row, c.name) for c in FailedJob.__table__.columns},
                "retryable": row.job_type in RETRYABLE,
            }
        )
        for row in rows
    ]


@router.post("/{job_id}/retry", response_model=RetryResult)
async def retry_failed_job(job_id: int, session: SessionDep) -> Any:
    """Put one dead-lettered job back into the system.

    Retry means "run the same operation again", and what that operation IS
    differs by job type — so this dispatches rather than blindly re-enqueueing.
    A row written by ingest never became a queue job; re-enqueueing it would
    push a comment id that does not exist and land straight back here.

    On success the row is deleted. The DLQ holds work that still needs
    attention, and history is not lost: a retry that fails again writes a fresh
    row with its own error, which is more useful than a stale one with a flag.
    """
    job = await session.get(FailedJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Failed job not found")

    # Every job key carries a fresh attempt suffix. arq keeps a finished job's
    # key for an hour, so without this a retry inside that hour is silently
    # refused and the button appears to do nothing (D9).
    attempt = f"-retry-{int(time.time())}"

    match job.job_type:
        case "process_comment":
            comment_id = int(job.payload_json["comment_id"])
            queued = await enqueue_comments([comment_id], attempt=attempt)
            detail = f"Re-queued comment {comment_id}"
        case "process_asset":
            asset_id = int(job.payload_json["asset_id"])
            queued = int(await enqueue_asset(asset_id, attempt=attempt))
            detail = f"Re-queued asset {asset_id}"
        case _:
            # Including "ingest_comment". Retrying it re-runs a validation that
            # cannot pass — an earlier version did exactly that, returned the
            # same error every time, and incremented `attempts` on each press.
            # A counter that only records how many times someone pressed a
            # button that cannot work is not information.
            raise HTTPException(
                status_code=422,
                detail=(
                    f"{job.job_type} cannot be re-queued. Fix the row in the source "
                    f"data and ingest it again, then discard this entry."
                ),
            )

    if not queued:
        # arq refused the key, which means the job is already queued. Leaving the
        # DLQ row in place would be wrong (it is no longer dead) but so would
        # claiming we queued it.
        await session.delete(job)
        await session.commit()
        return RetryResult(requeued=False, detail="Already queued; cleared from the DLQ")

    await session.delete(job)
    await session.commit()
    return RetryResult(requeued=True, detail=detail)


@router.post("/{job_id}/discard", response_model=DiscardResult)
async def discard_failed_job(job_id: int, session: SessionDep) -> Any:
    """Acknowledge a failure and clear it from the queue.

    The DLQ is a list of work that still needs attention. For a malformed input
    row the attention it needs is a person reading the reason and fixing the
    source — there is nothing here to re-run. Discard is how that row leaves,
    once someone has actually looked at it.

    Deliberately not restricted to unretryable types: an operator who has
    decided a dead comment job is not worth chasing should be able to clear it
    without inventing a reason to press Retry first.
    """
    job = await session.get(FailedJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Failed job not found")

    job_type = job.job_type
    await session.delete(job)
    await session.commit()
    return DiscardResult(discarded=True, detail=f"Cleared the {job_type} entry")


__all__ = ["RETRYABLE", "dead_letter_rows", "router"]
