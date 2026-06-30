# Stage 1: Build frontend
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY app/frontend/package.json app/frontend/package-lock.json* ./
RUN npm install
COPY app/frontend/ ./
ENV VITE_API_URL=""
ENV VITE_BETA_MODE="true"
RUN npm run build

# Stage 2: Python backend + built frontend
FROM python:3.11-slim AS production
WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies via pip (avoid poetry in production)
RUN pip install --no-cache-dir poetry poetry-plugin-export
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --only main --no-root && \
    pip uninstall -y poetry poetry-plugin-export

# Copy application code
COPY app/ ./app/
COPY src/ ./src/
COPY v2/ ./v2/

# Copy built frontend into the expected location
COPY --from=frontend-build /app/frontend/dist ./app/frontend/dist

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

#update fr railway
CMD gunicorn app.backend.main:app -w 1 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 300
