"""Response: draft a reply in the brand's voice. Runs only when triage says so."""

from worker.agents.base import BaseAgent
from worker.agents.schemas import ResponseInput, ResponseOutput


class ResponseAgent(BaseAgent[ResponseInput, ResponseOutput]):
    # `standard`: drafting in a brand's voice is where the larger model earns its
    # latency, and it runs on roughly two thirds of comments rather than all.
    tier = "standard"
    prompt_name = "response"
    output_schema = ResponseOutput
