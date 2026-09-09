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

from pydantic import BaseModel, Field, field_validator


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


# --- media (vision tier) ---------------------------------------------------


class BrandCheck(BaseModel):
    """Whether the image is publishable under the brand's rules (D16).

    `issues` is the reason the brand manager reads on the Content page, so it
    stays a list of short sentences rather than rule ids — nothing else in the
    system resolves an id back to a rule.
    """

    passes: bool
    issues: list[str] = Field(default_factory=list)


class MediaOutput(BaseModel):
    """The media contract from CLAUDE.md."""

    description: str
    # Text the model can read IN the image — a label, a sign, packaging copy.
    # Empty list when there is none, never a null: the content agent renders
    # this straight into its prompt and `None` would arrive as the word "None".
    detected_text: list[str] = Field(default_factory=list)
    brand_check: BrandCheck


class MediaInput(BaseModel):
    """What the media agent needs.

    The image is carried here but never rendered into the prompt — `MediaAgent`
    overrides `variables()` to drop it. The default `model_dump()` would str()
    several hundred kilobytes of JPEG into the text, which a 9B model answers
    from as if it were the instruction.
    """

    image_data: bytes
    image_media_type: str
    # D16, rendered as plain comma-separated lists because the prompt is the
    # whole contract under PromptedOutput.
    prohibited_content: str
    required_elements: str


# --- content (standard tier) -----------------------------------------------

PLATFORMS: tuple[str, ...] = ("x", "instagram", "linkedin")


class PlatformDraft(BaseModel):
    """One platform's caption."""

    platform: Literal["x", "instagram", "linkedin"]
    text: str
    # Kept out of `text` so `max_hashtags` (D16) is checkable without parsing
    # prose, which is also why the column is separate.
    hashtags: list[str] = Field(default_factory=list)


class ContentOutput(BaseModel):
    """The content contract from CLAUDE.md: one draft per platform.

    CLAUDE.md describes the output as a bare list. It is wrapped in an object
    because `PromptedOutput` needs a BaseModel, and a named field also gives the
    prompt something to show — a top-level array is the shape small models are
    least reliable at closing.
    """

    drafts: list[PlatformDraft]

    @field_validator("drafts")
    @classmethod
    def one_draft_per_platform(cls, drafts: list[PlatformDraft]) -> list[PlatformDraft]:
        """Exactly x, instagram and linkedin — no repeats, none missing.

        Enforced here rather than patched up afterwards so Pydantic AI's own
        retry loop (retries=3, hard rule #4) gets a chance to fix it, and the
        model is told what was wrong. The Content page puts the three side by
        side; a response with two drafts would render a blank column, and one
        with two Instagram captions would silently drop LinkedIn.
        """
        found = [draft.platform for draft in drafts]
        if sorted(found) != sorted(PLATFORMS):
            raise ValueError(
                f"Expected exactly one draft for each of {', '.join(PLATFORMS)}; got {found}"
            )
        return drafts


class ContentInput(BaseModel):
    """What the content agent needs to write three captions.

    Everything here is already flattened to a string: the prompt is the whole
    contract, and a 9B model handles a comma-separated list far better than
    nested JSON pasted into an instruction.
    """

    description: str
    detected_text: str
    brand_voice: str
    # D16: one column, three consumers. Content reads tone and max_hashtags.
    avoid_words: str
    prefer_words: str
    max_hashtags: int
