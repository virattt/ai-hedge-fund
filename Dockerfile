FROM python:3.11-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry==1.7.1

# Copy only dependency files first for better caching
COPY pyproject.toml poetry.lock* /app/

# Configure Poetry to not use a virtual environment
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Copy rest of the source code
COPY . /app/

# Make sure Python can find packages from the root directory
ENV PYTHONPATH=/app

# Default command (will be overridden by Docker Compose)
CMD ["python", "-m", "src.main"] 