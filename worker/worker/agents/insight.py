"""Insight: find plain-language patterns in a brand's real post performance."""

from typing import ClassVar

from worker.agents.base import BaseAgent
from worker.agents.schemas import InsightInput, InsightOutput
from worker.config import Tier


class InsightAgent(BaseAgent[InsightInput, InsightOutput]):
    # `standard`, not `fast`. Measured, not assumed: a first live run on
    # qwen3:0.6b (fast) didn't compare posts at all — it echoed four input
    # lines back verbatim as "markers", satisfying the output schema while
    # doing none of the actual reasoning. Comparing performance ACROSS several
    # posts and synthesizing a pattern is generative reasoning, not bounded
    # per-item classification — closer to content/response's shape than
    # triage's, whatever the original plan assumed on paper.
    tier: ClassVar[Tier] = "standard"
    prompt_name = "insight"
    output_schema = InsightOutput
