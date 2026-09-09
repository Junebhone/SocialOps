"""Constraints that the database enforces, proven against the real database.

These are the guarantees the rest of the system is allowed to assume. Each one
is enforced in Postgres rather than in application code, so no future endpoint
can bypass it by forgetting a check.
"""

from decimal import Decimal
from typing import Any, cast

import pytest
from sqlalchemy import CursorResult, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentRun, Comment, ReplyDraft
from tests.factories import NOW, a_post, an_account, build_comment


async def test_comments_unique_constraint_rejects_a_duplicate(session: AsyncSession) -> None:
    """D9: replaying the same dump twice must not re-insert or re-spend an LLM call."""
    post = await a_post(session)
    session.add(build_comment(post, external_id="c-1"))
    await session.commit()

    session.add(build_comment(post, external_id="c-1", text="the same comment again"))
    with pytest.raises(IntegrityError) as exc:
        await session.commit()

    assert "uq_comments_post_id_external_id" in str(exc.value)
    await session.rollback()


async def test_the_same_external_id_is_allowed_on_a_different_post(session: AsyncSession) -> None:
    """The constraint is composite. Narrowed to external_id alone it would drop
    legitimate comments that happen to share an id across posts."""
    account = await an_account(session)
    first = await a_post(session, account=account, external_id="p-1")
    second = await a_post(session, account=account, external_id="p-2")

    session.add(build_comment(first, external_id="shared"))
    session.add(build_comment(second, external_id="shared"))
    await session.commit()

    count = len((await session.execute(select(Comment))).scalars().all())
    assert count == 2


async def test_external_id_cannot_be_null(session: AsyncSession) -> None:
    """Postgres treats NULLs as distinct in a unique index, so a nullable
    external_id would silently turn D9's constraint into a no-op."""
    post = await a_post(session)
    comment = build_comment(post)
    # Deliberately violating the Python type: the point is that the DATABASE
    # rejects this, not that mypy does.
    comment.external_id = None  # type: ignore[assignment]
    session.add(comment)

    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


async def test_on_conflict_do_nothing_is_idempotent(session: AsyncSession) -> None:
    """The exact statement step 4's POST /ingest/comments will use.

    This is what makes its {inserted, skipped} response correct rather than
    aspirational.
    """
    post = await a_post(session)
    values = {
        "post_id": post.id,
        "external_id": "c-1",
        "author": "@rae",
        "text": "hello",
        "created_at": NOW,
    }
    stmt = insert(Comment).values(values).on_conflict_do_nothing(
        index_elements=["post_id", "external_id"]
    )

    # rowcount is a CursorResult attribute; session.execute is typed as Result.
    first = cast("CursorResult[Any]", await session.execute(stmt))
    second = cast("CursorResult[Any]", await session.execute(stmt))
    await session.commit()

    assert first.rowcount == 1
    assert second.rowcount == 0
    assert len((await session.execute(select(Comment))).scalars().all()) == 1


@pytest.mark.parametrize("sentiment", [-3, 3])
async def test_sentiment_outside_minus_two_to_two_is_rejected(
    session: AsyncSession, sentiment: int
) -> None:
    """D8: enforced in the database so a miscalibrated model cannot poison eval."""
    post = await a_post(session)
    session.add(build_comment(post, sentiment=sentiment))

    with pytest.raises(IntegrityError) as exc:
        await session.commit()

    assert "ck_comments_sentiment_range" in str(exc.value)
    await session.rollback()


@pytest.mark.parametrize("sentiment", [-2, -1, 0, 1, 2])
async def test_every_sentiment_bucket_is_accepted(
    session: AsyncSession, sentiment: int
) -> None:
    post = await a_post(session)
    session.add(build_comment(post, sentiment=sentiment))
    await session.commit()


async def test_a_comment_inserts_before_triage_has_run(session: AsyncSession) -> None:
    """Ingest writes the row; triage fills in the four outputs later."""
    post = await a_post(session)
    session.add(build_comment(post))
    await session.commit()

    comment = (await session.execute(select(Comment))).scalar_one()
    assert comment.category is None
    assert comment.sentiment is None
    assert comment.needs_reply is None
    assert comment.urgency is None
    assert comment.status == "new"


async def test_an_unknown_category_is_rejected(session: AsyncSession) -> None:
    """The triage contract, enforced where it cannot be bypassed."""
    post = await a_post(session)
    session.add(build_comment(post, category="rant"))

    with pytest.raises(IntegrityError) as exc:
        await session.commit()

    assert "ck_comments_category_allowed" in str(exc.value)
    await session.rollback()


async def test_reply_draft_status_rejects_edited(session: AsyncSession) -> None:
    """D3 deleted the 'edited' status: a non-null final_text is the edit record.

    This test is what stops it being quietly reintroduced.
    """
    post = await a_post(session)
    comment = build_comment(post)
    session.add(comment)
    await session.commit()

    session.add(ReplyDraft(comment_id=comment.id, text="draft", status="edited"))
    with pytest.raises(IntegrityError) as exc:
        await session.commit()

    assert "ck_reply_drafts_status_allowed" in str(exc.value)
    await session.rollback()


