"""Shared test fixtures.

Config is required-by-default (`app.config`), so the environment must be populated
before anything imports the app. Compose already sets these for the container, but
setting them here keeps the suite runnable anywhere.
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

# Hard rule #10's `models.ALLOW_MODEL_REQUESTS = False` guard lives in the WORKER's
# conftest, not here: pydantic-ai is a worker dependency and the API never calls a
# model. Importing it here to set a flag would add the dependency the rule guards.

