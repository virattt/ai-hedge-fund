FROM python:3.11-slim

WORKDIR /app

# Set PYTHONPATH to include the app directory
ENV PYTHONPATH=/app

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

# Create a non-root user to run the applicationnRUN groupadd -r appuser && useradd -r -g appuser appusernn# Change ownership of application files to the new usernRUN chown -R appuser:appuser /app || truenn# Switch to the non-root usernUSER appuser


# Create a non-root user to run the application
RUN groupadd -r -g 1001 appuser && useradd -r -u 1001 -g appuser appuser

# Change ownership of application files to the new user
RUN chown -R appuser:appuser /app || true

# Switch to the non-root user
USER appuser

CMD ["python", "src/main.py"] 
