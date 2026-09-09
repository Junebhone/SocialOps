"""Asset upload and the route that serves an uploaded file.

The upload is the front half of step 6's demo criterion — "upload one product
photo and watch three platform-specific drafts appear". Everything after the
`201` happens in the worker's asset graph.
"""

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select

from app.db import SessionDep
from app.models import Asset, Brand
from app.routers.params import BrandIdQuery, StorageDep
from app.schemas.asset import AssetRead
from app.services.queue import enqueue_asset
from app.storage import ASSET_FILE_ROUTE, StorageError, new_key

router = APIRouter(tags=["assets"])

# What a vision model can actually read, and nothing else. An allowlist rather
# than a blocklist: the file is decoded by Pillow in the worker and then sent to
# a model, so "anything that is not obviously dangerous" is the wrong default.
ALLOWED_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}

# 10 MB. Comfortably above a phone photo and far below what would make the
# worker's decode step a memory problem — the pixel-count guard in
# worker/images.py handles the other half of that, since a small file can still
# declare an enormous canvas.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class UploadResult(BaseModel):
    """The asset, plus the job that will analyse it.

    `enqueued` is false when the job key already existed, which is how the
    caller can tell a re-upload from a first one without reading the queue.
    """

    asset: AssetRead
    enqueued: bool


@router.post("/assets", response_model=UploadResult, status_code=201)
async def upload_asset(
    session: SessionDep,
    storage: StorageDep,
    brand_id: BrandIdQuery,
    file: Annotated[UploadFile, ...],
) -> Any:
    """Store one image and enqueue the media job.

    `brand_id` is a required query param here for the same reason it is on every
    list endpoint (D17): an asset that lands on the wrong brand gets checked
    against the wrong rules and drafted in the wrong voice.
    """
    if (await session.get(Brand, brand_id)) is None:
        raise HTTPException(status_code=404, detail=f"Brand {brand_id} not found")

    mime = (file.content_type or "").split(";")[0].strip().lower()
    if mime not in ALLOWED_MIME:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported type {mime or 'unknown'}. Allowed: {', '.join(ALLOWED_MIME)}",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="The uploaded file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is {len(data)} bytes; the limit is {MAX_UPLOAD_BYTES}",
        )

    filename = file.filename or f"upload{ALLOWED_MIME[mime]}"
    key = new_key(brand_id, filename)
    await storage.put(key, data)

    asset = Asset(brand_id=brand_id, filename=filename, storage_key=key, mime=mime)
    session.add(asset)
    # Committed BEFORE the enqueue, not after. The worker picks the job up in
    # milliseconds, and a job that arrives before its row is visible fails with
    # "asset not found" and burns all three retries into the DLQ.
    await session.commit()

    enqueued = await enqueue_asset(asset.id)
    return UploadResult(asset=_read(asset, storage.url(key)), enqueued=enqueued)


@router.get(
    f"{ASSET_FILE_ROUTE}/{{key:path}}",
    response_class=Response,
    responses={200: {"content": {"image/*": {}}}},
)
async def serve_asset_file(key: str, session: SessionDep, storage: StorageDep) -> Response:
    """Serve the bytes behind a storage key.

    Declared before any `/assets/{id}` route would be, because FastAPI matches
    in declaration order and `file` would otherwise be parsed as an id.

    The mime comes from the `assets` row rather than from the key's extension:
    the extension is derived from a filename the uploader chose, and echoing a
    caller-influenced content type back to a browser is how an "image" gets
    served as HTML. A key with no row is a 404 even if the bytes exist, which
    also means this cannot be used to enumerate the storage volume.

    In Phase 4 `S3Storage.url()` returns a presigned URL and this route stops
    being called at all — the web app only ever uses the `url` the API gave it.
    """
    asset = await _asset_for_key(session, key)
    if asset is None:
        raise HTTPException(status_code=404, detail="No such asset")

    try:
        data = await storage.get(key)
    except StorageError as exc:
        # The row exists but the bytes do not: a volume wiped between a demo
        # reset and a reseed. Worth its own message, because "404" here means
        # something different from "no such asset".
        raise HTTPException(status_code=404, detail="Asset file is missing from storage") from exc

    return Response(
        content=data,
        media_type=asset.mime,
        # Immutable by construction: a storage key contains a uuid and is never
        # rewritten, so the browser can keep it for as long as it likes.
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


async def _asset_for_key(session: SessionDep, key: str) -> Asset | None:
    return (
        await session.execute(select(Asset).where(Asset.storage_key == key))
    ).scalar_one_or_none()


def _read(asset: Asset, url: str) -> AssetRead:
    """ORM row + the backend's URL, which is not a column."""
    return AssetRead.model_validate(
        {
            **{column.name: getattr(asset, column.name) for column in Asset.__table__.columns},
            "url": url,
        }
    )
