#!/usr/bin/env bash
#
# Post one comment and watch the agents handle it.
#
#   ./scripts/comment.sh "Do you ship to Singapore?"
#   ./scripts/comment.sh -b fieldnote "Is this suitable for sensitive skin?"
#   ./scripts/comment.sh -n "check out my page, free followers"   # don't wait
#
# Everything the raw curl makes you supply by hand, this works out:
#
#   external_id      a fresh one every run. Reusing one is a deliberate no-op
#                    (D9), which reads as {"inserted":0,"skipped":1} and looks
#                    broken when it is the idempotency guarantee working.
#   created_at       now, so the comment sorts to the top of the Inbox rather
#                    than below seed data dated from 2026-08-01.
#   handle + post    resolved from the API. They depend on seed order, and a
#                    pair that does not match a seeded row is counted as
#                    `skipped` — the same number as a duplicate, for a
#                    completely different reason.
set -euo pipefail

API="${API:-http://localhost:8000}"
WEB="${WEB:-http://localhost:3000}"
BRAND_QUERY="${BRAND:-}"
WAIT=1
TIMEOUT=120

usage() {
  cat <<'USAGE'
Usage: scripts/comment.sh [options] "comment text"

Options:
  -b, --brand NAME|ID   Brand to post under. Name is matched case-insensitively
                        on a substring ("fieldnote"). Default: the first brand.
  -a, --author HANDLE   Comment author. Default: @you
  -n, --no-wait         Post and exit without waiting for the agents.
  -t, --timeout SECS    How long to wait for a draft. Default: 120
  -h, --help            This.

Environment: API (default http://localhost:8000), WEB, BRAND.
USAGE
}

AUTHOR="@you"
TEXT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -b|--brand)   BRAND_QUERY="${2:-}"; shift 2 ;;
    -a|--author)  AUTHOR="${2:-}"; shift 2 ;;
    -t|--timeout) TIMEOUT="${2:-}"; shift 2 ;;
    -n|--no-wait) WAIT=0; shift ;;
    -h|--help)    usage; exit 0 ;;
    # Anything else is the comment text. Unknown flags are NOT silently
    # swallowed — scripts/demo.sh once treated --help as "proceed" and its next
    # action was `make reset`.
    -*)           echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    *)            TEXT="${TEXT:+$TEXT }$1"; shift ;;
  esac
done

[[ -n "$TEXT" ]] || { echo "Nothing to post: give me some comment text." >&2; usage >&2; exit 2; }

for tool in curl jq; do
  command -v "$tool" >/dev/null || { echo "Need $tool on PATH." >&2; exit 1; }
done

# --- is anything actually up? ----------------------------------------------
# Readiness, not liveness: /health stays green in front of a stopped Postgres,
# which is exactly how a full disk once presented as a healthy stack (D28).
READY=$(curl -sf -m 5 "$API/health/ready" 2>/dev/null) || {
  echo "The API is not ready at $API. Try: make up" >&2
  exit 1
}
echo "$READY" | jq -e '.database and .redis' >/dev/null || {
  echo "The API is up but a dependency is down: $READY" >&2
  exit 1
}

# Ollama runs on the HOST, not in Compose, so `docker compose ps` says nothing
# about it and /health/ready cannot either — the API never calls a model. It
# has been down three times in this project, and each time the symptom was a
# comment that ingested fine and then simply never got a draft. One second
# here beats two minutes of waiting and a failed agent run.
OLLAMA="${OLLAMA_HOST:-http://localhost:11434}"
curl -sf -m 5 "$OLLAMA/api/tags" >/dev/null 2>&1 || {
  echo "Ollama is not answering on $OLLAMA." >&2
  echo "The comment would ingest and then never get a draft. Start it with:" >&2
  echo "  ollama serve" >&2
  echo "Then pick up anything already stranded:" >&2
  echo "  curl -X POST $API/queue/requeue" >&2
  exit 1
}

# --- which brand, which post ------------------------------------------------
BRANDS=$(curl -sf "$API/brands")
if [[ -z "$BRAND_QUERY" ]]; then
  BRAND_ID=$(jq -r '.[0].id' <<<"$BRANDS")
elif [[ "$BRAND_QUERY" =~ ^[0-9]+$ ]]; then
  BRAND_ID="$BRAND_QUERY"
