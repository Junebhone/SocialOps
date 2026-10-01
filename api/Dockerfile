# Three stages. The LAST one is the default target, so a plain `docker build`
# (CI, ECR, ECS) produces the lean runtime image; local compose asks for `dev`
# explicitly in docker-compose.override.yml. See D33.
#
#   builder  a virtualenv holding the runtime dependencies, nothing else
#   dev      builder + test/lint tools + the whole source tree, run with --reload
#   runtime  python:3.12-slim + the virtualenv + app/ and alembic/, as non-root

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app


FROM base AS builder

# Dependencies resolve from pyproject.toml alone, so this layer caches across
# source edits. Only the dependency list is installed, not the package itself:
# the source is on PYTHONPATH, which avoids installing a stub `app` package
# into site-packages just to satisfy setuptools.
COPY pyproject.toml ./
RUN python -m venv /opt/venv \
 && python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt \
 && pip install --no-cache-dir -r /tmp/requirements.txt


FROM builder AS dev

RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['optional-dependencies']['dev']))" > /tmp/requirements-dev.txt \
 && pip install --no-cache-dir -r /tmp/requirements-dev.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]


FROM base AS runtime

# A fixed UID, shared with the worker image, so both can write the same
# uploads volume without either running as root.
RUN useradd --system --uid 10001 --no-create-home app

COPY --from=builder /opt/venv /opt/venv

# Only what the process imports or runs. alembic/ and alembic.ini are here
# because `alembic upgrade head` runs from this image (the ECS migrate task).
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

# Owned by the app user so a fresh named volume mounted here inherits it.
RUN mkdir -p /app/storage && chown app:app /app/storage

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
