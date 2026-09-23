"""Analytics: turn one brand's weekly numbers into a short plain-English summary."""

from typing import ClassVar

from worker.agents.base import BaseAgent
from worker.agents.schemas import AnalyticsInput, AnalyticsOutput
from worker.config import Tier


class AnalyticsAgent(BaseAgent[AnalyticsInput, AnalyticsOutput]):
    # `fast`, per the module plan. This is narrower than the insight agent's
    # job, which had to move to `standard` (see agents/insight.py): insight
    # compares posts and synthesizes a pattern, while this agent only restates
    # figures it is handed. Every number is computed by SQL beforehand
    # (ADR-0005), so the model never does arithmetic.
    tier: ClassVar[Tier] = "fast"
    prompt_name = "analytics"
    output_schema = AnalyticsOutput
