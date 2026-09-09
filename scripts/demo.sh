#!/usr/bin/env bash
#
# The demo path, from nothing to a page you can show someone.
#
#   ./scripts/demo.sh            reset, seed, upload a photo, replay 300 comments
#   ./scripts/demo.sh --keep     same, but do not wipe the database first
#
# Everything here is a `make` target you could run by hand. It exists so the
# order is not something to remember five minutes before showing it to someone.
set -euo pipefail

cd "$(dirname "$0")/.."

API="${API:-http://localhost:8000}"
WEB="${WEB:-http://localhost:3000}"
BRAND_NAME="${BRAND_NAME:-Ridgeline Roasters}"
SAMPLE_IMAGE="${SAMPLE_IMAGE:-data/sample_images/ridgeline_beans_flatlay.png}"

usage() {
  sed -n '3,9p' "$0" | sed 's/^# \{0,1\}//'
}

# Anything unrecognised is refused rather than ignored. The first real action
# here deletes the database volume, and `--help` silently falling through to
# that is not a mistake worth making once.
KEEP=0
case "${1:-}" in
  "")       ;;
  --keep)   KEEP=1 ;;
  -h|--help) usage; exit 0 ;;
  *)
    echo "Unknown option: $1" >&2
    usage >&2
    exit 2
    ;;
esac

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
note() { printf '  %s\n' "$*"; }

require() {
  command -v "$1" >/dev/null 2>&1 || { echo "Need $1 on PATH." >&2; exit 1; }
}
require curl
require jq
require docker

# --- 0. Preflight ----------------------------------------------------------
# The two things that have actually broken a run: Ollama not running, and the
# Docker disk being full. Both are silent until they are not (D19).

say "Checking prerequisites"

if ! curl -sf -m 5 "${OLLAMA_HOST:-http://localhost:11434}/api/tags" >/dev/null; then
  echo "Ollama is not answering on ${OLLAMA_HOST:-http://localhost:11434}." >&2
  echo "Start it, then run 'make models' if you have not pulled qwen3.5:2b and 9b." >&2
  exit 1
fi
note "Ollama is up"

FREE_MB=$(docker run --rm alpine:3 df -m / 2>/dev/null | awk 'NR==2 {print $4}' || echo 0)
if [[ "${FREE_MB:-0}" -lt 2048 ]]; then
  echo "Only ${FREE_MB}MB free in the Docker VM. Postgres will PANIC and refuse to" >&2
  echo "restart when this fills. Run 'docker builder prune -af', or raise Docker" >&2
  echo "Desktop's virtual disk limit. See D19." >&2
  exit 1
fi
note "Docker has ${FREE_MB}MB free"

# --- 1. A clean stack ------------------------------------------------------

if [[ "$KEEP" -eq 0 ]]; then
  say "Resetting the stack (this deletes the database volume)"
  make reset
else
  say "Keeping existing data"
  make up
  make migrate
fi

say "Waiting for the API to be ready"
# /health/ready, not /health: readiness touches Postgres and Redis, so this
# cannot go green in front of a database that is down.
for _ in $(seq 1 60); do
  if curl -sf -m 5 "$API/health/ready" >/dev/null; then break; fi
  sleep 2
done
curl -sf -m 5 "$API/health/ready" | jq -c . || { echo "API never became ready." >&2; exit 1; }

# --- 2. One photo ----------------------------------------------------------
# Done BEFORE the comment replay on purpose. The upload needs qwen3.5:9b, which
# is the same model the response agent uses (D20) — so it loads once here and is
# warm for the replay, instead of the replay being interrupted by a cold 6.6 GB
# load partway through.

BRAND_ID=$(curl -sf "$API/brands" | jq -r --arg n "$BRAND_NAME" '.[] | select(.name==$n) | .id')
[[ -n "$BRAND_ID" ]] || { echo "No brand named '$BRAND_NAME'. Did make seed run?" >&2; exit 1; }
note "Brand '$BRAND_NAME' is id $BRAND_ID"

say "Uploading $SAMPLE_IMAGE"
curl -sf -F "file=@${SAMPLE_IMAGE}" "$API/assets?brand_id=${BRAND_ID}" \
  | jq -c '{asset: .asset.id, file: .asset.filename, queued: .enqueued}'
note "media + content run in the worker; three drafts appear in ~15-35s"

# --- 3. The comment replay -------------------------------------------------

say "Replaying 300 comments"
curl -sf -X POST -H "Content-Type: application/json" \
  --data @data/comments_small.json "$API/ingest/comments" | jq -c .
note "the queue drains at roughly 7 comments a minute on one laptop"
note "watch it with: make logs    or the counter in the top bar"

# --- 4. Where to look ------------------------------------------------------

say "Open these"
printf '  Inbox     %s/inbox?brand_id=%s\n'   "$WEB" "$BRAND_ID"
printf '  Content   %s/content?brand_id=%s\n' "$WEB" "$BRAND_ID"
printf '  Agents    %s/agents?brand_id=%s\n'  "$WEB" "$BRAND_ID"
printf '  API docs  %s/docs\n'                "$API"

say "The demo, in order"
note "1. Inbox: triaged comments with drafted replies. Approve a few, or select and batch-approve."
note "2. Watch 'failed' and the queue counters in the top bar while it drains."
note "3. Content: the photo, what the vision agent saw, the brand check, three platform captions."
note "4. Agents: every model call, its tokens, cost and latency. Click an entity to see one comment end to end."
echo
