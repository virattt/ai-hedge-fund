FROM python:3.10-slim-bullseye

WORKDIR /app

# Install system dependencies (if needed by your packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Add poetry to PATH
ENV PATH="/root/.local/bin:$PATH"

# Copy project files
COPY pyproject.toml poetry.lock .env ./
COPY ./src .

# Install project dependencies
RUN poetry install --no-root --no-interaction --no-ansi

# Set the entrypoint

ENTRYPOINT  ["/bin/bash"]


