"""Row builders for tests.

Deliberately plain functions rather than a factory library: the point is that a
test reads as a specification, and `await a_comment(session, external_id="c-1")`
says more than a fixture name would.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentRun, Asset, Brand, Comment, ContentDraft, PlatformAccount, Post

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


async def an_asset(
    session: AsyncSession,
    brand: Brand | None = None,
    filename: str = "bag.png",
    analysis: dict[str, Any] | None = None,
) -> Asset:
    """An uploaded photo. `analysis=None` is the still-being-analysed card."""
    brand = brand or await a_brand(session)
    asset = Asset(
        brand_id=brand.id,
        filename=filename,
        storage_key=f"brands/{brand.id}/{filename}",
        mime="image/png",
        analysis_json=analysis,
    )
    session.add(asset)
    await session.commit()
    await session.refresh(asset)
    return asset


ANALYSIS: dict[str, Any] = {
    "description": "A kraft coffee bag on a wooden table.",
    "detected_text": ["RIDGELINE ROASTERS"],
    "brand_check": {"passes": True, "issues": []},
}


async def content_drafts(session: AsyncSession, asset: Asset) -> list[ContentDraft]:
    """The three captions the content agent writes for one asset."""
    drafts = [
        ContentDraft(
            asset_id=asset.id,
            platform=platform,
            text=f"A caption for {platform}.",
            hashtags_json=["coffee"],
            status="pending",
        )
        for platform in ("x", "instagram", "linkedin")
    ]
    session.add_all(drafts)
    await session.commit()
    for draft in drafts:
        await session.refresh(draft)
    return drafts


async def agent_run(
    session: AsyncSession,
    brand: Brand,
    agent: str = "triage",
    *,
    entity_type: str = "comment",
    entity_id: int = 1,
    latency_ms: int = 100,
    cost_usd: Decimal | None = Decimal(0),
    status: str = "ok",
    input_tokens: int = 10,
    output_tokens: int = 5,
    error: str | None = None,
) -> AgentRun:
    """One audit row. `cost_usd=None` is D15's third state — unpriceable."""
    run = AgentRun(
        agent=agent,
        entity_type=entity_type,
        entity_id=entity_id,
        brand_id=brand.id,
        output_json={} if status == "ok" else None,
        status=status,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        error=error,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run
