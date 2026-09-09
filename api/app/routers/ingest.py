"""Comment ingestion and queue visibility.

Ingest is idempotent (D9): running `make replay` twice inserts nothing the second
time and enqueues nothing, so a repeated 2,000-comment dump costs zero extra
model calls rather than two wasted hours.
"""

import csv
import io
import time
from collections.abc import Iterator
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request, UploadFile
from pydantic import AwareDatetime, BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.db import SessionDep
from app.models import Asset, Comment, FailedJob, PlatformAccount, Post
from app.services.queue import enqueue_asset, enqueue_comments, queue_depth

router = APIRouter(tags=["ingest"])

log = structlog.get_logger()

# Rows per INSERT. Postgres allows 65,535 bind parameters in one statement and
# each row uses five, so this leaves a wide margin while still turning a
# 2,000-row replay into two round trips instead of two thousand.
CHUNK_ROWS = 1000


def _chunks[T](items: list[T], size: int) -> Iterator[list[T]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


class IncomingComment(BaseModel):
    """One row of a dump. Shaped by what a platform export actually gives you."""

    external_id: str = Field(min_length=1, max_length=128)
    post_external_id: str
    account_handle: str
    author: str
    text: str
    # No default: comments.created_at is the platform's timestamp and the column
    # has no server default, so a missing value must fail here rather than at insert.
    created_at: AwareDatetime


class IngestResult(BaseModel):
    inserted: int
    # Already present, or attached to a post we do not have. Neither is an error.
    skipped: int
    enqueued: int
    # Rows that could not be parsed. Each one is now a `failed_jobs` row, so the
    # count here and the DLQ panel always agree.
    rejected: int = 0


async def _resolve_posts(session: SessionDep) -> dict[tuple[str, str], int]:
    """Map (account_handle, post_external_id) -> post id.

    Resolved in one query rather than per comment: at 2,000 comments the
    round-trips dominate everything else in this endpoint.
    """
    rows = await session.execute(
        select(PlatformAccount.handle, Post.external_id, Post.id).join(
            Post, Post.account_id == PlatformAccount.id
        )
    )
    return {(handle, external_id): post_id for handle, external_id, post_id in rows}


class RejectedRow(BaseModel):
    """A row that could not be parsed, on its way to the DLQ."""

    row: dict[str, Any]
    error: str


def parse_rows(raw_rows: list[dict[str, Any]]) -> tuple[list[IncomingComment], list[RejectedRow]]:
    """Validate row by row, and never let one bad row reject the batch.

    This used to be a list comprehension inside a single try, so a single
    unparseable row raised 422 for the WHOLE payload. `data/viral_post_dump.json`
    deliberately contains one such row — `created_at: "not-a-timestamp"` — and
    the generator that made it says the other 1,999 must still process, which is
    the point. They did not: `make replay-full` returned 422, inserted nothing,
    enqueued nothing, and put nothing in the DLQ. Step 9's unattended two-hour
    run would have finished in the first second with an empty database.

    Rejected rows are returned rather than raised so the caller can dead-letter
    them (hard rule #7: never swallow errors). A malformed row is a permanent
    failure, so it goes straight to `failed_jobs` instead of through arq's three
    retries — retrying a date that is not a date three times is not resilience.
    """
    parsed: list[IncomingComment] = []
    rejected: list[RejectedRow] = []

    for raw in raw_rows:
        try:
            parsed.append(IncomingComment(**raw))
        except (ValidationError, TypeError) as exc:
            rejected.append(RejectedRow(row=raw, error=_describe(exc)))

    return parsed, rejected


def _describe(exc: Exception) -> str:
    """A one-line reason a person can act on, not a JSON blob.

    This string is what the Failed Jobs panel shows, so "created_at: Input
    should be a valid datetime" has to survive to the screen intact.
    """
    if isinstance(exc, ValidationError):
        return "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or 'row'}: {error['msg']}"
            for error in exc.errors(include_url=False)
        )
    return f"{type(exc).__name__}: {exc}"


def _csv_rows(raw: bytes) -> list[dict[str, Any]]:
    return list(csv.DictReader(io.StringIO(raw.decode())))


async def _read_payload(request: Request) -> list[dict[str, Any]]:
    """Accept a JSON array, a CSV upload, or a raw CSV body.

    Content-type branching rather than two typed parameters: declaring an
    `UploadFile` alongside a JSON body makes FastAPI treat the whole endpoint as
    multipart, and the JSON array then never binds — which is a 422 on the happy
    path that `make replay` uses.

    Returns raw dicts. Validation happens per row in `parse_rows`, because a
    payload that is structurally fine except for one row is not a bad request.
    """
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise HTTPException(status_code=422, detail="Expected a 'file' part")
        return _csv_rows(await upload.read())

    if "csv" in content_type:
        return _csv_rows(await request.body())

    try:
        rows = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Body is not valid JSON") from exc
    if not isinstance(rows, list):
        raise HTTPException(status_code=422, detail="Expected a JSON array of comments")
    if any(not isinstance(row, dict) for row in rows):
        raise HTTPException(status_code=422, detail="Every element must be a JSON object")
    return rows


