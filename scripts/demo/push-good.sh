#!/usr/bin/env bash
# Segment 10:00. Pushes ONE harmless commit to main so the pipeline builds, deploys and health-checks.
# Run from a clean clone of the repo. Asks before pushing.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git checkout main && git pull --ff-only origin main
[ -z "$(git status --porcelain)" ] || { echo "Working tree is not clean. Stop."; exit 1; }
echo "- $(date -u +%FT%TZ) live demo deploy" >> docs/milestone6/DEMO_LOG.md
git add docs/milestone6/DEMO_LOG.md
git commit -m "docs: record live demo deploy"
read -r -p "Push this commit to main now? Type YES: " a; [ "$a" = "YES" ] || { echo "not pushed"; exit 1; }
git push origin main
echo "Pushed $(git rev-parse --short HEAD). Open https://github.com/Junebhone/SocialOps/actions"
