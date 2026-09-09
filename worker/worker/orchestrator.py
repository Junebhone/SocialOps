"""The comment pipeline, as a `pydantic-graph` graph (D12).

    ingest → triage → (needs_reply ? respond : persist) → persist → end

Why a graph rather than a 15-line async function: typed state passed between
steps, a shape that absorbs the asset path in step 6 without reshaping, and a
Mermaid diagram generated from the definition rather than hand-drawn and left to
rot (step 10). It also translates directly into a Phase 5 Step Functions state
machine.

The branch is an `if`, deliberately. Routing through a model — Pydantic AI
sub-agents, or triage calling response as a tool — would put control flow inside
a 2B model's judgement, nondeterministically and unauditably, and the nested call
would break hard rule #5's one row per invocation.

Nodes call agents and write `agent_runs`; agents touch neither the queue nor the
database (hard rule #3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog
from app.models import AgentRun, Brand, Comment, PlatformAccount, Post, ReplyDraft
from pydantic_graph import BaseNode, End, GraphBuilder, GraphRunContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from worker.agents.response import ResponseAgent
from worker.agents.schemas import ResponseInput, TriageInput, TriageOutput
from worker.agents.triage import TriageAgent
from worker.llm import Usage

log = structlog.get_logger()


@dataclass
class CommentState:
    """Everything the run needs, and everything it has learned so far."""

    comment_id: int
    session: AsyncSession

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


async def _record_run(
    state: CommentState,
    agent: str,
    output: dict[str, object] | None,
    usage: Usage | None,
    status: str,
    error: str | None = None,
) -> int:
    """One `agent_runs` row per agent invocation (hard rule #5).

    Written by the node, not the agent, and always joinable back to the comment
    that caused it through entity_type/entity_id (D7).
    """
    run = AgentRun(
        agent=agent,
        entity_type="comment",
        entity_id=state.comment_id,
        brand_id=state.brand_id,
        output_json=output,
        status=status,
        input_tokens=usage.input_tokens if usage else 0,
        output_tokens=usage.output_tokens if usage else 0,
        cost_usd=usage.cost_usd if usage else None,
        latency_ms=usage.latency_ms if usage else 0,
        error=error,
    )
    state.session.add(run)
    await state.session.flush()
    state.agents_run.append(agent)
    return run.id


@dataclass
class Ingest(BaseNode[CommentState, None, int]):
    """Load the comment and its brand context. No model call."""

    async def run(self, ctx: GraphRunContext[CommentState, None]) -> Triage:
        state = ctx.state
        row = (
            await state.session.execute(
                select(Comment, Brand)
                .join(Post, Comment.post_id == Post.id)
                .join(PlatformAccount, Post.account_id == PlatformAccount.id)
                .join(Brand, PlatformAccount.brand_id == Brand.id)
                .where(Comment.id == state.comment_id)
            )
        ).first()

        if row is None:
            raise LookupError(f"comment {state.comment_id} not found")

        comment, brand = row
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
        output, usage = await TriageAgent().run_with_usage(
            TriageInput(comment_text=state.comment_text)
        )
        await _record_run(state, "triage", output.model_dump(), usage, "ok")

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
        output, usage = await ResponseAgent().run_with_usage(
            ResponseInput(
                comment_text=state.comment_text,
                brand_voice=state.brand_voice,
                avoid_words=state.avoid_words,
            )
        )
        state.reply_agent_run_id = await _record_run(
            state, "response", output.model_dump(), usage, "ok"
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


def _build_graph() -> object:
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


comment_graph = _build_graph()


async def run_comment(comment_id: int, session: AsyncSession) -> CommentState:
    """The single entry point. arq calls this; nothing else knows the graph exists."""
    state = CommentState(comment_id=comment_id, session=session)
    # The start edge carries the first node as its input, so the entry node is
    # passed via `inputs` rather than positionally.
    await comment_graph.run(state=state, inputs=Ingest())  # type: ignore[attr-defined]
    return state


def mermaid() -> str:
    """Step 10's diagram, generated from the definition rather than drawn."""
    return comment_graph.render(title="Comment pipeline", direction="LR")  # type: ignore[attr-defined]


__all__ = ["CommentState", "comment_graph", "mermaid", "run_comment", "datetime", "UTC"]
