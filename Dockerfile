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

# Default command (will be overridden by Docker Compose)
# Create a non-root user
RUN groupadd -r appuser && useradd -r -g appuser -s /bin/false appuser

# Change ownership of application files to appuser
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser
CMD ["python", "src/main.py"] 