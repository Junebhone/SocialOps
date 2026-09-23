# ADR-0005: Analytics computed live from the source tables

Date: 2026-09-23
Status: accepted

## Context
The Analytics page needs per-brand sentiment trend, category mix, and
time-to-first-response, filterable by date range. These can be computed on
every request from `comments`, `reply_drafts`, and `outbox`, or pre-computed
into a rollup table on a schedule.

Two facts from this codebase shape the choice. Volumes are small: thousands
of comments per brand, so an aggregate over them is fast with the existing
indexes. And arq cron jobs are unreliable here: arq orders its queue by
enqueue time, so a scheduled job waits behind every queued comment job. During
a 300-comment replay the outbox cron waited behind 261 jobs and never ran (see
`_outbox_loop` in `worker/main.py`). A rollup refreshed by arq cron would go
stale during a replay, exactly when the numbers change fastest.

## Decision
Phase 1 computes analytics on read, with plain SQL aggregates. No rollup table
and no cache: the API stays stateless (hard rule 2).

- **Numbers come from SQL, never from a model.** A 2B model cannot be trusted
  to add up, the same reason D12 makes routing an `if`, not a model decision.
- **Days are bucketed in the brand's own time zone.** A new `brands.timezone`
  column (IANA name, default `UTC`) means "Monday" is the brand's Monday.
- **Metric definitions:**
  - Sentiment trend: daily average of `comments.sentiment`, triaged rows only.
  - Category mix: daily count of comments per `category`.
  - Time to first response: `outbox.sent_at - comments.created_at` for
    published replies, reported as p50, p95, and a histogram.
- **Refresh cadence:** every page load reads current data, so there is no
  staleness to manage.
- **Retention:** Phase 1 deletes no raw data. If a retention policy is added
  for `agent_runs` later, a rollup must be added first, or history is lost.

## Alternatives considered
- **Nightly rollup via arq cron.** Rejected: it starves behind queued jobs
  (above), and the data would be up to a day old.
- **Materialized view refreshed by a periodic asyncio task,** like
  `_outbox_loop`. Viable, but unnecessary at current volumes. This is the
  planned upgrade path.
- **Ask the LLM to compute the numbers.** Rejected: small models get
  arithmetic wrong.

## Consequences
- Simple, and always current. No new moving parts.
- Query cost grows with row count. **Revisit trigger:** p95 latency of
  `GET /analytics` above 500 ms, or more than 1M comments for one brand. Then
  add an `analytics_daily` materialized view refreshed by a periodic task
  (Phase 1-4), or by an EventBridge schedule (Phase 5+).
- Time to first response on seeded data uses synthetic August dates, so it
  shows weeks, not seconds. Demo it with fresh comments from
  `scripts/comment.sh`, which stamps `created_at` as now.

## Addendum: the weekly summary (analytics agent)
The module also ships a weekly plain-English summary per brand, written by an
`analytics` agent (`tier: fast`). It follows the same rule as the dashboard:
**the model never computes a number.** The worker calls
`app/analytics_queries.py::compute_analytics` (the function behind
`GET /analytics`), flattens the result into labelled lines, and the agent only
puts those figures into words. The figures are stored with the text in
`analytics_summaries.stats_json`, so every sentence can be checked against its
inputs. A week with no triaged comments gets a fixed sentence and no model
call, because a model asked to describe nothing tends to invent something.

**Schedule.** Not an arq cron job, for the reason above. A plain asyncio loop
in the worker (`_summary_loop`, the `_outbox_loop` pattern) checks hourly
whether any brand lacks a summary for the Monday-to-Sunday week that just
ended, in the brand's own time zone, and enqueues one job per missing week.
The job may wait behind a replay, which is acceptable for a weekly digest;
the hourly re-check is what guarantees it runs eventually. A DB check plus a
per-week job key make the schedule idempotent. "Generate now" on the page
enqueues a summary of the last 7 days on demand, for demos.
