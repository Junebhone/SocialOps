"""Media: describe one uploaded image and check it against the brand's rules."""

from typing import ClassVar

from worker.agents.base import BaseAgent
from worker.agents.schemas import MediaInput, MediaOutput
from worker.config import Tier
from worker.llm import PromptImage


class MediaAgent(BaseAgent[MediaInput, MediaOutput]):
    # `vision`, which config resolves to the same model as `standard` — qwen3.5:9b
    # is multimodal (D20). The tier stays separate anyway: it is what lets Phase 4
    # point vision at a different Bedrock model without touching this file.
    tier: ClassVar[Tier] = "vision"
    prompt_name = "media"
    output_schema = MediaOutput

    def variables(self, payload: MediaInput) -> dict[str, object]:
        """Everything except the image.

        The default implementation is `payload.model_dump()`, which would render
        several hundred kilobytes of JPEG into the prompt text. The model then
        answers from the noise instead of the instruction — and the bytes are
        already going down the proper channel as `BinaryContent`.
        """
        return {
            "prohibited_content": payload.prohibited_content,
            "required_elements": payload.required_elements,
        }

    def images(self, payload: MediaInput) -> list[PromptImage]:
        """Already decoded, oriented and downscaled by the orchestrator node."""
        return [PromptImage(data=payload.image_data, media_type=payload.image_media_type)]
