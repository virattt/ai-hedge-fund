FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Install Poetry
RUN pip install --no-cache-dir poetry==1.8.3
RUN poetry config virtualenvs.create false

# Install dependencies (layer cached)
COPY pyproject.toml poetry.lock* /app/
RUN poetry install --no-interaction --no-ansi --no-root

# Copy source code
COPY src/ /app/src/
COPY v2/ /app/v2/
COPY app/ /app/app/

EXPOSE 8000

CMD ["uvicorn", "app.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
