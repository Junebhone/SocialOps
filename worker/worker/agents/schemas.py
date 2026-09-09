"""Agent output contracts.

One model per agent, named `<Agent>Output`. Under `PromptedOutput` the prompt is
the whole contract, so each of these must match the schema block written into
`prompts/<agent>.md` exactly — if they drift, the model is graded against a
schema it was never shown.

These Literals restate the ones in `api/app/enums.py` rather than importing
them: the api and the worker are separate installable packages in separate
containers (D22), and a shared package for four type aliases would cost more
than it saves. The database CHECK constraints are the backstop — a drift here
fails on insert rather than silently storing an invalid category.
"""

from typing import Literal

from pydantic import BaseModel, Field


class TriageOutput(BaseModel):
    """The triage contract from CLAUDE.md."""

    category: Literal["question", "complaint", "praise", "spam", "other"]
    # D8: a 5-point ordinal. Small models do not produce calibrated continuous
    # scores — they echo whatever numbers appear in the prompt's examples.
    sentiment: int = Field(ge=-2, le=2)
    needs_reply: bool
    urgency: Literal["low", "med", "high"]


class ResponseOutput(BaseModel):
    """The response contract from CLAUDE.md."""

    reply_text: str
    tone: str
    confidence: float = Field(ge=0.0, le=1.0)


class TriageInput(BaseModel):
    """What triage needs. Just the text — no brand context (CLAUDE.md contract)."""

    comment_text: str


class ResponseInput(BaseModel):
    """What the response agent needs to write in a brand's voice.

    `avoid_words` comes from `brand_rules_json.tone.avoid_words` (D16). It is
    rendered into the prompt as a plain comma-separated list, because the prompt
    is the whole contract under PromptedOutput.
    """

    comment_text: str
    brand_voice: str
    avoid_words: str