else
  BRAND_ID=$(jq -r --arg q "$BRAND_QUERY" \
    'map(select(.name | ascii_downcase | contains($q | ascii_downcase))) | .[0].id // empty' <<<"$BRANDS")
fi
[[ -n "${BRAND_ID:-}" && "$BRAND_ID" != "null" ]] || {
  echo "No brand matching '${BRAND_QUERY}'. Available:" >&2
  jq -r '.[] | "  \(.id)  \(.name)"' <<<"$BRANDS" >&2
  exit 1
}
BRAND_NAME=$(jq -r --argjson id "$BRAND_ID" '.[] | select(.id==$id) | .name' <<<"$BRANDS")

POST=$(curl -sf "$API/posts?brand_id=$BRAND_ID" | jq -c '.[0] // empty')
[[ -n "$POST" ]] || { echo "Brand $BRAND_ID has no posts. Run: make seed" >&2; exit 1; }
POST_EXTERNAL_ID=$(jq -r '.external_id' <<<"$POST")
ACCOUNT_ID=$(jq -r '.account_id' <<<"$POST")

# The comment attaches to a post, but ingest matches on the account's HANDLE —
# so it has to be the handle of the account that owns this particular post.
HANDLE=$(curl -sf "$API/platform_accounts?brand_id=$BRAND_ID" \
  | jq -r --argjson id "$ACCOUNT_ID" '.[] | select(.id==$id) | .handle')
[[ -n "$HANDLE" ]] || { echo "No account $ACCOUNT_ID for brand $BRAND_ID." >&2; exit 1; }

EXTERNAL_ID="cli-$(date +%s)-$RANDOM"
CREATED_AT=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)

echo "Posting to $BRAND_NAME ($HANDLE, $POST_EXTERNAL_ID)"

RESULT=$(jq -n \
  --arg e "$EXTERNAL_ID" --arg p "$POST_EXTERNAL_ID" --arg h "$HANDLE" \
  --arg a "$AUTHOR" --arg t "$TEXT" --arg c "$CREATED_AT" \
  '[{external_id:$e, post_external_id:$p, account_handle:$h, author:$a, text:$t, created_at:$c}]' \
  | curl -sf -X POST "$API/ingest/comments" -H "Content-Type: application/json" --data @-)

echo "  $RESULT"

# `skipped` covers two different things and reports one number. A fresh
# external_id rules out the duplicate case, so here it can only mean the
# handle/post pair did not resolve — worth saying outright rather than leaving
# a silent no-op.
if [[ "$(jq -r '.inserted' <<<"$RESULT")" != "1" ]]; then
  echo "Not inserted. The handle/post pair did not match a seeded row." >&2
  exit 1
fi

if [[ "$WAIT" -eq 0 ]]; then
  echo "Queued. Watch it at $WEB/inbox?brand_id=$BRAND_ID"
  exit 0
fi

# --- wait for the agents ----------------------------------------------------
printf 'Waiting for triage'
DEADLINE=$(( $(date +%s) + TIMEOUT ))
while [[ $(date +%s) -lt $DEADLINE ]]; do
  ROW=$(curl -sf "$API/comments?brand_id=$BRAND_ID&limit=100" \
    | jq -c --arg e "$EXTERNAL_ID" '.[] | select(.external_id==$e)' 2>/dev/null || true)

  if [[ -n "$ROW" ]]; then
    STATUS=$(jq -r '.status' <<<"$ROW")
    # `replied` is the terminal state for a comment needing no reply — spam and
    # praise never get a draft, and waiting for one would hang until timeout.
    if [[ "$STATUS" == "drafted" || "$STATUS" == "replied" || "$STATUS" == "failed" ]]; then
      echo
      jq -r '
        "  category  \(.category // "—")   sentiment \(.sentiment // "—")   urgency \(.urgency // "—")",
        "  status    \(.status)",
        (if .draft then "  draft     \(.draft.final_text // .draft.text)"
         elif .needs_reply == false then "  draft     none — needs_reply is false, so the drafting call was skipped"
         else "  draft     none" end)' <<<"$ROW"
      echo
      echo "  $WEB/inbox?brand_id=$BRAND_ID"
      exit 0
    fi
  fi
  printf '.'
  sleep 3
done

echo
echo "Still not drafted after ${TIMEOUT}s. Usually the model is unreachable —" >&2
echo "check that Ollama is running, then: curl -X POST $API/queue/requeue" >&2
exit 1
