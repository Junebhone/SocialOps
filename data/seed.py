"""Seed the database with two brands, their accounts, and their posts.

    make seed

Idempotent by design. `make seed` gets run twice during a demo more often than
anyone plans, and posts carry UNIQUE(account_id, external_id) precisely so the
second run is a no-op rather than a duplicate. Comments are NOT seeded here:
they arrive through `make replay`, which is the path the queue and the
orchestrator actually exercise.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from brands import BRANDS  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db import create_engine_and_sessionmaker  # noqa: E402
from app.models import Brand, PlatformAccount, Post  # noqa: E402

FIRST_POSTED_AT = datetime(2026, 7, 1, 10, 0, tzinfo=UTC)


async def seed() -> None:
    engine, session_factory = create_engine_and_sessionmaker()
    created = {"brands": 0, "accounts": 0, "posts": 0}

    async with session_factory() as session:
        for brand_index, spec in enumerate(BRANDS):
            brand = (
                await session.execute(select(Brand).where(Brand.name == spec["name"]))
            ).scalar_one_or_none()

            if brand is None:
                brand = Brand(
                    name=spec["name"],
                    voice_guidelines=spec["voice_guidelines"],
                    brand_rules_json=spec["rules"],
                )
                session.add(brand)
                await session.flush()
                created["brands"] += 1

            for account_spec in spec["accounts"]:
                account = (
                    await session.execute(
                        # Keyed on platform TOO: brands routinely use the same
                        # handle on Instagram and X, and those are two accounts.
                        select(PlatformAccount).where(
                            PlatformAccount.brand_id == brand.id,
                            PlatformAccount.platform == account_spec["platform"],
                            PlatformAccount.handle == account_spec["handle"],
                        )
                    )
                ).scalar_one_or_none()

                if account is None:
                    account = PlatformAccount(
                        brand_id=brand.id,
                        platform=account_spec["platform"],
                        handle=account_spec["handle"],
                    )
                    session.add(account)
                    await session.flush()
                    created["accounts"] += 1

                # Posts hang off the brand's first account — the one the comment
                # dumps reference by handle.
                if account_spec is not spec["accounts"][0]:
                    continue

                for post_index, (text, likes, comments, shares) in enumerate(spec["posts"]):
                    external_id = f"post-{brand_index}-{post_index}"
                    exists = (
                        await session.execute(
                            select(Post).where(
                                Post.account_id == account.id, Post.external_id == external_id
                            )
                        )
                    ).scalar_one_or_none()
                    if exists is not None:
                        continue

                    session.add(
                        Post(
                            account_id=account.id,
                            external_id=external_id,
                            text=text,
                            posted_at=FIRST_POSTED_AT + timedelta(days=post_index * 3),
                            metrics_json={
                                "likes": likes,
                                "comments": comments,
                                "shares": shares,
                                "impressions": likes * 11,
                            },
                        )
                    )
                    created["posts"] += 1

        await session.commit()

    await engine.dispose()

    print(
        f"seeded: {created['brands']} brands, "
        f"{created['accounts']} accounts, {created['posts']} posts "
        f"({'nothing new — already seeded' if not any(created.values()) else 'inserted'})"
    )


if __name__ == "__main__":
    asyncio.run(seed())
