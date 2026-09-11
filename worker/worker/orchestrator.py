"""The two pipelines, as `pydantic-graph` graphs (D12).

    comment:  ingest → triage → (needs_reply ? respond : persist) → persist → end
    asset:    ingest → media  → content → persist → end

Why a graph rather than a 15-line async function: typed state passed between
steps, a shape that absorbs the asset path without reshaping, and a Mermaid
diagram generated from the definition rather than hand-drawn and left to rot
(step 10). It also translates directly into a Phase 5 Step Functions state
machine.

The asset path is where the second claim gets tested, and it held: the comment
path needed no change to make room for it. Both graphs share one state contract,
one audit writer and one idempotency rule, and differ only in their nodes.

The branch is an `if`, deliberately. Routing through a model — Pydantic AI
sub-agents, or triage calling response as a tool — would put control flow inside
a 2B model's judgement, nondeterministically and unauditably, and the nested call
would break hard rule #5's one row per invocation.

Nodes call agents and write `agent_runs`; agents touch neither the queue nor the
database (hard rule #3).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import structlog
from app.models import (
    AgentRun,
    Asset,
    Brand,
    Comment,
    ContentDraft,
    ContentIdea,
    Insight,
    PlatformAccount,
    Post,
    ReplyDraft,
)
from pydantic import BaseModel
from pydantic_graph import BaseNode, End, GraphBuilder, GraphRunContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from worker.agents.base import BaseAgent
from worker.agents.content import ContentAgent
from worker.agents.ideation import IdeationAgent
from worker.agents.insight import InsightAgent
from worker.agents.media import MediaAgent
from worker.agents.response import ResponseAgent
from worker.agents.schemas import (
    ContentInput,
    IdeationInput,
    InsightInput,
    MediaInput,
    MediaOutput,
    PlatformDraft,
    ResponseInput,
    TriageInput,
    TriageOutput,
)
from worker.agents.triage import TriageAgent
from worker.images import downscale
from worker.llm import Usage
from worker.storage import get_storage

log = structlog.get_logger()


class AuditableState(Protocol):
    """What `_record_run` needs from a graph's state.

    A Protocol rather than a base class: both states are dataclasses with
    required fields of their own, and inheriting from a base that already
    carries defaults forces every subclass field to become keyword-only for a
    reason a reader would have to reverse-engineer. Structural typing gets the
    same guarantee — mypy will not let a new graph reach `_record_run` without
    telling the audit trail what entity its runs belong to.
    """

    session: AsyncSession
    audit_factory: async_sessionmaker[AsyncSession] | None
    brand_id: int
    agents_run: list[str]

    @property
    def entity_type(self) -> str:
        """D7: `comment` or `asset`. Deliberately unconstrained at the database."""

    @property
    def entity_id(self) -> int:
        """The row this run is about, joinable back through the D7 index."""


@dataclass
class CommentState:
    """Everything the comment run needs, and everything it has learned so far."""

    comment_id: int
    session: AsyncSession
    # Used only for the failure row (see `_run_agent`), which has to outlive the
    # rollback that `session_scope` performs so arq can retry cleanly.
    audit_factory: async_sessionmaker[AsyncSession] | None = None

    # Filled by Ingest.
    brand_id: int = 0
    comment_text: str = ""
    brand_voice: str = ""
    avoid_words: str = ""

    # Filled by Triage and Respond.
    triage: TriageOutput | None = None
    reply_text: str | None = None
    reply_agent_run_id: int | None = None

    agents_run: list[str] = field(default_factory=list)

    @property
    def entity_type(self) -> str:
        return "comment"

    @property
    def entity_id(self) -> int:
        return self.comment_id


async def _record_run(
    state: AuditableState,
    agent: str,
    output: dict[str, object] | None,
    usage: Usage | None,
    status: str,
    error: str | None = None,
) -> int:
    """One `agent_runs` row per agent invocation (hard rule #5).

    Written by the node, not the agent, and always joinable back to the row that
    caused it through entity_type/entity_id (D7).

    One function for both graphs on purpose. The audit trail is the payoff for
    hard rule #5 — it is the cost dashboard and the "what did this asset cost
    end to end" query — and two copies of this would drift in exactly the field
    that makes the join work.
    """
    run = _build_run(state, agent, output, usage, status, error)
    state.session.add(run)
    await state.session.flush()
    state.agents_run.append(agent)
    return run.id


def _build_run(
    state: AuditableState,
    agent: str,
    output: dict[str, object] | None,
    usage: Usage | None,
    status: str,
    error: str | None,
) -> AgentRun:
    """One shape for the row, whichever session ends up writing it."""
    return AgentRun(
        agent=agent,
        entity_type=state.entity_type,
        entity_id=state.entity_id,
        brand_id=state.brand_id,
        output_json=output,
        status=status,
        input_tokens=usage.input_tokens if usage else 0,
        output_tokens=usage.output_tokens if usage else 0,
        # NULL rather than 0 on a failure. The call may well have spent tokens
        # before it died; we do not know how many, and "unknown" is a different
        # fact from "free" — the same distinction D15 draws for cost.
        cost_usd=usage.cost_usd if usage else None,
        latency_ms=usage.latency_ms if usage else 0,
        error=error,
    )


async def _run_agent[InputT: BaseModel, OutputT: BaseModel](
    state: AuditableState,
    name: str,
    agent: BaseAgent[InputT, OutputT],
    payload: InputT,
) -> tuple[OutputT, int]:
    """Call one agent and write its audit row, whichever way the call goes.

    Hard rule #5 says every agent *invocation* writes a row, not every
    successful one — `agent_runs.status` and `agent_runs.error` exist for
    precisely this, and "which runs failed" is one of the two questions D7
    restructured the table to answer. Before this wrapper the error path wrote
    nothing at all, so both columns were unreachable and the Agents page had a
    status filter for a value nothing could produce.

    The failure row is written on its OWN session. `session_scope` is about to
    roll the job's session back so arq can retry from a clean slate, and a row
    added to it would be discarded along with everything else — the same reason
    `_record_failure` in main.py opens its own session for the DLQ write.
    """
    try:
        output, usage = await agent.run_with_usage(payload)
    except (Exception, asyncio.CancelledError) as exc:
        # arq's `job_timeout` cancels this coroutine via `asyncio.wait_for`,
        # which raises `CancelledError` — a `BaseException` since Python 3.8,
        # so a bare `except Exception` misses it and a timeout leaves no row
        # (hard rule #5). Recording it here does not swallow the cancellation:
        # it is always re-raised below.
        await _record_failed_run(state, name, exc)
        raise

    run_id = await _record_run(state, name, output.model_dump(), usage, "ok")
    return output, run_id


async def _record_failed_run(
    state: AuditableState, agent: str, exc: Exception | asyncio.CancelledError
) -> None:
    """Persist the failure independently of the job's transaction.

    Best-effort by design: if this write itself fails, the original agent error
    is the one worth propagating, and swallowing it to report a bookkeeping
    problem would hide the actual cause from `failed_jobs`.
    """
    detail = f"{type(exc).__name__}: {exc}"[:2000]
    log.warning(
        "agent.failed",
        agent=agent,
        entity=state.entity_type,
        entity_id=state.entity_id,
        error=detail,
    )

    if state.audit_factory is None:
        # No factory: a test driving the graph directly on one session. Writing
        # there is the best available, and nothing rolls it back.
        state.session.add(_build_run(state, agent, None, None, "error", detail))
        await state.session.flush()
        state.agents_run.append(agent)
        return

    try:
        async with state.audit_factory() as session:
            session.add(_build_run(state, agent, None, None, "error", detail))
            await session.commit()
    except Exception:
        log.exception("agent.failure_not_recorded", agent=agent)
    state.agents_run.append(agent)


# A comment whose pipeline finished. Re-running it would re-spend the model
# calls and write a second draft over the first.
COMPLETED_STATUSES = frozenset({"drafted", "replied"})


@dataclass
class Ingest(BaseNode[CommentState, None, int]):
    """Load the comment and its brand context, or stop if it is already done.

    The early exit is not an optimisation, it is correctness. arq retries a
    failed job, and step 9's Retry button re-enqueues by hand — without this
    guard a job that ran once and was retried produces a second triage run and a
    second reply draft, which double-charges the model and shows the reviewer
    two drafts for one comment. Measured: an emergency requeue after a disk
    outage gave 6 comments two drafts and 10 comments two triage runs.

    Returning End here also makes the skip visible in the generated diagram
    rather than hiding it inside the node.
    """

    async def run(self, ctx: GraphRunContext[CommentState, None]) -> Triage | End[int]:
        state = ctx.state
        row = (
            await state.session.execute(
                select(Comment, Brand)
                .join(Post, Comment.post_id == Post.id)
                .join(PlatformAccount, Post.account_id == PlatformAccount.id)
                .join(Brand, PlatformAccount.brand_id == Brand.id)
                .where(Comment.id == state.comment_id)
                # Lock the comment row for the life of this transaction.
                #
                # Without it the guard below is check-then-act: two attempts at
                # the same comment can both read `new` and both go on to draft a
                # reply. Measured on a 300-comment replay — comment 242 was
                # triaged and drafted twice, `GET /comments/242` then returned
                # 500, and the Inbox listed it twice. `of=Comment` locks only
                # the comment; the brand join is read-only and must not be
                # locked, or every job in the replay would serialise behind one
                # brand row.
                .with_for_update(of=Comment)
            )
        ).first()

        if row is None:
            raise LookupError(f"comment {state.comment_id} not found")

        comment, brand = row
        if comment.status in COMPLETED_STATUSES:
            log.info(
                "comment.already_processed",
                comment_id=state.comment_id,
                status=comment.status,
            )
            return End(state.comment_id)

        state.comment_text = comment.text
        state.brand_id = brand.id
        state.brand_voice = brand.voice_guidelines
        # D16: one column, three consumers. Response reads tone.avoid_words.
        tone = brand.brand_rules_json.get("tone", {})
        state.avoid_words = ", ".join(tone.get("avoid_words", [])) or "none"

        return Triage()


@dataclass
class Triage(BaseNode[CommentState, None, int]):
    """Classify the comment, then branch on the result.

    The union return type is the branch, and it is what makes the conditional
    visible in the generated Mermaid diagram.
    """

    async def run(self, ctx: GraphRunContext[CommentState, None]) -> Respond | Persist:
        state = ctx.state
        output, _run_id = await _run_agent(
            state, "triage", TriageAgent(), TriageInput(comment_text=state.comment_text)
        )

        state.triage = output
        comment = await state.session.get(Comment, state.comment_id)
        if comment is not None:
            comment.category = output.category
            comment.sentiment = output.sentiment
            comment.needs_reply = output.needs_reply
            comment.urgency = output.urgency
            comment.status = "triaged"

        # The routing rule, in full.
        return Respond() if output.needs_reply else Persist()


@dataclass
class Respond(BaseNode[CommentState, None, int]):
    """Draft a reply. Only reached when triage asked for one."""

    async def run(self, ctx: GraphRunContext[CommentState, None]) -> Persist:
        state = ctx.state
        output, state.reply_agent_run_id = await _run_agent(
            state,
            "response",
            ResponseAgent(),
            ResponseInput(
                comment_text=state.comment_text,
                brand_voice=state.brand_voice,
                avoid_words=state.avoid_words,
            ),
        )
        state.reply_text = output.reply_text
        return Persist()


@dataclass
class Persist(BaseNode[CommentState, None, int]):
    """Write the draft and close out the run.

    Approval is not a paused graph run (D12): the draft is persisted as `pending`
    and the run ends here. A human approving it days later arrives over a separate
    HTTP request, and D3's outbox is what closes the loop.
    """

    async def run(self, ctx: GraphRunContext[CommentState, None]) -> End[int]:
        state = ctx.state
        comment = await state.session.get(Comment, state.comment_id)

        if state.reply_text is not None:
            state.session.add(
                ReplyDraft(
                    comment_id=state.comment_id,
                    text=state.reply_text,
                    agent_run_id=state.reply_agent_run_id,
                    status="pending",
                )
            )
            if comment is not None:
                comment.status = "drafted"
        elif comment is not None and comment.status == "triaged":
            # Nothing to reply to — spam, or praise that needs no answer.
            comment.status = "replied"

        log.info(
            "comment.processed",
            comment_id=state.comment_id,
            brand_id=state.brand_id,
            category=state.triage.category if state.triage else None,
            drafted=state.reply_text is not None,
            agents=state.agents_run,
        )
        return End(state.comment_id)


# ---------------------------------------------------------------------------
# The asset path: ingest → media → content → persist
# ---------------------------------------------------------------------------


@dataclass
class AssetState:
    """Everything the asset run needs, and everything it has learned so far.

    Note what is NOT here: a storage path. The node reads bytes through
    `StorageBackend` (hard rule #9), so the state carries the decoded image and
    never a filename — which is what keeps the Phase 4 move to S3 from reaching
    into the graph.
    """

    asset_id: int
    session: AsyncSession
    audit_factory: async_sessionmaker[AsyncSession] | None = None

    # Filled by IngestAsset.
    brand_id: int = 0
    image_data: bytes = b""
    image_media_type: str = ""
    # D16: one column, four consumers now. Media checks the first two; content
    # respects tone and max_hashtags.
    prohibited_content: str = ""
    required_elements: str = ""
    brand_voice: str = ""
    avoid_words: str = ""
    prefer_words: str = ""
    max_hashtags: int = 5

    # Filled by Media and Content.
    analysis: MediaOutput | None = None
    drafts: list[PlatformDraft] = field(default_factory=list)
    content_agent_run_id: int | None = None

    agents_run: list[str] = field(default_factory=list)

    @property
    def entity_type(self) -> str:
        return "asset"

    @property
    def entity_id(self) -> int:
        return self.asset_id


@dataclass
class IdeationState:
    """Everything one ideation run needs.

    No graph: a single agent call has no branching or multi-step state to pass
    between nodes, so `pydantic-graph` would buy nothing here that D12 didn't
    already reject buying for a *two*-step chain. `_run_agent` and the
    `AuditableState` protocol are the only things reused — the audit trail
    (hard rule #5) still applies to a call outside a graph.
    """

    brand_id: int
    session: AsyncSession
    audit_factory: async_sessionmaker[AsyncSession] | None = None

    agents_run: list[str] = field(default_factory=list)

    @property
    def entity_type(self) -> str:
        # D7: unconstrained at the database, same as "comment"/"asset". This
        # run is about the brand as a whole, not one comment or asset row.
        return "brand"

    @property
    def entity_id(self) -> int:
        return self.brand_id


# D31-style: a static, hand-curated JSON file, not a database table and not an
# admin UI. One consumer (`run_ideation`), same reasoning as PROMPTS_DIR in
# llm.py — resolved relative to this file, not the process's cwd.
TRENDS_PATH = Path(__file__).parent.parent / "data" / "trends.json"


def _load_trend_signals(brand_name: str) -> list[str]:
    """This brand's seeded content-angle categories, or an empty list.

    Missing file or missing brand both return empty rather than raising — a
    brand with no seeded trends yet is a data gap, not a job failure, and
    `run_ideation` renders an empty list as "none" the same way `_rule_list`
    does for an unset brand rule.
    """
    if not TRENDS_PATH.exists():
        return []
    data = json.loads(TRENDS_PATH.read_text())
    return [line for line in data.get(brand_name, []) if isinstance(line, str)]


def _rule_list(values: object) -> str:
    """Render one `brand_rules_json` list into the prompt's comma-separated form.

    "none" rather than an empty string when a brand sets no rules: an empty
    string leaves the prompt reading "Prohibited content: " with nothing after
    it, and a 9B model fills that silence by inventing rules to check against.
    """
    if isinstance(values, list) and values:
        return ", ".join(str(value) for value in values)
    return "none"


@dataclass
class IngestAsset(BaseNode[AssetState, None, int]):
    """Load the asset, its brand rules and its bytes — or stop if it is done.

    The same early exit as the comment path, for the same reason: arq retries,
    and step 9's Retry button re-enqueues by hand. Without it a retried asset
    pays for a vision call and a drafting call again and shows the reviewer six
    platform drafts for one photo.

    `analysis_json` is the marker rather than a status column, because an asset
    has no status column — a media run that completed is exactly what "already
    processed" means here.
    """

    async def run(self, ctx: GraphRunContext[AssetState, None]) -> Media | End[int]:
        state = ctx.state
        row = (
            await state.session.execute(
                select(Asset, Brand)
                .join(Brand, Asset.brand_id == Brand.id)
                .where(Asset.id == state.asset_id)
            )
        ).first()

        if row is None:
            raise LookupError(f"asset {state.asset_id} not found")

        asset, brand = row
        if asset.analysis_json is not None:
            log.info("asset.already_processed", asset_id=state.asset_id)
            return End(state.asset_id)

        state.brand_id = brand.id
        state.brand_voice = brand.voice_guidelines

        rules = brand.brand_rules_json or {}
        state.prohibited_content = _rule_list(rules.get("prohibited_content"))
        state.required_elements = _rule_list(rules.get("required_elements"))
        tone = rules.get("tone", {})
        state.avoid_words = _rule_list(tone.get("avoid_words"))
        state.prefer_words = _rule_list(tone.get("prefer_words"))
        state.max_hashtags = int(rules.get("max_hashtags", 5))

        # Read through the backend, never with open() (hard rule #9), and
        # downscale HERE rather than inside the agent so the latency recorded
        # against the media run is model time and not our own JPEG encoding.
        raw = await get_storage().get(asset.storage_key)
        prepared = downscale(raw)
        state.image_data = prepared.data
        state.image_media_type = prepared.media_type

        return Media()


@dataclass
class Media(BaseNode[AssetState, None, int]):
    """Describe the image and check it against the brand's rules."""

    async def run(self, ctx: GraphRunContext[AssetState, None]) -> Content:
        state = ctx.state
        output, _run_id = await _run_agent(
            state,
            "media",
            MediaAgent(),
            MediaInput(
                image_data=state.image_data,
                image_media_type=state.image_media_type,
                prohibited_content=state.prohibited_content,
                required_elements=state.required_elements,
            ),
        )

        state.analysis = output
        asset = await state.session.get(Asset, state.asset_id)
        if asset is not None:
            asset.analysis_json = output.model_dump()

        return Content()


@dataclass
class Content(BaseNode[AssetState, None, int]):
    """Draft one caption per platform from the analysis.

    Unconditional, even when the brand check failed. A failing check is
    information for the human reviewing the Content page, not a reason to
    withhold the drafts — the issues and the captions are shown side by side so
    they can fix the photo and keep the copy.
    """

    async def run(self, ctx: GraphRunContext[AssetState, None]) -> PersistContent:
        state = ctx.state
        analysis = state.analysis
        output, state.content_agent_run_id = await _run_agent(
            state,
            "content",
            ContentAgent(),
            ContentInput(
                description=analysis.description if analysis else "",
                detected_text=_rule_list(analysis.detected_text if analysis else []),
                brand_voice=state.brand_voice,
                avoid_words=state.avoid_words,
                prefer_words=state.prefer_words,
                max_hashtags=state.max_hashtags,
            ),
        )
        state.drafts = output.drafts
        return PersistContent()


@dataclass
class PersistContent(BaseNode[AssetState, None, int]):
    """Write the three drafts and close out the run."""

    async def run(self, ctx: GraphRunContext[AssetState, None]) -> End[int]:
        state = ctx.state

        for draft in state.drafts:
            # max_hashtags is a brand rule (D16) and the prompt asks for it, but
            # a 9B model overshoots it often enough that an unenforced limit is
            # not a rule. Trimmed here rather than rejected: the agent_runs row
            # still holds the model's raw output, so the audit trail shows what
            # was actually returned while the stored draft obeys the brand.
            hashtags = draft.hashtags[: state.max_hashtags]
            if len(hashtags) < len(draft.hashtags):
                log.info(
                    "content.hashtags_trimmed",
                    asset_id=state.asset_id,
                    platform=draft.platform,
                    returned=len(draft.hashtags),
                    kept=len(hashtags),
                )
            state.session.add(
                ContentDraft(
                    asset_id=state.asset_id,
                    platform=draft.platform,
                    text=draft.text,
                    hashtags_json=hashtags,
                    agent_run_id=state.content_agent_run_id,
                    status="pending",
                )
            )

        log.info(
            "asset.processed",
            asset_id=state.asset_id,
            brand_id=state.brand_id,
            brand_check_passes=state.analysis.brand_check.passes if state.analysis else None,
            drafts=len(state.drafts),
            agents=state.agents_run,
        )
        return End(state.asset_id)


# ---------------------------------------------------------------------------
# Graph construction and the two entry points
# ---------------------------------------------------------------------------


def _build_comment_graph() -> object:
    builder = GraphBuilder(state_type=CommentState, output_type=int)
    # `builder.node()` reads each node's `run` return type and wires its outgoing
    # edges from it — which is why Triage's `Respond | Persist` return becomes a
    # visible branch in the rendered diagram rather than a hidden if.
    builder.add(
        builder.node(Ingest),
        builder.node(Triage),
        builder.node(Respond),
        builder.node(Persist),
        builder.edge_from(builder.start_node).to(Ingest),
    )
    return builder.build()


def _build_asset_graph() -> object:
    builder = GraphBuilder(state_type=AssetState, output_type=int)
    builder.add(
        builder.node(IngestAsset),
        builder.node(Media),
        builder.node(Content),
        builder.node(PersistContent),
        builder.edge_from(builder.start_node).to(IngestAsset),
    )
    return builder.build()


comment_graph = _build_comment_graph()
asset_graph = _build_asset_graph()


async def run_comment(
    comment_id: int,
    session: AsyncSession,
    audit_factory: async_sessionmaker[AsyncSession] | None = None,
) -> CommentState:
    """The comment entry point. arq calls this; nothing else knows the graph exists.

    `audit_factory` is only used to write an agent's failure row on a session
    that survives this job's rollback. Optional so a test can drive the graph
    with a single session.
    """
    state = CommentState(comment_id=comment_id, session=session, audit_factory=audit_factory)
    # The start edge carries the first node as its input, so the entry node is
    # passed via `inputs` rather than positionally.
    await comment_graph.run(state=state, inputs=Ingest())  # type: ignore[attr-defined]
    return state


async def run_asset(
    asset_id: int,
    session: AsyncSession,
    audit_factory: async_sessionmaker[AsyncSession] | None = None,
) -> AssetState:
    """The asset entry point. Same shape as `run_comment`, deliberately."""
    state = AssetState(asset_id=asset_id, session=session, audit_factory=audit_factory)
    await asset_graph.run(state=state, inputs=IngestAsset())  # type: ignore[attr-defined]
    return state


async def run_ideation(
    brand_id: int,
    session: AsyncSession,
    audit_factory: async_sessionmaker[AsyncSession] | None = None,
) -> IdeationState:
    """The ideation entry point. One agent call; see `IdeationState` for why
    there is no graph here.

    Unlike the comment/asset paths there is no idempotency guard: ideation is
    triggered on demand (a "Generate Ideas" click), not by a queued row that
    arq might retry, so there is no earlier attempt to detect and no work to
    protect against re-doing.
    """
    state = IdeationState(brand_id=brand_id, session=session, audit_factory=audit_factory)

    brand = await session.get(Brand, brand_id)
    if brand is None:
        raise LookupError(f"brand {brand_id} not found")

    signals = _load_trend_signals(brand.name)
    signals_text = "\n".join(signals) if signals else "none"

    # Real markers if the Insight Agent has produced any for this brand — this
    # is the feedback loop closing. Newest first, capped: an unbounded history
    # would eventually push trend_signals out of the model's usable context.
    insights = (
        (
            await session.execute(
                select(Insight.text)
                .where(Insight.brand_id == brand_id)
                .order_by(Insight.id.desc())
                .limit(5)
            )
        )
        .scalars()
        .all()
    )
    insights_text = "\n".join(insights) if insights else "none"

    output, run_id = await _run_agent(
        state,
        "ideation",
        IdeationAgent(),
        IdeationInput(
            brand_voice=brand.voice_guidelines,
            trend_signals=signals_text,
            past_insights=insights_text,
        ),
    )

    for item in output.ideas:
        session.add(
            ContentIdea(
                brand_id=brand_id,
                text=item.text,
                source_signal=item.source_signal,
                agent_run_id=run_id,
            )
        )
    await session.flush()

    return state


@dataclass
class InsightState:
    """Same shape as `IdeationState`, same reasoning: one agent call, no
    branching, no `pydantic-graph`."""

    brand_id: int
    session: AsyncSession
    audit_factory: async_sessionmaker[AsyncSession] | None = None

    agents_run: list[str] = field(default_factory=list)

    @property
    def entity_type(self) -> str:
        return "brand"

    @property
    def entity_id(self) -> int:
        return self.brand_id


def _summarize_posts(posts: list[Post]) -> str:
    """One line per post: what it said and what it actually did.

    Real numbers only — this is what keeps the agent's output honest (see
    `prompts/insight.md` rules 3-4). Nothing here is a forecast; `metrics_json`
    is filled in only after a post exists, so an unposted idea has no line
    here to summarize in the first place.
    """
    lines = []
    for post in posts:
        metrics = post.metrics_json or {}
        lines.append(
            f"{post.text} — likes: {metrics.get('likes', 0)}, "
            f"comments: {metrics.get('comments', 0)}, shares: {metrics.get('shares', 0)}"
        )
    return "\n".join(lines)


async def run_insight(
    brand_id: int,
    session: AsyncSession,
    audit_factory: async_sessionmaker[AsyncSession] | None = None,
) -> InsightState:
    """The insight entry point. One agent call over real post performance.

    Raises if the brand has no posts yet — generating "patterns" from zero
    data would mean the model inventing them, which is exactly what the
    honesty rule in `prompts/insight.md` exists to prevent. Better as a clear
    dead-lettered error than a hallucinated marker on the Insights page.
    """
    state = InsightState(brand_id=brand_id, session=session, audit_factory=audit_factory)

    brand = await session.get(Brand, brand_id)
    if brand is None:
        raise LookupError(f"brand {brand_id} not found")

    posts = (
        (
            await session.execute(
                select(Post)
                .join(PlatformAccount, Post.account_id == PlatformAccount.id)
                .where(PlatformAccount.brand_id == brand_id)
            )
        )
        .scalars()
        .all()
    )
    if not posts:
        raise ValueError(f"brand {brand_id} has no posts to analyze yet")

    output, run_id = await _run_agent(
        state,
        "insight",
        InsightAgent(),
        InsightInput(posts_summary=_summarize_posts(list(posts))),
    )

    for marker in output.markers:
        session.add(Insight(brand_id=brand_id, text=marker, agent_run_id=run_id))
    await session.flush()

    return state


def mermaid() -> str:
    """Step 10's comment diagram, generated from the definition rather than drawn."""
    return comment_graph.render(title="Comment pipeline", direction="LR")  # type: ignore[attr-defined]


def mermaid_asset() -> str:
    """Step 10's asset diagram, from the same source of truth."""
    return asset_graph.render(title="Asset pipeline", direction="LR")  # type: ignore[attr-defined]


__all__ = [
    "UTC",
    "AssetState",
    "CommentState",
    "IdeationState",
    "InsightState",
    "asset_graph",
    "comment_graph",
    "datetime",
    "mermaid",
    "mermaid_asset",
    "run_asset",
    "run_comment",
    "run_ideation",
    "run_insight",
]
