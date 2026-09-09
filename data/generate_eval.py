"""Write data/eval.json from the hand-labeled source.

    docker compose exec api python /app/data/generate_eval.py

Keeping the labels in a Python module and generating the JSON means the reasoning
for a hard case lives next to its label, where the next person to argue with a
score will actually read it. eval.json stays the machine-readable artifact that
`make eval` consumes.
"""

import collections
import json
from pathlib import Path

from eval_source import EVAL

HERE = Path(__file__).parent

CATEGORIES = {"question", "complaint", "praise", "spam", "other"}


def main() -> None:
    assert len(EVAL) == 50, f"the eval set must be exactly 50 comments, found {len(EVAL)}"

    rows = []
    for index, item in enumerate(EVAL):
        assert item["category"] in CATEGORIES, item
        assert item["sentiment"] in (-2, -1, 0, 1, 2), item
        assert isinstance(item["needs_reply"], bool), item
        # Spam is never owed a reply; this is a labeling rule, so enforce it.
        if item["category"] == "spam":
            assert item["needs_reply"] is False, item

        rows.append(
            {
                "external_id": f"eval-{index:03d}",
                "text": item["text"],
                "category": item["category"],
                "sentiment": item["sentiment"],
                "needs_reply": item["needs_reply"],
                "hard": item.get("hard"),
            }
        )

    assert len({row["text"] for row in rows}) == 50, "duplicate text in the eval set"

    (HERE / "eval.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))

    by_category = collections.Counter(row["category"] for row in rows)
    hard = sum(1 for row in rows if row["hard"])
    print(f"eval.json  {len(rows)} comments, {hard} marked hard")
    for category, count in sorted(by_category.items()):
        print(f"  {category:<10} {count:>3}")


if __name__ == "__main__":
    main()
