"""Row builders for tests.

Deliberately plain functions rather than a factory library: the point is that a
test reads as a specification, and `await a_comment(session, external_id="c-1")`
says more than a fixture name would.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Brand, Comment, PlatformAccount, Post

NOW = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)

# The exact shape from CLAUDE.md / D16.
BRAND_RULES: dict[str, Any] = {
    "prohibited_content": ["competitor logos", "alcohol", "unaccompanied minors"],
    "required_elements": ["product visible", "logo visible"],
    "tone": {"avoid_words": ["cheap", "guys"], "prefer_words": ["small-batch", "crafted"]},
    "max_hashtags": 5,
}


async def a_brand(session: AsyncSession, name: str = "Ridgeline Roasters") -> Brand:
    brand = Brand(name=name, voice_guidelines="Warm, plain-spoken.", brand_rules_json=BRAND_RULES)
    session.add(brand)
    await session.commit()
    await session.refresh(brand)
    return brand


async def an_account(
    session: AsyncSession, brand: Brand | None = None, handle: str = "@ridgeline"
) -> PlatformAccount:
    brand = brand or await a_brand(session)
    account = PlatformAccount(brand_id=brand.id, platform="instagram", handle=handle)
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


async def a_post(
    session: AsyncSession, account: PlatformAccount | None = None, external_id: str = "p-1"
) -> Post:
    account = account or await an_account(session)
    post = Post(
        account_id=account.id,
        external_id=external_id,
        text="New single-origin, out now.",
        posted_at=NOW,
        metrics_json={"likes": 120},
    )
    session.add(post)
    await session.commit()
    await session.refresh(post)
    return post


def build_comment(post: Post, external_id: str = "c-1", **overrides: Any) -> Comment:
    """Unsaved, so a test can control exactly when the flush happens."""
    fields: dict[str, Any] = {
        "post_id": post.id,
        "external_id": external_id,
        "author": "@rae",
        "text": "Does this come in decaf?",
        "created_at": NOW,
    }
    fields.update(overrides)
    return Comment(**fields)
