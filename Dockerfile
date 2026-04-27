# syntax=docker/dockerfile:1.7
# Multi-stage build for the ai-hedge-fund FastAPI service.

# ---------- builder ----------
FROM python:3.13-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential curl \
 && rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

COPY pyproject.toml poetry.lock* ./
RUN poetry install --only=main --no-root

COPY src ./src
COPY server ./server
COPY alembic ./alembic
COPY alembic.ini ./

# ---------- runtime ----------
FROM python:3.13-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AHF_DB_URL=sqlite:////data/runs.db \
    AHF_DATA_DIR=/data

# Non-root user
RUN useradd --create-home --shell /bin/bash ahf

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

RUN mkdir -p /data && chown -R ahf:ahf /data /app
USER ahf

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/healthz', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
