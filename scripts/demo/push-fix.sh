#!/usr/bin/env bash
# After the rollback demo: reverts the controlled failure so main is healthy again. Asks before pushing.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git checkout main && git pull --ff-only origin main
[ -z "$(git status --porcelain)" ] || { echo "Working tree is not clean. Stop."; exit 1; }
grep -q "_DEMO_BREAK_READINESS = True" api/app/main.py || { echo "Break is not present. Nothing to fix."; exit 0; }
git log -1 --format=%s | grep -qE '^(Reapply|Revert "Revert)' || { echo "HEAD is not the re-armed failure commit. Stop."; exit 1; }
git revert --no-edit HEAD
grep -q "_DEMO_BREAK_READINESS" api/app/main.py && { echo "Break still present. Stop."; git revert --abort 2>/dev/null || true; exit 1; }
read -r -p "Push the fix to main now? Type YES: " a; [ "$a" = "YES" ] || { echo "not pushed"; exit 1; }
git push origin main
echo "Pushed $(git rev-parse --short HEAD). Wait for the run to go green, then run terraform plan again."
