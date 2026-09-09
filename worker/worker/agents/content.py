"""Content: turn one image analysis into three platform captions."""

from typing import ClassVar

from worker.agents.base import BaseAgent
from worker.agents.schemas import ContentInput, ContentOutput
from worker.config import Tier


class ContentAgent(BaseAgent[ContentInput, ContentOutput]):
    # `standard`. Writing three captions in a brand's voice is generation, not
    # classification, and it runs once per upload rather than thousands of times
    # per replay — so the larger model costs nothing that matters here.
    tier: ClassVar[Tier] = "standard"
    prompt_name = "content"
    output_schema = ContentOutput
