"""Step 0 acceptance: the worker's config is the only thing that knows a model name."""

import pytest
from pydantic_ai import models

from worker.config import Settings


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
