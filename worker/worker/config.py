"""The single place the worker reads environment variables (CLAUDE.md hard rule #1).

The API and the worker are separate containers and separate installable packages, so
they cannot share one module without a third shared package. Each service therefore
has exactly one `config.py`, which is what the rule is protecting: no scattered
`os.environ` calls, no hostname or model name written in code.

Tier → model lives here and nowhere else (D6). Agents declare a tier; only this file
knows that `fast` currently means `qwen3.5:2b`.
"""

from functools import lru_cache
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Tier = Literal["fast", "standard", "vision"]

# The providers this build knows how to construct a model for. This is a validation
# allowlist, not a hardcoded provider: which one runs is still chosen only by
# LLM_PROVIDER in the environment (ADR-0002). It is a named alias rather than an
# inline Literal so `worker/llm.py` can `match` on it exhaustively — adding a third
# provider then makes mypy point at the factory that has not handled it yet, instead
# of leaving a typo to surface as a runtime crash on the first model call. See D21.
LLMProvider = Literal["ollama", "bedrock"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str
    redis_url: str

    storage_backend: Literal["local", "s3"]
    # A directory for `local`, the bucket name for `s3` (infra/stack/main.tf).
    storage_root: str
    # Only S3 needs it, so it is the one optional field here. The validator below
    # still makes a missing region fail at startup rather than at the first image.
    aws_region: str | None = None

    llm_provider: LLMProvider
    llm_model_fast: str
    llm_model_text: str
    llm_model_vision: str
    ollama_base_url: str

    @model_validator(mode="after")
    def _s3_needs_a_region(self) -> Self:
        if self.storage_backend == "s3" and not self.aws_region:
            raise ValueError("STORAGE_BACKEND=s3 needs AWS_REGION")
        return self

    def model_for_tier(self, tier: Tier) -> str:
        """Tier → model name (D6). Agents never name a model."""
        return {
            "fast": self.llm_model_fast,
            "standard": self.llm_model_text,
            "vision": self.llm_model_vision,
        }[tier]

    @property
    def ollama_openai_base_url(self) -> str:
        """Pydantic AI's OllamaProvider needs the OpenAI-compatible `/v1` path.

        `OLLAMA_BASE_URL` is documented in CLAUDE.md without the suffix because that
        is the address of the Ollama server itself. Normalising here keeps the env var
        matching the docs and stops `/v1/v1` if someone sets the full path anyway.
        """
        base = self.ollama_base_url.rstrip("/")
        return base if base.endswith("/v1") else f"{base}/v1"


@lru_cache
def get_settings() -> Settings:
    """Cached so the environment is parsed once per worker process."""
    return Settings()
