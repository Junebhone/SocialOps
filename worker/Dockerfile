# Built from the REPO ROOT, not ./worker — see the `context: .` in docker-compose.yml.
# The worker's orchestrator writes comments, reply_drafts and agent_runs, so it needs
# the SQLAlchemy models. Those are defined once, in the api package, and copied in
# here rather than duplicated: two definitions of `comments` would drift, and the one
# that drifts silently is the one that only the replay exercises. See D24.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app:/opt/api \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies resolve from pyproject.toml alone, so this layer caches across source edits.
COPY worker/pyproject.toml ./
RUN mkdir -p worker && touch worker/__init__.py && pip install --no-cache-dir -e ".[dev]"

# The shared schema. Copied, not bind-mounted, so the image is self-contained and
# still runs on ECS in Phase 3 where there are no host mounts.
COPY api/app /opt/api/app

COPY worker/ .

CMD ["arq", "worker.main.WorkerSettings"]
