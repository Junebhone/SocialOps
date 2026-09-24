"""Step 0 acceptance: the worker's config is the only thing that knows a model name."""

import pytest
from pydantic import ValidationError
from pydantic_ai import models

from worker.config import Settings


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


def test_tier_maps_to_configured_model() -> None:
    """D6: three tiers, and in Phase 1 standard and vision resolve to one model (D20)."""
    settings = _settings(llm_model_text="qwen3.5:9b", llm_model_vision="qwen3.5:9b")

    assert settings.model_for_tier("fast") == "fast-model"
    assert settings.model_for_tier("standard") == "qwen3.5:9b"
    assert settings.model_for_tier("vision") == "qwen3.5:9b"


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("http://host.docker.internal:11434", "http://host.docker.internal:11434/v1"),
        ("http://host.docker.internal:11434/", "http://host.docker.internal:11434/v1"),
        ("http://host.docker.internal:11434/v1", "http://host.docker.internal:11434/v1"),
    ],
)
def test_ollama_base_url_normalises_to_openai_path(configured: str, expected: str) -> None:
    """Pydantic AI's OllamaProvider needs `/v1`; the env var documents the server address."""
    assert _settings(ollama_base_url=configured).ollama_openai_base_url == expected


def test_real_model_requests_are_blocked() -> None:
    """Hard rule #10 is enforced by the suite, not by convention."""
    assert models.ALLOW_MODEL_REQUESTS is False


def test_s3_storage_is_accepted_with_a_region() -> None:
    """Phase 4: the ECS task sets STORAGE_BACKEND=s3 and AWS_REGION (infra/stack)."""
    settings = _settings(storage_backend="s3", storage_root="bucket", aws_region="us-east-2")

    assert settings.storage_backend == "s3"
    assert settings.aws_region == "us-east-2"


def test_s3_storage_without_a_region_fails_at_startup() -> None:
    """Caught when the worker boots, not on the first image an hour into a replay."""
    with pytest.raises(ValidationError, match="AWS_REGION"):
        _settings(storage_backend="s3", storage_root="bucket")
