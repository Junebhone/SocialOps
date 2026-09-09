"""The agent contract (CLAUDE.md hard rule #3).

An agent is a prompt, an output schema, and a tier. It does not touch the queue,
it does not touch the database, and it does not know what model it runs on —
`config.py` maps its tier to a model name (D6), and the orchestrator does the
persisting.

Keeping agents this thin is what lets the same class be exercised against
`TestModel` in a unit test and against Qwen in a replay without changing a line.
"""

from __future__ import annotations

from abc import ABC
from typing import ClassVar

from pydantic import BaseModel

from worker.config import Tier
from worker.llm import PromptImage, Usage, complete


class BaseAgent[InputT: BaseModel, OutputT: BaseModel](ABC):
    """Subclasses declare the three class attributes and nothing else.

    A subclass overrides `variables()` when its prompt needs something other
    than the input model's own fields.
    """

    # Which model tier this agent needs. NEVER a model name (D6) — that mapping
    # belongs to config, so switching Ollama for Bedrock touches no agent.
    tier: ClassVar[Tier]
    # Filename in agents/prompts/, without the .md (hard rule #6).
    prompt_name: ClassVar[str]
    # The contract the prompt asks the model to satisfy. Under PromptedOutput
    # the prompt IS the whole contract, so this and the prompt must agree.
    output_schema: ClassVar[type[BaseModel]]

    def variables(self, payload: InputT) -> dict[str, object]:
        """Values for the prompt's `{{placeholders}}`. Input fields by default."""
        return payload.model_dump()

    def images(self, payload: InputT) -> list[PromptImage] | None:
        """Images for a vision-tier agent. None for text agents.

        Cheap by contract: the orchestrator node has already decoded, rotated
        and downscaled the bytes. Doing that work here would put it inside the
        window `complete()` times, and latency per agent is a step 9 deliverable.
        """
        return None

    async def run_with_usage(self, payload: InputT) -> tuple[OutputT, Usage]:
        """Run the agent and report what the call cost.

        The orchestrator uses this one: hard rule #5 requires it to write tokens,
        cost and latency into `agent_runs`, and that information only exists at
        the moment of the call.
        """
        output, usage = await complete(
            prompt_name=self.prompt_name,
            variables=dict(self.variables(payload)),
            schema=self.output_schema,
            tier=self.tier,
            images=self.images(payload),
        )
        return output, usage  # type: ignore[return-value]

    async def run(self, payload: InputT) -> OutputT:
        """The contract in hard rule #3: `run(input) -> output`.

        Delegates to `run_with_usage` and drops the usage. Both exist because
        rule #3 defines the agent's public shape while rule #5 needs the numbers;
        returning a tuple from `run` would satisfy the second by breaking the
        first, and stashing usage on `self` would make agents stateful.
        """
        output, _usage = await self.run_with_usage(payload)
        return output
