"""Brand schemas, including the typed shape of `brand_rules_json` (D16)."""

from pydantic import BaseModel, Field

from app.schemas.base import CreateModel, ORMModel


class BrandTone(BaseModel):
    avoid_words: list[str]
    prefer_words: list[str]


class BrandRules(BaseModel):
    """D16: one shape, three consumers.

    Media checks `prohibited_content` and `required_elements`; content respects
    `max_hashtags` and `tone`; response uses `tone.avoid_words`. The column stays
    JSONB — typing it here is what stops the three agents finding different shapes.
    """

    prohibited_content: list[str]
    required_elements: list[str]
    tone: BrandTone
    max_hashtags: int = Field(ge=0, le=30)


class BrandCreate(CreateModel):
    name: str = Field(min_length=1, max_length=120)
    voice_guidelines: str
    brand_rules_json: BrandRules


class BrandRead(ORMModel):
    id: int
    name: str
    voice_guidelines: str
    brand_rules_json: BrandRules
