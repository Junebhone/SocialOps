.PHONY: up down logs migrate seed test lint replay replay-full eval measure measure-full diagrams demo models reset

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

# 2,000 comments. Unattended: expect ~1h+. Stop the web container first to free memory.

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

# Unattended: expect 1.5-2h. Stop the web container first to free memory, and
# check `docker system df` — the default 8 GB Docker disk is not enough (D19).
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
