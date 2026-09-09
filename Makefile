.PHONY: up down logs migrate seed test lint replay replay-full eval measure measure-full diagrams demo models reset prune

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api worker

migrate:
	docker compose exec api alembic upgrade head

seed:
	docker compose exec api python /app/data/seed.py

test:
	docker compose exec api pytest -q
	docker compose exec worker pytest -q

lint:
	docker compose exec api ruff check . && docker compose exec api mypy app tests
	docker compose exec worker ruff check . && docker compose exec worker mypy worker tests
	cd web && npx eslint . --max-warnings=0

replay:
	curl -s -X POST -H "Content-Type: application/json" \
	  --data @data/comments_small.json http://localhost:8000/ingest/comments | jq .

# 2,000 comments. Unattended: measured ~10.5s per comment on one laptop, so
# expect 5-6 hours, not the hour originally estimated. Stop the web container
# first to free memory, and check `docker system df` (D19).

replay-full:
	curl -s -X POST -H "Content-Type: application/json" \
	  --data @data/viral_post_dump.json http://localhost:8000/ingest/comments | jq .

eval:
	docker compose exec worker python -m worker.eval data/eval.json

# Time a replay and print the Markdown block step 9 records in the README.
# Reads the percentiles off GET /agent_runs — the same query the Agents page
# renders — so the README and the screen cannot disagree.
measure:
	python3 scripts/measure.py data/comments_small.json --label "replay (300 comments)"

# Unattended: 5-6 hours at the measured 10.5s per comment. Stop the web
# container first, and check `docker system df` — the default 8 GB Docker disk
# is not enough (D19).
measure-full:
	python3 scripts/measure.py data/viral_post_dump.json --label "replay-full (2,000 comments)"

# Re-render the pipeline diagrams from the pydantic-graph definitions (D12).
# Run after adding or removing an orchestrator node.
diagrams:
	python3 scripts/gen_diagrams.py

demo:
	./scripts/demo.sh

models:
	ollama pull qwen3.5:2b
	ollama pull qwen3.5:9b

reset: down
	docker compose down -v
	$(MAKE) up migrate seed
	@# `up` builds, which orphans the previous images. Measured: one reset left
	@# ~2 GB of dangling layers behind, and three resets fill Docker's default
	@# 8 GB disk — at which point Postgres PANICs and will not restart (D19).
	docker image prune -f

# Reclaim Docker disk. Dangling images and build cache only: both are rebuild
# artefacts, so nothing here loses data.
#
# Deliberately NOT `docker volume prune`. That removes every volume no container
# references, which on a shared machine includes other projects' databases — it
# would have taken an unrelated project's MySQL volume on this one.
prune:
	docker image prune -f
	docker builder prune -af
	@docker run --rm alpine:3 df -h / | awk 'NR==2 {printf "  %s free of %s in the Docker VM\n", $$4, $$2}'
