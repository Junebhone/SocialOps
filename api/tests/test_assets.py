"""Upload, and the route that serves an uploaded file.

The upload is the front half of step 6's demo criterion — "upload one product
photo and watch three platform-specific drafts appear". Everything the worker
does afterwards is covered in the worker suite; this is the HTTP seam.
"""

import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import Asset
from app.routers.params import get_storage
from app.storage import LocalDiskStorage
from tests.conftest import FakeQueue
from tests.factories import a_brand


@pytest.fixture(autouse=True)
def storage(tmp_path: Path) -> Iterator[LocalDiskStorage]:
    """Write into a temp directory, never the real ./storage volume.

    Same reasoning as the queue guard in conftest: the compose volume holds the
    files a demo is about to be run against, and a test suite must not be able
    to add to it or delete from it.
    """
    backend = LocalDiskStorage(tmp_path)
    app.dependency_overrides[get_storage] = lambda: backend
    yield backend
    app.dependency_overrides.pop(get_storage, None)


def a_png(width: int = 64, height: int = 64) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (200, 120, 60)).save(buffer, format="PNG")
    return buffer.getvalue()


def upload(data: bytes | None = None, name: str = "bag.png", mime: str = "image/png") -> Any:
    return {"file": (name, data if data is not None else a_png(), mime)}


async def test_uploading_an_image_stores_it_and_queues_the_media_job(
    client: AsyncClient, session: AsyncSession, storage: LocalDiskStorage, queue: FakeQueue
) -> None:
    brand = await a_brand(session)

    response = await client.post("/assets", params={"brand_id": brand.id}, files=upload())

    assert response.status_code == 201
    body = response.json()
    assert body["enqueued"] is True
    assert body["asset"]["brand_id"] == brand.id
    assert body["asset"]["filename"] == "bag.png"
    assert body["asset"]["analysis_json"] is None

    # The bytes are actually on disk, under the key the API reported.
    assert await storage.get(body["asset"]["storage_key"]) == a_png()
    # And exactly one media job is waiting, keyed by asset id (D9).
    assert list(queue.jobs) == [f"asset-{body['asset']['id']}"]
    assert queue.jobs[f"asset-{body['asset']['id']}"][0] == "process_asset"


async def test_the_response_carries_a_url_the_browser_can_fetch(
    client: AsyncClient, session: AsyncSession
) -> None:
    """`url` is not a column — it is whatever the backend produced. The web app
    is never told which backend it is, which is the point of hard rule #9."""
    brand = await a_brand(session)

    created = (await client.post("/assets", params={"brand_id": brand.id}, files=upload())).json()

    served = await client.get(created["asset"]["url"])
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert served.content == a_png()


async def test_the_upload_is_committed_before_the_job_is_queued(
    client: AsyncClient, session: AsyncSession, queue: FakeQueue
) -> None:
    """The worker picks the job up in milliseconds. A job that arrives before
    its row is visible fails with 'asset not found' and burns all three retries
    into the DLQ."""
    brand = await a_brand(session)

    created = (await client.post("/assets", params={"brand_id": brand.id}, files=upload())).json()

    asset_id = created["asset"]["id"]
    _function, args = queue.jobs[f"asset-{asset_id}"]
    assert args == (asset_id,)
    assert (await session.get(Asset, asset_id)) is not None


async def test_brand_id_is_required(client: AsyncClient) -> None:
    """D17, on the write path too: an asset on the wrong brand is checked
    against the wrong rules and drafted in the wrong voice."""
    assert (await client.post("/assets", files=upload())).status_code == 422


async def test_an_unknown_brand_is_a_404(client: AsyncClient) -> None:
    response = await client.post("/assets", params={"brand_id": 4242}, files=upload())

    assert response.status_code == 404


