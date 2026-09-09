"""Query parameters and dependencies shared by the routers.

`app/storage.py` deliberately does not define the storage dependency itself: the
worker imports that module (D24) and does not have FastAPI installed, so a
`from fastapi import Depends` at its top would break the worker at import.
Framework wiring lives on this side of the line; the backend itself stays plain.
"""

from typing import Annotated

from fastapi import Depends, Query

from app.config import Settings, get_settings
from app.storage import StorageBackend, build_storage

# D17. No default — that alone is what makes it required, so an omitted brand_id
# is a 422 rather than an unscoped query quietly returning another brand's rows.
BrandIdQuery = Annotated[
    int,
    Query(description="Brand scope. Required: a shared link must resolve to the same view."),
]

LimitQuery = Annotated[int, Query(ge=1, le=200)]
OffsetQuery = Annotated[int, Query(ge=0)]


def get_storage(settings: Annotated[Settings, Depends(get_settings)]) -> StorageBackend:
    """The API's storage backend, built from the API's own config (D22).

    Built per request rather than held on the app: `LocalDiskStorage` is two
    immutable strings, so there is nothing to cache, and hard rule #2 says the
    API keeps no module-level mutable state. An S3 client in Phase 4 would move
    to the lifespan alongside the engine, and only this function would change.
    """
    return build_storage(settings.storage_backend, settings.storage_root)


StorageDep = Annotated[StorageBackend, Depends(get_storage)]
