#!/bin/sh
# Replaces the build-time API URL placeholder with this container's
# NEXT_PUBLIC_API_URL, then runs the server. See web/Dockerfile.
set -eu

: "${NEXT_PUBLIC_API_URL:?NEXT_PUBLIC_API_URL must be set: it is the browser's address for the API}"

# Runs once per container: after the first start the placeholder is gone, so a
# new value needs a new container (compose `up` / a new ECS task), not a restart.
# Only .next/ is rewritten; its directories are owned by `node`, which sed -i
# needs for its temp file. `&`, `|` and `\` are escaped for the replacement.
url=$(printf '%s' "$NEXT_PUBLIC_API_URL" | sed 's/[&|\\]/\\&/g')
grep -rl "__SOCIALOPS_API_URL__" /app/.next \
  | xargs -r sed -i "s|__SOCIALOPS_API_URL__|${url}|g"

exec "$@"