async def test_a_non_image_is_refused(client: AsyncClient, session: AsyncSession) -> None:
    """An allowlist, not a blocklist: the file is decoded by Pillow and then
    sent to a model, so 'not obviously dangerous' is the wrong default."""
    brand = await a_brand(session)

    response = await client.post(
        "/assets",
        params={"brand_id": brand.id},
        files=upload(b"%PDF-1.4", name="report.pdf", mime="application/pdf"),
    )

    assert response.status_code == 415


async def test_an_empty_file_is_refused(client: AsyncClient, session: AsyncSession) -> None:
    brand = await a_brand(session)

    response = await client.post("/assets", params={"brand_id": brand.id}, files=upload(b""))

    assert response.status_code == 422


async def test_an_oversized_file_is_refused(
    client: AsyncClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cap is lowered rather than a 10 MB body posted — proving a comparison
    works does not need ten megabytes of test fixture."""
    from app.routers import assets as assets_router

    monkeypatch.setattr(assets_router, "MAX_UPLOAD_BYTES", 16)
    brand = await a_brand(session)

    response = await client.post("/assets", params={"brand_id": brand.id}, files=upload())

    assert response.status_code == 413


async def test_nothing_is_stored_when_the_upload_is_refused(
    client: AsyncClient, session: AsyncSession, storage: LocalDiskStorage, queue: FakeQueue
) -> None:
    """A rejected upload must leave no file, no row and no job — otherwise the
    Content page grows orphan cards nobody can explain."""
    brand = await a_brand(session)

    await client.post(
        "/assets",
        params={"brand_id": brand.id},
        files=upload(b"nope", name="x.pdf", mime="application/pdf"),
    )

    assert (await session.execute(select(Asset))).scalars().all() == []
    assert queue.jobs == {}
    assert list(storage.root.rglob("*")) == []


async def test_the_uploaded_filename_never_becomes_a_path(
    client: AsyncClient, session: AsyncSession, storage: LocalDiskStorage
) -> None:
    """The filename is attacker-controlled. It is kept on assets.filename for
    display and is not what the key is built from."""
    brand = await a_brand(session)

    created = (
        await client.post(
            "/assets",
            params={"brand_id": brand.id},
            files=upload(name="../../../../etc/passwd.png"),
        )
    ).json()

    key = created["asset"]["storage_key"]
    assert key.startswith(f"brands/{brand.id}/")
    assert "passwd" not in key
    assert (storage.root / key).is_file()


async def test_serving_a_key_with_no_row_is_a_404(client: AsyncClient) -> None:
    """A key with no `assets` row is a 404 even if bytes exist, so this route
    cannot be used to enumerate the storage volume."""
    assert (await client.get("/assets/file/brands/1/nope.png")).status_code == 404


async def test_serving_a_traversing_key_is_refused(client: AsyncClient) -> None:
    assert (await client.get("/assets/file/../../etc/passwd")).status_code in (307, 404)


async def test_a_row_whose_bytes_are_gone_is_a_404_not_a_500(
    client: AsyncClient, session: AsyncSession, storage: LocalDiskStorage
) -> None:
    """A volume wiped between a demo reset and a reseed. It has its own message
    because it means something different from 'no such asset'."""
    brand = await a_brand(session)
    created = (await client.post("/assets", params={"brand_id": brand.id}, files=upload())).json()
    await storage.delete(created["asset"]["storage_key"])

    response = await client.get(created["asset"]["url"])

    assert response.status_code == 404
    assert "missing from storage" in response.json()["detail"]


async def test_the_served_mime_comes_from_the_row_not_the_extension(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Echoing a caller-influenced content type back to a browser is how an
    'image' gets served as HTML."""
    brand = await a_brand(session)
    created = (
        await client.post(
            "/assets",
            params={"brand_id": brand.id},
            files=upload(a_png(), name="bag.html", mime="image/png"),
        )
    ).json()

    served = await client.get(created["asset"]["url"])

    assert served.headers["content-type"] == "image/png"
