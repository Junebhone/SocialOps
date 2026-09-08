.PHONY: up down logs migrate seed test lint replay replay-full eval models reset

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
	docker compose exec api ruff check . && docker compose exec api mypy app
	docker compose exec worker ruff check . && docker compose exec worker mypy worker
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

models:
	ollama pull qwen3.5:2b
	ollama pull qwen3.5:9b

reset: down
	docker compose down -v
	$(MAKE) up migrate seed
