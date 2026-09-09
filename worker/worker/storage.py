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

from app.storage import (
    LocalDiskStorage,
    StorageBackend,
    StorageError,
    build_storage,
    new_key,
    validate_key,
)

from worker.config import get_settings


def get_storage() -> StorageBackend:
    """The worker's storage backend, built from the worker's own config."""
    settings = get_settings()
    return build_storage(settings.storage_backend, settings.storage_root)


__all__ = [
    "LocalDiskStorage",
    "StorageBackend",
    "StorageError",
    "build_storage",
    "get_storage",
    "new_key",
    "validate_key",
]
