# AI Hedge Fund Web App - Docker Image
# Supports both frontend (React/Vite) and backend (FastAPI)

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends \
    nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==1.8.3

# Configure Poetry: no virtualenv inside container
RUN poetry config virtualenvs.create false

# Copy dependency files first for better Docker layer caching
COPY pyproject.toml poetry.lock* ./

# Install Python dependencies
RUN poetry install --no-interaction --no-ansi --no-root

# Copy the entire project
COPY . .

# Install frontend dependencies
WORKDIR /app/app/frontend
RUN npm install

# Return to project root
WORKDIR /app

# Expose ports
# 8000: FastAPI backend
# 5173: Vite frontend dev server
EXPOSE 8000 5173

# Environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Copy and set entrypoint
COPY app/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
