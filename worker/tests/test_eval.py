"""The eval runner (D5).

Scored against a scripted model, never a real one — the point of these tests is
the scoring arithmetic and the report, not the model's accuracy.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from worker import eval as eval_module
from worker import llm
from worker.eval import Scores, append_to_eval_doc, markdown_row, report, score

ROWS = [
    {"external_id": "e-0", "text": "Does this come in decaf?", "category": "question",
     "sentiment": 0, "needs_reply": True, "hard": None},
    {"external_id": "e-1", "text": "🔥🔥🔥", "category": "praise",
     "sentiment": 2, "needs_reply": False, "hard": "emoji-only"},
]


@pytest.fixture
def always_question(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A model that answers 'question' to everything: right once, wrong once."""
    monkeypatch.setattr(llm, "PROMPTS_DIR", tmp_path)
    (tmp_path / "triage.md").write_text("Classify: {{comment_text}}")

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(
            parts=[TextPart('{"category":"question","sentiment":0,'
                            '"needs_reply":true,"urgency":"low"}')]
        )

    monkeypatch.setattr(llm, "_build_model", lambda settings, tier: FunctionModel(respond))


async def test_scoring_counts_each_dimension(always_question: None) -> None:
    scores = await score(ROWS, "fast")

    assert scores.total == 2
    assert scores.category_accuracy == 0.5
    assert scores.needs_reply_accuracy == 0.5
    # sentiment: |0-0| and |0-2| -> mean 1.0
    assert scores.sentiment_mae == 1.0


async def test_hard_cases_are_scored_separately(always_question: None) -> None:
    """An overall number that hides the hard subset would flatter the small
    model exactly where it fails, which is where D4's decision is made."""
    scores = await score(ROWS, "fast")

    assert scores.hard_total == 1
    assert scores.hard_correct == 0


async def test_misclassifications_are_reported(always_question: None) -> None:
    """A score with no examples is unactionable — you cannot fix a prompt from
    a percentage."""
    scores = await score(ROWS, "fast")

    assert scores.misses == [("🔥🔥🔥", "question", "praise")]
    assert "got question" in report(scores, "fast")


async def test_ollama_cost_is_reported_as_zero_not_missing(always_question: None) -> None:
    """D15: Ollama is genuinely free, so it is 0. A NULL would mean unpriceable
    and is excluded from the average instead of being counted as free."""
    scores = await score(ROWS, "fast")

    assert scores.cost_per_100 == 0.0
    assert len(scores.costs) == 2


def _scores() -> Scores:
    return Scores(
        total=50, category_correct=46, needs_reply_correct=46,
        sentiment_errors=[1] * 50, latencies=[900] * 50, costs=[0.0] * 50,
        hard_total=19, hard_correct=17, errors=[], misses=[],
    )


def test_the_markdown_row_matches_the_eval_table_columns() -> None:
    """docs/eval.md is a table; a row with the wrong column count silently
    corrupts it."""
    row = markdown_row(_scores(), "fast")

    assert row.count("|") == 10
    assert "92%" in row
    assert "qwen3.5:2b" in row


def test_the_row_is_appended_below_the_existing_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Appended under the last row, not at the end of the file — the prose that
    explains the table has to stay below it."""
    doc = tmp_path / "eval.md"
    doc.write_text("# Log\n\n| Date | Provider |\n|---|---|\n| old | ollama |\n\n## Why\n\nprose\n")
    monkeypatch.setattr(eval_module, "EVAL_DOC", doc)

    assert append_to_eval_doc("| new | ollama |") is True

    lines = doc.read_text().split("\n")
    assert lines.index("| new | ollama |") == lines.index("| old | ollama |") + 1
    assert doc.read_text().endswith("prose\n")


def test_appending_is_skipped_when_the_doc_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_module, "EVAL_DOC", tmp_path / "nope.md")

    assert append_to_eval_doc("| x |") is False
