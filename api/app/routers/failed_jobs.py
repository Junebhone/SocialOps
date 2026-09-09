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
from app.routers.ingest import dead_letter_rows, parse_rows
from app.routers.params import LimitQuery, OffsetQuery
from app.schemas.agent_run import FailedJobRead
from app.services.queue import enqueue_asset, enqueue_comments

router = APIRouter(prefix="/failed_jobs", tags=["failed_jobs"])


class RetryResult(BaseModel):
    requeued: bool
    detail: str


@router.get("", response_model=list[FailedJobRead])
async def list_failed_jobs(
    session: SessionDep, limit: LimitQuery = 50, offset: OffsetQuery = 0
) -> Any:
    """Newest first: the failure you are debugging is the one that just happened."""
    return list(
        (
            await session.execute(
                select(FailedJob).order_by(FailedJob.id.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )


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
        case "ingest_comment":
            return await _retry_ingest(session, job)
        case _:
            raise HTTPException(
                status_code=422, detail=f"Cannot retry job type {job.job_type!r}"
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


async def _retry_ingest(session: SessionDep, job: FailedJob) -> RetryResult:
    """Re-validate the stored row.

    Nothing about the row has changed since it failed, so this normally fails
    again — and that is the honest behaviour. The button re-runs the same
    operation and reports the same reason, rather than pretending. It succeeds
    only if someone actually fixed the payload, which is the case it exists for.
    """
    _parsed, rejected = parse_rows([job.payload_json])
    if rejected:
        job.attempts += 1
        job.error = rejected[0].error
        await session.commit()
        raise HTTPException(status_code=422, detail=f"Still invalid — {rejected[0].error}")

    # It parses now. Re-ingesting is the caller's job: this endpoint has no post
    # lookup and no business duplicating one. Clearing the row is what it can
    # honestly do.
    await session.delete(job)
    await session.commit()
    return RetryResult(
        requeued=False, detail="Row is valid now; re-run the ingest to load it"
    )


__all__ = ["dead_letter_rows", "router"]
