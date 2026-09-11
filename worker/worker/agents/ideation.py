"""Ideation: propose content angles from seeded trend signals for one brand."""

from typing import ClassVar

from worker.agents.base import BaseAgent
from worker.agents.schemas import IdeationInput, IdeationOutput
from worker.config import Tier


class IdeationAgent(BaseAgent[IdeationInput, IdeationOutput]):
    # `standard`, not `fast`: this is a generative task (several original post
    # concepts), not a bounded classification, and it runs on demand — once per
    # "Generate Ideas" click, not thousands of times per replay like triage.
    tier: ClassVar[Tier] = "standard"
    prompt_name = "ideation"
    output_schema = IdeationOutput
