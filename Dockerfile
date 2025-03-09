# Use Python 3.10 slim image as base
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Copy requirements first to leverage Docker cache
# Copy source code
COPY src/ src/
COPY .env .
COPY .gitignore .
COPY README.md .
COPY LICENSE .
COPY pyproject.toml .

# Install Python dependencies
RUN poetry install

# Set environment variable for Python to run in unbuffered mode
ENV PYTHONUNBUFFERED=1

# Set default command with -u flag for unbuffered output
ENTRYPOINT ["poetry", "run", "python", "-u", "src/main.py"]
CMD ["--ticker", "AAPL,MSFT,NVDA"]  # Optional default arguments