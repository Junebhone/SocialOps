#!/usr/bin/env python3
"""Time a replay and print the numbers step 9 records in the README.

Run against a dump; it POSTs the file, waits for the queue to drain, then reads
the per-agent totals straight off `GET /agent_runs`. The percentiles come from
the same query the Agents page renders, so the README and the screen cannot
disagree — that is the whole reason this reads the API rather than doing its own
arithmetic over the database.

    python scripts/measure.py data/comments_small.json
    python scripts/measure.py data/viral_post_dump.json --label "replay-full (2,000)"
    python scripts/measure.py data/comments_small.json --report-only

`--report-only` skips the ingest and reports on the run already in the database,
which is how you recover the numbers when the poll loop did not survive the
drain. Wall time comes from the audit trail either way, not from this script's
stopwatch, so the report does not depend on it having been watching.

Prints a Markdown block. Paste it into the README, or use `make measure`.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

# The API's address as seen from wherever this runs. Overridable because the
# same script has to work from the host and from inside the api container.
DEFAULT_API = "http://localhost:8000"

# How long the queue must read empty before we call it drained. One empty poll
# is not enough: between a job finishing and the next being picked up, both
# `queued` and `running` are legitimately 0 for a moment, and stopping there
# would report a wall time that is minutes short.
QUIET_POLLS = 3
POLL_SECONDS = 5

# How many consecutive unreachable polls before giving up on watching. Enough to
# ride out an API reload; short enough not to hang for an hour on a dead stack.
MAX_CONSECUTIVE_MISSES = 12


def _get(api: str, path: str) -> Any:
    with urllib.request.urlopen(f"{api}{path}", timeout=30) as response:
        return json.loads(response.read())


def _get_or_none(api: str, path: str) -> Any:
    """A single failed poll must not end a two-hour measurement.

    The API restarts on `--reload` whenever a file changes, and a request in
    flight at that moment gets `RemoteDisconnected`. That killed one run of this
    script outright, after twenty minutes of draining, while the worker carried
    on perfectly well — the measurement was the only casualty.
    """
    try:
        return _get(api, path)
    except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError):
        return None


def _post_json(api: str, path: str, body: Any) -> Any:
    request = urllib.request.Request(
        f"{api}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        sys.exit(f"Ingest failed with HTTP {exc.code}: {exc.read().decode()[:400]}")


def _brand_ids(api: str) -> list[int]:
    return [brand["id"] for brand in _get(api, "/brands")]


def _drain(api: str) -> tuple[float, int]:
    """Block until the queue has been empty for QUIET_POLLS consecutive checks."""
    started = time.monotonic()
    quiet = 0
    peak = 0
    misses = 0

    while quiet < QUIET_POLLS:
        stats = _get_or_none(api, "/queue/stats")
        if stats is None:
            # Do not count a failed poll as an empty queue. That would end the
            # drain early and report a wall time far short of the truth.
            misses += 1
            if misses > MAX_CONSECUTIVE_MISSES:
                print("\n  API unreachable for too long; reporting on what is recorded.")
                break
            time.sleep(POLL_SECONDS)
            continue

        misses = 0
        depth = stats["queued"] + stats["running"]
        peak = max(peak, depth)
        quiet = quiet + 1 if depth == 0 else 0

        elapsed = time.monotonic() - started
        print(
            f"\r  {elapsed / 60:6.1f} min  queued {stats['queued']:5d}  "
            f"running {stats['running']:2d}  failed {stats['failed']:3d}",
            end="",
            flush=True,
        )
        if quiet < QUIET_POLLS:
            time.sleep(POLL_SECONDS)

    print()
    # Subtract the confirmation polls; the work was already done when the first
    # empty reading came back.
    return time.monotonic() - started - (QUIET_POLLS - 1) * POLL_SECONDS, peak


def _window(api: str, brand_ids: list[int]) -> tuple[str | None, str | None]:
    """When the first and last recorded run happened, across every brand."""
    firsts: list[str] = []
    lasts: list[str] = []
    for brand_id in brand_ids:
        page = _get(api, f"/agent_runs?brand_id={brand_id}&limit=1")
        if page.get("first_run_at"):
            firsts.append(page["first_run_at"])
        if page.get("last_run_at"):
            lasts.append(page["last_run_at"])
    return (min(firsts) if firsts else None, max(lasts) if lasts else None)


def _seconds_between(first: str | None, last: str | None) -> float | None:
    if not first or not last:
        return None
    started = datetime.fromisoformat(first)
    ended = datetime.fromisoformat(last)
    return (ended - started).total_seconds()


def _totals(api: str, brand_ids: list[int]) -> dict[str, dict[str, Any]]:
    """Per-agent totals summed across brands.

    `GET /agent_runs` is brand-scoped by design (D17), and a replay spans every
    seeded brand, so the totals are combined here rather than by relaxing the
    endpoint. Token counts and run counts add; percentiles do not, so those are
    reported per brand-max rather than averaged into a number that means nothing.
    """
    combined: dict[str, dict[str, Any]] = {}
    for brand_id in brand_ids:
        page = _get(api, f"/agent_runs?brand_id={brand_id}&limit=1")
        for row in page["totals"]:
            entry = combined.setdefault(
                row["agent"],
                {"runs": 0, "errors": 0, "input_tokens": 0, "output_tokens": 0,
                 "p50": 0, "p95": 0},
            )
            entry["runs"] += row["runs"]
            entry["errors"] += row["errors"]
            entry["input_tokens"] += row["input_tokens"]
            entry["output_tokens"] += row["output_tokens"]
            entry["p50"] = max(entry["p50"], row["p50_latency_ms"])
            entry["p95"] = max(entry["p95"], row["p95_latency_ms"])
    return combined


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", help="Path to a comments JSON dump")
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--label", default=None, help="How to name this run in the table")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Skip the ingest and report on the run already in the database",
    )
    args = parser.parse_args()

    with open(args.dump) as handle:
        rows = json.load(handle)

    label = args.label or f"{args.dump} ({len(rows):,})"
    brand_ids = _brand_ids(args.api)
    if not brand_ids:
        sys.exit("No brands. Run `make seed` first.")

    before = _get(args.api, "/queue/stats")["failed"]
    peak = 0
    watched: float | None = None

    if args.report_only:
        result = {"inserted": len(rows), "skipped": 0, "rejected": 0, "enqueued": 0}
        print("Reporting on the run already recorded; nothing ingested.")
    else:
        print(f"Ingesting {len(rows):,} rows from {args.dump} …")
        result = _post_json(args.api, "/ingest/comments", rows)
        print(f"  {result}")

        if result["enqueued"] == 0:
            print("Nothing was enqueued — already ingested.")
            print("Use --report-only to report on it, or `make reset` to measure it again.")
            return

        print("Draining …")
        watched, peak = _drain(args.api)

    totals = _totals(args.api, brand_ids)
    first, last = _window(args.api, brand_ids)
    recorded = _seconds_between(first, last)
    # The audit trail is authoritative: it is what actually happened, and it does
    # not care whether this script was watching. The stopwatch is the fallback.
    seconds = recorded if recorded is not None else (watched or 0.0)
    after = _get(args.api, "/queue/stats")["failed"]

    runs = sum(row["runs"] for row in totals.values())
    tokens_in = sum(row["input_tokens"] for row in totals.values())
    tokens_out = sum(row["output_tokens"] for row in totals.values())

    print()
    print(f"### {label}")
    print()
    print(f"- Ingested **{result['inserted']:,}** comments "
          f"({result['skipped']:,} already present, {result['rejected']:,} rejected to the DLQ)")
    source = "first to last recorded run" if recorded is not None else "measured by this script"
    peak_note = f", peak queue depth {peak:,}" if peak else ""
    print(f"- Wall time **{seconds / 60:.1f} min** ({seconds:.0f}s, {source}){peak_note}")
    print(f"- **{runs:,}** agent runs, **{tokens_in + tokens_out:,}** tokens "
          f"({tokens_in:,} in / {tokens_out:,} out)")
    print(f"- Dead-lettered during this run: **{after - before}**")
    if result["inserted"]:
        print(f"- **{seconds / result['inserted']:.1f}s per comment** end to end")
    print()
    print("| Agent | Runs | Errors | Tokens in | Tokens out | p50 | p95 |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for agent in ("triage", "response", "media", "content"):
        row = totals.get(agent)
        if not row:
            continue
        print(f"| {agent} | {row['runs']:,} | {row['errors']:,} | {row['input_tokens']:,} "
              f"| {row['output_tokens']:,} | {row['p50']:,} ms | {row['p95']:,} ms |")


if __name__ == "__main__":
    main()
