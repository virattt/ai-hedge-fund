FROM python:3.11-slim

WORKDIR /app

# Set PYTHONPATH to include the app directory
ENV PYTHONPATH=/app

# Install Poetry
RUN pip install poetry==1.7.1

# Copy only dependency files first for better caching
COPY ../pyproject.toml ../poetry.lock* /app/

# Configure Poetry to not use a virtual environment
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Copy rest of the source code
COPY ../ /app/

# Default command (will be overridden by Docker Compose)
CMD ["python", "src/main.py"] 