@router.post(
    "/ingest/comments",
    response_model=IngestResult,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/IncomingComment"},
                    }
                },
                "text/csv": {"schema": {"type": "string"}},
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {"file": {"type": "string", "format": "binary"}},
                    }
                },
            }
        }
    },
)
async def ingest_comments(request: Request, session: SessionDep) -> IngestResult:
    """Insert new comments and enqueue one job per NEW comment.

    Idempotent: replaying the same dump inserts nothing the second time.
    """
    raw_rows = await _read_payload(request)
    if not raw_rows:
        raise HTTPException(status_code=422, detail="Provide a JSON array or a CSV file")

    payload, rejected = parse_rows(raw_rows)
    await dead_letter_rows(session, rejected)

    posts = await _resolve_posts(session)

    rows: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    skipped = 0

    for comment in payload:
        post_id = posts.get((comment.account_handle, comment.post_external_id))
        if post_id is None:
            # An unknown post is a data problem, not a transient one; retrying
            # would not help, so it is counted rather than raised.
            skipped += 1
            continue

        # Deduplicated within the batch as well as against the table. The dumps
        # are generated with stable external_ids, but a hand-assembled payload
        # with the same row twice would otherwise reach ON CONFLICT twice in one
        # statement, and only the first insert is visible to the second's
        # conflict check — so the duplicate would slip through.
        key = (post_id, comment.external_id)
        if key in seen:
            skipped += 1
            continue
        seen.add(key)

        rows.append(
            {
                "post_id": post_id,
                "external_id": comment.external_id,
                "author": comment.author,
                "text": comment.text,
                "created_at": comment.created_at,
            }
        )

    inserted_ids: list[int] = []
    if rows:
        # One statement, not one per comment. D9 makes replaying deliberate and
        # repeated, and `replay-full` is 2,000 rows: at a round trip each, the
        # round trips dominate everything else this endpoint does — which the
        # docstring on `_resolve_posts` already said, while the insert loop
        # below it did the opposite.
        #
        # Chunked because a single statement carries five bind parameters per
        # row, and Postgres caps a statement at 65,535 of them.
        for chunk in _chunks(rows, CHUNK_ROWS):
            statement = (
                insert(Comment)
                .values(chunk)
                # D9. ON CONFLICT on exactly the (post_id, external_id) unique
                # constraint, so a replayed dump is a no-op rather than a
                # duplicate charge. RETURNING yields only the rows that were
                # actually inserted, which is exactly what needs enqueueing.
                .on_conflict_do_nothing(index_elements=["post_id", "external_id"])
                .returning(Comment.id)
            )
            inserted_ids.extend((await session.execute(statement)).scalars().all())

    # Anything accepted but not inserted was already present.
    skipped += len(rows) - len(inserted_ids)

    await session.commit()

    enqueued = await enqueue_comments(inserted_ids)
    if rejected:
        log.warning(
            "ingest.rows_rejected", rejected=len(rejected), accepted=len(payload)
        )
    return IngestResult(
        inserted=len(inserted_ids),
        skipped=skipped,
        enqueued=enqueued,
        rejected=len(rejected),
    )


async def dead_letter_rows(session: SessionDep, rejected: list[RejectedRow]) -> None:
    """One `failed_jobs` row per unparseable input row (hard rule #7).

    `job_type="ingest_comment"` rather than "process_comment": it never became a
    job, and labelling it as one would make the Retry button re-enqueue a
    comment id that does not exist. The payload is the original row, which is
    what makes the row actionable — someone can read the bad field on the Failed
    Jobs panel and fix the source.
    """
    for item in rejected:
        session.add(
            FailedJob(
                job_type="ingest_comment",
                payload_json=item.row,
                error=item.error,
                # It failed at the boundary, before arq ever saw it. A malformed
                # date is permanent, so there is nothing for the three retries in
                # hard rule #7 to accomplish.
                attempts=1,
            )
        )


class RequeueResult(BaseModel):
    requeued: int


@router.post("/queue/requeue", response_model=RequeueResult)
async def requeue_unprocessed(session: SessionDep) -> RequeueResult:
    """Re-enqueue every comment still at `new` and every asset still unanalysed.

    Ingest only enqueues comments it actually inserted (D9), which is right: it
    is what stops a replayed dump re-spending model calls. But it means a job
    lost to a worker outage is never retried — the comment stays `new` forever
    and the queue looks healthy. This is the recovery path, and it is what
    step 9's Retry button calls.

    Idempotent for the same reason ingest is: the job key is derived from the
    comment id, so a comment already queued is not queued twice.
    """
    attempt = f"-retry-{int(time.time())}"

    stuck_comments = (
        (await session.execute(select(Comment.id).where(Comment.status == "new")))
        .scalars()
        .all()
    )
    # Assets too. The asset row is committed before the job is enqueued — it has
    # to be, or the worker beats its own row to the database — so a Redis blip
    # between those two lines leaves a row with no job and no `failed_jobs`
    # entry, because no job ever existed. The card then reads "Analysing the
    # photo…" forever. `analysis_json IS NULL` is the same marker the graph uses
    # for "not yet processed".
    stuck_assets = (
        (await session.execute(select(Asset.id).where(Asset.analysis_json.is_(None))))
        .scalars()
        .all()
    )

    requeued = await enqueue_comments(list(stuck_comments), attempt=attempt)
    for asset_id in stuck_assets:
        requeued += await enqueue_asset(asset_id, attempt=attempt)

    return RequeueResult(requeued=requeued)


class QueueStats(BaseModel):
    queued: int
    running: int
    failed: int


@router.get("/queue/stats", response_model=QueueStats)
async def queue_stats(session: SessionDep) -> QueueStats:
    """Live queue depth for the top bar, polled every 2s.

    Read straight from Redis and the DLQ table — see `services/queue.py` for why
    it is not sampled into a table (D18).
    """
    queued, running = await queue_depth()
    failed = int(await session.scalar(select(func.count()).select_from(FailedJob)) or 0)

    return QueueStats(queued=queued, running=running, failed=failed)
