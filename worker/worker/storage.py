"""The worker's view of storage (hard rule #9).

There is exactly one implementation and it is `app/storage.py`, copied into this
image at build time the same way the SQLAlchemy models are (D24). The API writes
an upload and the worker reads it back; a second implementation of "what does a
storage_key mean on disk" would drift, and the drift would only ever surface on
the media path.

What this module adds is the config read: D22 says each service resolves its own
environment, so the worker builds its backend from the worker's `Settings` and
never from the API's.
"""

from __future__ import annotations

from functools import lru_cache

from app.storage import (
    LocalDiskStorage,
    S3Storage,
    StorageBackend,
    StorageError,
    build_storage,
    new_key,
    s3_client,
    validate_key,
)

from worker.config import get_settings


@lru_cache
def get_storage() -> StorageBackend:
    """The worker's storage backend, built once per process from the worker's own
    config (D22).

    Cached like `get_settings`: an S3 client costs tens of milliseconds to build
    and is safe to share, and the worker is one event loop, so there is no race
    to build it. Hard rule #2's "no module-level state" is the API's rule; the
    worker already caches its settings the same way.
    """
    settings = get_settings()
    return build_storage(settings.storage_backend, settings.storage_root, settings.aws_region)


__all__ = [
    "LocalDiskStorage",
    "S3Storage",
    "StorageBackend",
    "StorageError",
    "build_storage",
    "get_storage",
    "new_key",
    "s3_client",
    "validate_key",
]
