"""The single place the API reads environment variables (CLAUDE.md hard rule #1).

Nothing else in `app/` may call `os.environ`. Every value is required and has no
default, so a missing variable fails at import time rather than halfway through a
request. There is no `localhost` anywhere in here: hostnames come from the
environment, which is what makes the Phase 2+ move to RDS/ElastiCache an env change.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Mirrors `worker/worker/config.py`. A validation allowlist, not a hardcoded
# provider — the value is still chosen only by LLM_PROVIDER (ADR-0002, D21). The
# API declares it so a misconfigured deployment fails at API start, not at the
# first job an hour into a replay.
LLMProvider = Literal["ollama", "bedrock"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str
    redis_url: str

    storage_backend: Literal["local"]
    storage_root: str

    llm_provider: LLMProvider
    llm_model_fast: str
    llm_model_text: str
    llm_model_vision: str
    ollama_base_url: str

    # The tier → model map deliberately lives ONLY in `worker/worker/config.py` (D6).
    # The API never calls a model, so a copy here would be a second source of truth for
    # the exact mapping D6 exists to centralise. The variables are still declared and
    # required so a misconfigured deployment fails at API start, not at first job.


@lru_cache
def get_settings() -> Settings:
    """Cached so the environment is parsed once per process.

    This is a pure read of immutable config, not the mutable module state hard
    rule #2 forbids.
    """
    return Settings()
