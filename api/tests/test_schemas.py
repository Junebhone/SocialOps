"""Boundary validation. No database, so this stays the fast feedback loop."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.agent_run import AgentRunRead
from app.schemas.brand import BrandCreate, BrandRead, BrandRules
from app.schemas.comment import CommentRead
from app.schemas.post import PlatformAccountCreate
from tests.factories import BRAND_RULES, NOW


def _brand_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Ridgeline Roasters",
        "voice_guidelines": "Warm, plain-spoken.",
        "brand_rules_json": BRAND_RULES,
    }
    payload.update(overrides)
    return payload


def test_brand_read_validates_from_an_orm_object() -> None:
    """from_attributes matters outside FastAPI too — seed.py and the worker
    build schemas from ORM rows directly, where FastAPI's implicit handling
    does not apply."""

    class Row:
        id = 1
        name = "Ridgeline Roasters"
        voice_guidelines = "Warm."
        brand_rules_json = BRAND_RULES

    assert BrandRead.model_validate(Row()).name == "Ridgeline Roasters"


def test_brand_create_rejects_an_unknown_field() -> None:
    """A client must not be able to POST an id or a status it does not own."""
    with pytest.raises(ValidationError) as exc:
        BrandCreate(**_brand_payload(id=7))

    assert exc.value.errors()[0]["type"] == "extra_forbidden"


def test_brand_rules_requires_max_hashtags() -> None:
    """D16's shape is enforced at the boundary, not just described in a doc."""
    incomplete = {key: value for key, value in BRAND_RULES.items() if key != "max_hashtags"}

    with pytest.raises(ValidationError):
        BrandRules(**incomplete)


def test_brand_rules_keeps_the_three_consumers_fields() -> None:
    rules = BrandRules(**BRAND_RULES)

    assert rules.prohibited_content  # media
    assert rules.required_elements  # media
    assert rules.tone.avoid_words  # response
    assert rules.max_hashtags == 5  # content


def test_platform_account_create_rejects_an_unknown_platform() -> None:
    with pytest.raises(ValidationError):
        PlatformAccountCreate(brand_id=1, platform="tiktok", handle="@x")


@pytest.mark.parametrize("sentiment", [-3, 3])
def test_comment_read_rejects_a_sentiment_outside_the_range(sentiment: int) -> None:
    """The Sentiment alias carries ge=-2/le=2 into every schema that reuses it."""
    with pytest.raises(ValidationError):
        CommentRead(
            id=1,
            post_id=1,
            external_id="c-1",
            author="@rae",
            text="hi",
            created_at=NOW,
            sentiment=sentiment,
            status="new",
        )


def _agent_run(cost: Decimal | None) -> AgentRunRead:
    return AgentRunRead(
        id=1,
        agent="triage",
        entity_type="comment",
        entity_id=1,
        brand_id=1,
        status="ok",
        input_tokens=10,
        output_tokens=5,
        cost_usd=cost,
        latency_ms=120,
        created_at=NOW,
    )


def test_a_null_cost_serializes_as_null_not_zero() -> None:
    """D15: the Agents page renders NULL as an em dash and never as $0.00, which
    only works if the two states stay distinguishable all the way to the wire."""
    assert _agent_run(None).model_dump(mode="json")["cost_usd"] is None
    assert _agent_run(Decimal("0")).model_dump(mode="json")["cost_usd"] == "0"


def test_a_sub_cent_cost_does_not_round_to_zero() -> None:
    """Serialized as a string, not a float. A float would round a real Bedrock
    call toward zero and report a paid provider as free."""
    serialized = _agent_run(Decimal("0.00001234")).model_dump(mode="json")["cost_usd"]

    assert serialized == "0.00001234"
    assert isinstance(serialized, str)
