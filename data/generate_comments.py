"""Generate the synthetic comment dumps.

Run once; the JSON it writes is committed. Regenerating with the same seed
produces byte-identical files, so a rebuild never invalidates an `external_id`
that has already been ingested.

    docker compose exec api python /app/data/generate_comments.py

Category mix follows PROMPTS.md step 2: ~40% question, 25% praise, 20%
complaint, 10% spam, 5% other. Templates are hand-written rather than
Faker-generated prose, because triage has to classify these and Faker's lorem
has no category signal — a model would be graded on noise. Faker supplies the
things that genuinely should vary: names, handles, dates, order numbers.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from faker import Faker

HERE = Path(__file__).parent

# Fixed so external_ids are stable across regenerations.
SEED = 20260909

# A comment that ingest must reject, for the DLQ (step 9). Its created_at is not
# a timestamp, so parsing fails on this row and this row only — the other 1,999
# must still process, which is the point.
MALFORMED_INDEX = 1447

QUESTIONS = [
    "Does this come in decaf?",
    "Do you ship to Canada?",
    "What's the roast date on the Guji?",
    "Is the packaging recyclable or just the box?",
    "How long does a subscription pause last?",
    "Can I change my grind after ordering?",
    "Is this suitable for sensitive skin?",
    "Does the serum have fragrance in it?",
    "What percentage niacinamide is in this?",
    "Can I use this with retinol at night?",
    "When is the SPF actually launching?",
    "Do the refill pouches fit the old bottle?",
    "Whats the difference between this and the standard one",
    "any chance of a bigger size?",
    "Do you do wholesale for cafes?",
    "Is there a student discount?",
    "how much is shipping to the UK",
    "Are the beans oily or dry roast?",
    "Do you have an ingredient list somewhere?",
    "Is my order still coming? Placed it on the {date}.",
    "Hi, can someone tell me if order {order} shipped yet?",
    "Do you restock the sampler often?",
]

PRAISE = [
    "This is genuinely the best coffee I've had all year.",
    "Third bag this month. No notes.",
    "The Guji is unreal. Thank you.",
    "Finally a brand that just tells you what's in the bottle.",
    "My skin has calmed down so much since switching.",
    "Love that you published the supplier audit. Rare.",
    "The refill pouches are such a good call.",
    "Best customer service I've dealt with, honestly.",
    "obsessed with this",
    "packaging is beautiful and it actually works",
    "Recommended you to my whole office.",
    "Been using this for six months and it's the only thing that hasn't irritated me.",
    "the decaf is better than most regular coffee",
    "You've earned a customer for life.",
]

COMPLAINTS = [
    "Order {order} arrived smashed. Two bags split open.",
    "Been waiting 11 days and no shipping update at all.",
    "This gave me a rash within two days. Really disappointed.",
    "Third time the subscription charged early. Sort it out.",
    "The grind was completely wrong, ordered filter got espresso.",
    "Support hasn't answered my email in a week.",
    "Price went up 20% with no warning to subscribers.",
    "Bottle arrived half empty. Not what I paid for.",
    "This is nothing like the sample. Really let down.",
    "I want a refund for order {order} please. This is unusable.",
    "Cancelled my subscription and was still charged.",
    "The new formula is worse. Bring back the old one.",
    "arrived stale, roast date was 6 weeks ago",
    "You've ignored three messages now.",
]

SPAM = [
    "Make $5000/week from home! Click my bio 💰💰",
    "FOLLOW ME FOR FREE GIVEAWAYS 🎁🎁🎁",
    "check out my page for cheap designer bags",
    "Grow your followers fast — link in bio",
    "🔥🔥 DM me for promo 🔥🔥",
    "Best crypto signals, 300% returns guaranteed",
    "free iphone winner click here",
    "Buy real followers cheap!!! dm now",
]

OTHER = [
    "🔥🔥🔥",
    "😍",
    "第一次买，包装很好看。",
    "Muy buen café, gracias.",
    "Ist das vegan?",
    "tagging @{handle} you need to see this",
    "commenting so I can find this later",
    "👀",
    "lol",
    "Bonjour, est-ce que vous livrez en France ?",
    "❤️❤️",
    "saving this one",
]

# Weighted to the mix in PROMPTS.md step 2.
MIX: list[tuple[str, list[str], float]] = [
    ("question", QUESTIONS, 0.40),
    ("praise", PRAISE, 0.25),
    ("complaint", COMPLAINTS, 0.20),
    ("spam", SPAM, 0.10),
    ("other", OTHER, 0.05),
]


def _render(template: str, fake: Faker, rng: random.Random) -> str:
    """Fill the placeholders Faker is genuinely useful for."""
    return template.format(
        order=f"RR-{rng.randint(10000, 99999)}",
        date=fake.date_this_year().isoformat(),
        handle=fake.user_name(),
    )


def _category_plan(count: int, rng: random.Random) -> list[str]:
    """Exact quotas, then shuffled.

    Weighted random sampling drifts on small n — at 300 comments it landed 5
    points over on questions, which would quietly bias the eval set and the
    demo's category chart. Quotas make the mix a property of the file rather
    than of the seed.
    """
    plan: list[str] = []
    for category, _templates, share in MIX:
        plan.extend([category] * round(count * share))
    # Rounding can leave the plan a row short or long.
    while len(plan) < count:
        plan.append(MIX[0][0])
    del plan[count:]
    rng.shuffle(plan)
    return plan


def _comment(
    index: int,
    prefix: str,
    post_external_id: str,
    account_handle: str,
    category: str,
    fake: Faker,
    rng: random.Random,
    base_time: datetime,
) -> dict[str, Any]:
    templates = next(row[1] for row in MIX if row[0] == category)

    return {
        # Stable and unique: this is what makes replay idempotent (D9).
        "external_id": f"{prefix}-{index:05d}",
        "post_external_id": post_external_id,
        "account_handle": account_handle,
        "author": f"@{fake.user_name()}",
        "text": _render(rng.choice(templates), fake, rng),
        # A real platform timestamp. comments.created_at has no server default,
        # so ingest depends on this field being present on every row.
        "created_at": (base_time + timedelta(minutes=index * 7)).isoformat(),
    }


def generate(count: int, prefix: str, targets: list[tuple[str, str]]) -> list[dict[str, Any]]:
    fake = Faker()
    Faker.seed(SEED)
    rng = random.Random(SEED)
    base_time = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)

    plan = _category_plan(count, rng)
    comments = []
    for index in range(count):
        post_external_id, account_handle = targets[index % len(targets)]
        comments.append(
            _comment(
                index, prefix, post_external_id, account_handle, plan[index], fake, rng, base_time
            )
        )
    return comments


def main() -> None:
    from brands import BRANDS

    # The small dump spreads across both brands so the Inbox's brand selector
    # has something to switch between during the demo.
    spread = [
        (f"post-{brand_index}-{post_index}", brand["accounts"][0]["handle"])
        for brand_index, brand in enumerate(BRANDS)
        for post_index in range(len(brand["posts"]))
    ]
    small = generate(300, "cs", spread)
    (HERE / "comments_small.json").write_text(json.dumps(small, indent=2, ensure_ascii=False))

    # The viral dump is one post going off, which is the scenario the whole
    # queue story is about.
    viral_target = [("post-0-9", BRANDS[0]["accounts"][0]["handle"])]
    viral = generate(2000, "vp", viral_target)

    # Exactly one row the parser must reject (step 9's DLQ evidence).
    viral[MALFORMED_INDEX]["created_at"] = "not-a-timestamp"
    viral[MALFORMED_INDEX]["text"] = "This row is deliberately malformed: created_at is not a date."

    (HERE / "viral_post_dump.json").write_text(json.dumps(viral, indent=2, ensure_ascii=False))

    print(f"comments_small.json    {len(small):>5} comments")
    print(
        f"viral_post_dump.json   {len(viral):>5} comments "
        f"(1 malformed at index {MALFORMED_INDEX})"
    )


if __name__ == "__main__":
    main()
