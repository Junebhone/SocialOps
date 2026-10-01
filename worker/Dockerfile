# Built from the REPO ROOT, not ./worker — see the `context: .` in docker-compose.yml.
# The worker's orchestrator writes comments, reply_drafts and agent_runs, so it needs
# the SQLAlchemy models. Those are defined once, in the api package, and copied in
# here rather than duplicated: two definitions of `comments` would drift, and the one
# that drifts silently is the one that only the replay exercises. See D24.
#
# Same three stages as api/Dockerfile, and the last is the default (D33):
#   builder  a virtualenv holding the runtime dependencies
#   dev      builder + test/lint tools + the worker source tree
#   runtime  python:3.12-slim + the virtualenv + the worker package, as non-root

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app:/opt/api \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app


FROM base AS builder

# Dependencies resolve from pyproject.toml alone, so this layer caches across
# source edits. The package itself is not installed; it is on PYTHONPATH.
COPY worker/pyproject.toml ./
RUN python -m venv /opt/venv \
 && python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt \
 && pip install --no-cache-dir -r /tmp/requirements.txt


FROM builder AS dev

RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['optional-dependencies']['dev']))" > /tmp/requirements-dev.txt \
 && pip install --no-cache-dir -r /tmp/requirements-dev.txt

# The shared schema. Copied, not bind-mounted, so the image is self-contained and
# still runs on ECS where there are no host mounts.
COPY api/app /opt/api/app

COPY worker/ .

CMD ["arq", "worker.main.WorkerSettings"]


FROM base AS runtime

# Same UID as the api image: both write the shared uploads volume.
RUN useradd --system --uid 10001 --no-create-home app

COPY --from=builder /opt/venv /opt/venv
COPY api/app /opt/api/app
COPY worker/worker ./worker

# The ideation node reads trends.json relative to its own module
# (orchestrator.py, TRENDS_PATH), i.e. /app/data/trends.json. Compose used to
# supply it through the ./data bind mount, which ECS does not have; without
# this line ideation silently runs with no trend signals.
COPY data/trends.json ./data/trends.json

RUN mkdir -p /app/storage && chown app:app /app/storage

USER app

CMD ["arq", "worker.main.WorkerSettings"]
