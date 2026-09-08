# ADR-0003: Orchestration via pydantic-graph

Date: 2026-09-08
Status: accepted

## Context
`CLAUDE.md` originally specified LangGraph for the orchestrator. The Phase 1 graph is
`ingest → triage → (needs_reply ? response : end) → persist` — a linear chain with one branch.
Meanwhile ADR-0002 adopts Pydantic AI, whose ecosystem already covers orchestration
(`pydantic-graph`, sub-agents, durable execution, deferred tools).

## Decision
`worker/orchestrator.py` is a `pydantic-graph` graph with one typed node per step. Nodes call
Pydantic AI agents and write `agent_runs`; agents contain no graph types. No durable-execution
layer.

## Alternatives considered
- **LangGraph** — a good library, but oversized for a linear chain with one branch, and a second
  framework family paid for twice now that Pydantic AI covers the same ground.
- **A plain async function** (~15 lines) — entirely defensible and the right call if time gets
  tight. Rejected because `pydantic-graph` costs ~45 extra lines and returns typed state between
  nodes, a shape that absorbs the asset path without reshaping, and **auto-generated Mermaid from
  the graph definition** — a step 10 deliverable that would otherwise be hand-drawn and left to rot.
- **Pydantic AI sub-agents / agent delegation** — routing inside a model call means a 2B model
  decides control flow, nondeterministically and unauditably, and the nested call breaks hard rule
  #5's one-row-per-invocation. The routing rule is `if needs_reply`; it stays an `if`.
- **Durable execution (Temporal, DBOS, Prefect, Restate)** — each drags in a new infrastructure
  component, and `arq` on Redis already owns retries and the DLQ. Two retry mechanisms on one job
  means double-charged LLM calls and DLQ entries nobody can explain.
- **Human-in-the-loop primitives** (LangGraph `interrupt()`, Pydantic AI deferred tools) — the
  strongest argument for either framework, and still wrong here: approval arrives days later over a
  separate HTTP request, so pausing a live run would need durably checkpointed state and fights hard
  rule #2's stateless API. The graph persists the draft and ends; approval is the outbox.

## Consequences
The graph object translates directly into the Phase 5 Step Functions state machine, making that
migration a translation rather than a rewrite, and the architecture diagram is generated rather than
maintained by hand. Cost: more ceremony than a function for a chain this short, and one more package
in the dependency tree — though from a family already present.
