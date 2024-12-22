FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 -

ENV PATH="${PATH}:/root/.local/bin"

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN poetry config virtualenvs.create false

RUN poetry install --no-dev

COPY .env* ./

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default to showing help for agents.py
CMD ["python", "src/agents.py", "--help"]
