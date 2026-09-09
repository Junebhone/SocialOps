"""Triage: classify one comment. The first node of the comment path."""

from typing import ClassVar

from worker.agents.base import BaseAgent
from worker.agents.schemas import TriageInput, TriageOutput
from worker.config import Tier


class TriageAgent(BaseAgent[TriageInput, TriageOutput]):
    # `fast` because triage is a bounded classification run thousands of times
    # per replay (D4). Whether that is still the right tier is a live question —
    # see docs/eval.md, where 2b is 8 points behind 9b.
    tier: ClassVar[Tier] = "fast"
    prompt_name = "triage"
    output_schema = TriageOutput
