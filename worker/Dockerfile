FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies resolve from pyproject.toml alone, so this layer caches across source edits.
COPY pyproject.toml ./
RUN mkdir -p worker && touch worker/__init__.py && pip install --no-cache-dir -e ".[dev]"

COPY . .

CMD ["arq", "worker.main.WorkerSettings"]
