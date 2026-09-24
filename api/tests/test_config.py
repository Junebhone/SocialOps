"""The API's config accepts the Phase 4 storage backend, and only with a region."""

import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.fixture(autouse=True)
def no_region_in_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings also reads the environment, so an AWS_REGION exported in the
    shell or CI job would satisfy the "missing region" tests by accident."""
    monkeypatch.delenv("AWS_REGION", raising=False)


def _settings(**overrides: str) -> Settings:
    base = {
        "database_url": "postgresql+asyncpg://u:p@postgres:5432/db",
        "redis_url": "redis://redis:6379/0",
        "storage_backend": "local",
        "storage_root": "/app/storage",
        "llm_provider": "ollama",
        "llm_model_fast": "fast-model",
        "llm_model_text": "text-model",
        "llm_model_vision": "vision-model",
        "ollama_base_url": "http://host.docker.internal:11434",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_local_storage_needs_no_region() -> None:
    """Phase 1 and the VM run with no AWS settings at all."""
    assert _settings().aws_region is None


def test_s3_storage_is_accepted_with_a_region() -> None:
    settings = _settings(storage_backend="s3", storage_root="bucket", aws_region="us-east-2")

    assert settings.storage_backend == "s3"


def test_s3_storage_without_a_region_fails_at_startup() -> None:
    with pytest.raises(ValidationError, match="AWS_REGION"):
        _settings(storage_backend="s3", storage_root="bucket")
