"""Score the triage agent against the hand-labeled set (D5).

    make eval

This is the only evidence that the small `fast` model did not cost us accuracy
when D4 split the tiers, and the only thing that catches a prompt edit quietly
destroying it. It is also what makes ADR-0002's claim — that switching to
Bedrock is an env change plus an eval run — something you can actually perform
rather than assert.

It reports the `hard` subset separately. 19 of the 50 comments are marked hard
(sarcasm, emoji-only, four non-English, praise wrapped around a question), and
an overall score that hides them would flatter the small model exactly where it
fails.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from worker.agents.schemas import TriageInput, TriageOutput
from worker.agents.triage import TriageAgent
from worker.config import Tier, get_settings
from worker.llm import Usage

EVAL_DOC = Path("/app/docs/eval.md")


@dataclass
class Scores:
    total: int
    category_correct: int
    needs_reply_correct: int
    sentiment_errors: list[int]
    latencies: list[int]
    costs: list[float]
    hard_total: int
    hard_correct: int
    errors: list[str]
    misses: list[tuple[str, str, str]]

    @property
    def category_accuracy(self) -> float:
        return self.category_correct / self.total if self.total else 0.0

    @property
    def needs_reply_accuracy(self) -> float:
        return self.needs_reply_correct / self.total if self.total else 0.0

    @property
    def sentiment_mae(self) -> float:
        return statistics.mean(self.sentiment_errors) if self.sentiment_errors else 0.0

    @property
    def p50_latency_ms(self) -> float:
        return statistics.median(self.latencies) if self.latencies else 0.0

    @property
    def cost_per_100(self) -> float:
        """Scaled from what the run actually spent, not from a price list."""
        if not self.costs:
            return 0.0
        return sum(self.costs) / len(self.costs) * 100


async def score(rows: list[dict[str, Any]], tier: Tier) -> Scores:
    agent = TriageAgent()
    # The tier is normally a class attribute (D6). Overriding it here is what
    # lets one command compare `fast` against `standard` on identical inputs,
    # which is the comparison D4's promotion rule is written against.
    agent.tier = tier  # type: ignore[misc]

    result = Scores(len(rows), 0, 0, [], [], [], 0, 0, [], [])

    for index, row in enumerate(rows, 1):
        is_hard = bool(row.get("hard"))
        result.hard_total += is_hard
        try:
            output, usage = await agent.run_with_usage(TriageInput(comment_text=row["text"]))
        except Exception as exc:  # noqa: BLE001 - a failure is a data point, not a crash
            result.errors.append(f"{row['external_id']}: {type(exc).__name__}")
            continue

        _tally(result, row, output, usage, is_hard)
        print(f"\r  scored {index}/{len(rows)}", end="", file=sys.stderr, flush=True)

    print("", file=sys.stderr)
    return result


def _tally(
    result: Scores, row: dict[str, Any], output: TriageOutput, usage: Usage, is_hard: bool
) -> None:
    correct = output.category == row["category"]
    result.category_correct += correct
    result.hard_correct += correct and is_hard
    result.needs_reply_correct += output.needs_reply == row["needs_reply"]
    result.sentiment_errors.append(abs(output.sentiment - row["sentiment"]))
    result.latencies.append(usage.latency_ms)
    # A NULL cost means unpriceable, not free (D15) — excluded rather than
    # counted as zero, so an unpriced provider cannot look free.
    if usage.cost_usd is not None:
        result.costs.append(float(usage.cost_usd))
    if not correct:
        result.misses.append((row["text"], output.category, row["category"]))


def markdown_row(scores: Scores, tier: Tier) -> str:
    settings = get_settings()
    today = datetime.now(UTC).date().isoformat()
    cost = f"${scores.cost_per_100:.4f}".rstrip("0").rstrip(".") if scores.costs else "—"
    return (
        f"| {today} | {settings.llm_provider} | {tier} | {settings.model_for_tier(tier)} "
        f"| {scores.category_accuracy:.0%} | {scores.needs_reply_accuracy:.0%} "
        f"| {scores.sentiment_mae:.2f} | {scores.p50_latency_ms:.0f} | {cost} |"
    )


def report(scores: Scores, tier: Tier) -> str:
    settings = get_settings()
    hard = (
        f"{scores.hard_correct}/{scores.hard_total} "
        f"({scores.hard_correct / scores.hard_total:.0%})"
        if scores.hard_total
        else "n/a"
    )
    lines = [
        f"tier {tier} -> {settings.model_for_tier(tier)} via {settings.llm_provider}",
        f"  category accuracy     {scores.category_correct}/{scores.total} "
        f"({scores.category_accuracy:.0%})",
        f"  needs_reply accuracy  {scores.needs_reply_correct}/{scores.total} "
        f"({scores.needs_reply_accuracy:.0%})",
        f"  sentiment MAE         {scores.sentiment_mae:.2f}",
        f"  hard cases            {hard}",
        f"  p50 latency           {scores.p50_latency_ms:.0f}ms",
        f"  cost / 100 comments   ${scores.cost_per_100:.4f}"
        if scores.costs
        else "  cost / 100 comments   — (unpriceable)",
    ]
    if scores.errors:
        lines.append(f"  errors                {len(scores.errors)}: {scores.errors[:3]}")
    if scores.misses:
        lines.append("\n  misclassified:")
        lines += [
            f"    got {got:<10} want {want:<10} | {text[:52]}"
            for text, got, want in scores.misses
        ]
    return "\n".join(lines)


def append_to_eval_doc(row: str) -> bool:
    """Append the row under the existing table, keeping the prose below it."""
    if not EVAL_DOC.is_file():
        return False

    lines = EVAL_DOC.read_text().split("\n")
    last_row = max(
        (i for i, line in enumerate(lines) if line.startswith("| ") and "|" in line[2:]),
        default=None,
    )
    if last_row is None:
        return False

    lines.insert(last_row + 1, row)
    EVAL_DOC.write_text("\n".join(lines))
    return True


async def main() -> int:
    parser = argparse.ArgumentParser(description="Score triage against data/eval.json")
    parser.add_argument("path", nargs="?", default="data/eval.json")
    parser.add_argument(
        "--tier",
        default="fast",
        choices=["fast", "standard", "vision"],
        help="Which tier to score. Use --tier standard for the D4 comparison.",
    )
    parser.add_argument(
        "--write", action="store_true", help="Append the result row to docs/eval.md"
    )
    args = parser.parse_args()

    rows = json.loads(Path(args.path).read_text())
    print(f"scoring {len(rows)} labeled comments on the {args.tier} tier", file=sys.stderr)

    scores = await score(rows, args.tier)
    print(report(scores, args.tier))
    print(f"\n{markdown_row(scores, args.tier)}")

    if args.write and append_to_eval_doc(markdown_row(scores, args.tier)):
        print(f"\nappended to {EVAL_DOC}", file=sys.stderr)

    # D4's promotion rule needs a number, so make the gap the exit signal:
    # a category accuracy below 90% is the "more than a few points behind" case.
    return 0 if scores.category_accuracy >= 0.90 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