async def test_cost_usd_keeps_null_zero_and_a_sub_cent_value_distinct(
    session: AsyncSession,
) -> None:
    """D15's three states: free (Ollama), priced, and unpriceable.

    Numeric(12, 8) so a real sub-cent Bedrock call does not round to zero and
    report a paid provider as free.
    """
    account = await an_account(session)
    for index, cost in enumerate([None, Decimal("0"), Decimal("0.00001234")]):
        session.add(
            AgentRun(
                agent="triage",
                entity_type="comment",
                entity_id=index + 1,
                brand_id=account.brand_id,
                status="ok",
                input_tokens=10,
                output_tokens=5,
                cost_usd=cost,
                latency_ms=120,
            )
        )
    await session.commit()

    runs = (await session.execute(select(AgentRun).order_by(AgentRun.id))).scalars().all()
    assert [run.cost_usd for run in runs] == [None, Decimal("0"), Decimal("0.00001234")]


async def test_entity_type_is_not_constrained_at_the_database(session: AsyncSession) -> None:
    """Documents an intentional ABSENCE.

    D7's stated virtue is that a new agent input type needs no migration. A CHECK
    on entity_type would reintroduce exactly the migration it exists to avoid, so
    'video' must insert cleanly even though no agent produces it yet.
    """
    account = await an_account(session)
    session.add(
        AgentRun(
            agent="media",
            entity_type="video",
            entity_id=1,
            brand_id=account.brand_id,
            status="ok",
            input_tokens=1,
            output_tokens=1,
            cost_usd=None,
            latency_ms=1,
        )
    )
    await session.commit()

    assert (await session.execute(select(AgentRun))).scalar_one().entity_type == "video"


async def test_comment_text_accepts_ten_thousand_characters(session: AsyncSession) -> None:
    """Proves the column is Text, not a bounded VARCHAR."""
    post = await a_post(session)
    session.add(build_comment(post, text="x" * 10_000))
    await session.commit()

    assert len((await session.execute(select(Comment))).scalar_one().text) == 10_000


async def test_comment_text_round_trips_emoji_and_non_english(session: AsyncSession) -> None:
    """The seed data's stated mix includes both; ingest must not fail on them."""
    post = await a_post(session)
    session.add(build_comment(post, external_id="c-emoji", text="🔥🔥🔥"))
    session.add(build_comment(post, external_id="c-ja", text="これは美味しいですね"))
    await session.commit()

    texts = {c.text for c in (await session.execute(select(Comment))).scalars().all()}
    assert texts == {"🔥🔥🔥", "これは美味しいですね"}


async def test_deleting_a_brand_cascades_through_the_whole_chain(session: AsyncSession) -> None:
    """Five levels deep. No orphans survive a brand delete."""
    post = await a_post(session)
    comment = build_comment(post)
    session.add(comment)
    await session.commit()
    session.add(ReplyDraft(comment_id=comment.id, text="draft"))
    await session.commit()

    account = await session.get(type(post), post.id)
    assert account is not None
    brand_id = (await session.execute(select(Comment))).scalar_one().post_id

    from app.models import Brand, PlatformAccount, Post

    brand = (await session.execute(select(Brand))).scalar_one()
    await session.delete(brand)
    await session.commit()

    assert (await session.execute(select(PlatformAccount))).scalars().all() == []
    assert (await session.execute(select(Post))).scalars().all() == []
    assert (await session.execute(select(Comment))).scalars().all() == []
    assert (await session.execute(select(ReplyDraft))).scalars().all() == []
    assert brand_id is not None


async def test_deleting_an_agent_run_nulls_the_draft_reference(session: AsyncSession) -> None:
    """Provenance, not ownership: purging an audit row must never delete a draft
    a human approved."""
    post = await a_post(session)
    comment = build_comment(post)
    session.add(comment)
    await session.commit()

    account = await an_account(session, handle="@second")
    run = AgentRun(
        agent="response",
        entity_type="comment",
        entity_id=comment.id,
        brand_id=account.brand_id,
        status="ok",
        input_tokens=1,
        output_tokens=1,
        cost_usd=None,
        latency_ms=1,
    )
    session.add(run)
    await session.commit()

    draft = ReplyDraft(comment_id=comment.id, text="draft", agent_run_id=run.id)
    session.add(draft)
    await session.commit()

    await session.delete(run)
    await session.commit()

    # expire_on_commit=False means the identity map still holds the pre-delete
    # object; the assertion is about what Postgres did, so force a reload.
    session.expire_all()
    surviving = (await session.execute(select(ReplyDraft))).scalar_one()
    assert surviving.agent_run_id is None


async def test_timestamps_round_trip_with_a_timezone(session: AsyncSession) -> None:
    """DateTime(timezone=True), so the browser receives an offset."""
    post = await a_post(session)
    session.add(build_comment(post))
    await session.commit()

    comment = (await session.execute(select(Comment))).scalar_one()
    assert comment.created_at.tzinfo is not None
    assert comment.created_at == NOW


async def test_brand_rules_json_round_trips_the_d16_shape(session: AsyncSession) -> None:
    """One column, three consumers. Nested dicts and lists must survive JSONB."""
    from tests.factories import BRAND_RULES, a_brand

    brand = await a_brand(session)
    await session.refresh(brand)

    assert brand.brand_rules_json == BRAND_RULES
    assert brand.brand_rules_json["tone"]["avoid_words"] == ["cheap", "guys"]


async def test_posts_reject_a_duplicate_external_id_per_account(session: AsyncSession) -> None:
    """Makes `make seed` re-runnable."""
    account = await an_account(session)
    await a_post(session, account=account, external_id="p-1")

    with pytest.raises((IntegrityError, DBAPIError)):
        await a_post(session, account=account, external_id="p-1")
    await session.rollback()
