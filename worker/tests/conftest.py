"""Shared worker test fixtures.

Two jobs: populate the required environment before `worker.config` is imported, and
slam the door on real model calls. `ALLOW_MODEL_REQUESTS = False` makes hard rule #10
("no test may call a real model") something the suite enforces rather than something
we promise — any accidental live request raises instead of quietly hitting Ollama.
"""

import os

_TEST_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://socialops:socialops@postgres:5432/socialops",
    "REDIS_URL": "redis://redis:6379/0",
    "STORAGE_BACKEND": "local",
    "STORAGE_ROOT": "/app/storage",
    "LLM_PROVIDER": "ollama",
    "LLM_MODEL_FAST": "qwen3.5:2b",
    "LLM_MODEL_TEXT": "qwen3.5:9b",
    "LLM_MODEL_VISION": "qwen3.5:9b",
    "OLLAMA_BASE_URL": "http://host.docker.internal:11434",
}

for _key, _value in _TEST_ENV.items():
    os.environ.setdefault(_key, _value)

from pydantic_ai import models  # noqa: E402

models.ALLOW_MODEL_REQUESTS = False
