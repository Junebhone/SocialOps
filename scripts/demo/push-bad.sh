#!/usr/bin/env bash
# Segment 13:00. Re-arms the CONTROLLED failure: on ECS only, /health/ready returns 503.
# The site and /health stay up (the ECS circuit breaker does not trip); the pipeline's own
# health check fails and rolls back automatically. Run from a clean clone. Asks before pushing.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git checkout main && git pull --ff-only origin main
[ -z "$(git status --porcelain)" ] || { echo "Working tree is not clean. Stop."; exit 1; }
# 746c48a reverted the demo break (862d1ce). Reverting that revert puts the break back.
git revert --no-edit 746c48a
grep -q "_DEMO_BREAK_READINESS = True" api/app/main.py || { echo "Break not applied. Stop."; git revert --abort 2>/dev/null || true; exit 1; }
read -r -p "Push the controlled failure to main now? Type YES: " a; [ "$a" = "YES" ] || { echo "not pushed"; exit 1; }
git push origin main
echo "Pushed $(git rev-parse --short HEAD). Expect: deploy runs, health check fails 10/10, ROLLED BACK, run is red."
echo "AFTER the demo, run scripts/demo/push-fix.sh to restore normal."
