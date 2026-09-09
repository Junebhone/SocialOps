"""The synthetic data files are inputs to everything downstream.

A silently malformed dump would surface as a confusing failure two steps later
(a NOT NULL violation mid-replay, or an eval score that means nothing), so the
files are checked here rather than trusted.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

DATA = Path("/app/data")
CATEGORIES = {"question", "complaint", "praise", "spam", "other"}
DUMPS = ["comments_small.json", "viral_post_dump.json"]
EXPECTED_ROWS = {"comments_small.json": 300, "viral_post_dump.json": 2000}
# Written by generate_comments.py; the one row ingest must reject (step 9).
MALFORMED_EXTERNAL_ID = "vp-01447"


def _load(name: str) -> list[dict[str, object]]:
    return json.loads((DATA / name).read_text())


@pytest.mark.parametrize("name", DUMPS)
def test_the_dump_has_the_expected_row_count(name: str) -> None:
    assert len(_load(name)) == EXPECTED_ROWS[name]


@pytest.mark.parametrize("name", DUMPS)
def test_every_external_id_is_unique(name: str) -> None:
    """D9: replay idempotency is only as good as the ids being distinct."""
    rows = _load(name)

    assert len({row["external_id"] for row in rows}) == len(rows)


@pytest.mark.parametrize("name", DUMPS)
def test_every_row_carries_the_fields_ingest_needs(name: str) -> None:
    """comments.created_at has no server default, so a row missing it would fail
    on insert rather than being quietly defaulted."""
    for row in _load(name):
        for field in ("external_id", "post_external_id", "account_handle", "author", "text"):
            assert isinstance(row[field], str) and row[field], (name, row)
        assert "created_at" in row


def test_exactly_one_row_is_malformed() -> None:
    """Step 9 needs something to land in the DLQ, and needs the other 1,999 to
    survive — so this must be one row, not a class of rows."""
    rows = _load("viral_post_dump.json")

    unparseable = []
    for row in rows:
        try:
            datetime.fromisoformat(str(row["created_at"]))
        except ValueError:
            unparseable.append(row["external_id"])

    assert unparseable == [MALFORMED_EXTERNAL_ID]


def test_the_small_dump_is_entirely_parseable() -> None:
    """`make replay` is the demo path; nothing in it should fail."""
    for row in _load("comments_small.json"):
        datetime.fromisoformat(str(row["created_at"]))


def test_the_dumps_include_emoji_and_non_english() -> None:
    """Step 2 requires both, and they are what break a naive ingest."""
    texts = [str(row["text"]) for row in _load("comments_small.json")]

    assert any(any(ord(char) > 0x2000 for char in text) for text in texts)
    assert any(any("一" <= char <= "鿿" for char in text) for text in texts)


def test_the_eval_set_is_fifty_labeled_comments() -> None:
    """D5: this file is the only evidence that the 2B triage model is good
    enough to keep on the fast tier."""
    rows = _load("eval.json")

    assert len(rows) == 50
    for row in rows:
        assert row["category"] in CATEGORIES, row
        assert row["sentiment"] in (-2, -1, 0, 1, 2), row
        assert isinstance(row["needs_reply"], bool), row


def test_the_eval_set_never_asks_for_a_reply_to_spam() -> None:
    """A labeling rule, not a model expectation. If it is violated here, the
    needs_reply score measures the labeler's inconsistency."""
    for row in _load("eval.json"):
        if row["category"] == "spam":
            assert row["needs_reply"] is False, row


def test_the_eval_set_covers_every_category_and_both_sentiment_extremes() -> None:
    """A set with no hostile comments and no delighted ones cannot show that
    sentiment MAE is meaningful."""
    rows = _load("eval.json")

    assert {row["category"] for row in rows} == CATEGORIES
    sentiments = {row["sentiment"] for row in rows}
    assert -2 in sentiments and 2 in sentiments


def test_the_eval_set_contains_hard_cases() -> None:
    """Sarcasm, emoji-only and non-English are where a 2B model actually fails.
    Without them the score would be flattering and useless for the tier
    decision in D4."""
    hard = [row for row in _load("eval.json") if row.get("hard")]

    assert len(hard) >= 12


def test_five_sample_images_exist() -> None:
    images = sorted((DATA / "sample_images").glob("*.png"))

    assert len(images) == 5
    assert all(image.stat().st_size > 1000 for image in images)


def test_brand_rules_match_the_d16_shape() -> None:
    """One column, three consumers. A brand missing a key breaks whichever agent
    reads it, two steps later."""
    import sys

    sys.path.insert(0, str(DATA))
    from brands import BRANDS

    assert len(BRANDS) == 2
    for brand in BRANDS:
        rules = brand["rules"]
        assert set(rules) == {
            "prohibited_content",
            "required_elements",
            "tone",
            "max_hashtags",
        }
        assert set(rules["tone"]) == {"avoid_words", "prefer_words"}
        assert isinstance(rules["max_hashtags"], int)
        assert len(brand["accounts"]) == 3
        assert len(brand["posts"]) == 10
