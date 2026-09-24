"""Query parameters and dependencies shared by the routers.

`app/storage.py` deliberately does not define the storage dependency itself: the
worker imports that module (D24) and does not have FastAPI installed, so a
`from fastapi import Depends` at its top would break the worker at import.
Framework wiring lives on this side of the line; the backend itself stays plain.
"""

from typing import Annotated

from fastapi import Depends, Query, Request

from app.storage import StorageBackend

# D17. No default — that alone is what makes it required, so an omitted brand_id
# is a 422 rather than an unscoped query quietly returning another brand's rows.
BrandIdQuery = Annotated[
    int,
    Query(description="Brand scope. Required: a shared link must resolve to the same view."),
]

LimitQuery = Annotated[int, Query(ge=1, le=200)]
OffsetQuery = Annotated[int, Query(ge=0)]


def get_storage(request: Request) -> StorageBackend:
    """The API's storage backend, built once in the lifespan from the API's own
    config (D22) and reached through `request.state`, like the engine.

    Not a module global (hard rule #2), and not built per request: an S3 client
    costs tens of milliseconds to construct and is safe to share (D25).
    """
    storage: StorageBackend = request.state.storage
    return storage


StorageDep = Annotated[StorageBackend, Depends(get_storage)]
