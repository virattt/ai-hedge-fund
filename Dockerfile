FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false

RUN pip install --no-cache-dir poetry==1.8.5

# Dependencies first for layer caching; the root package is installed after the copy.
COPY pyproject.toml poetry.lock README.md /app/
RUN poetry install --no-interaction --no-ansi --only main --no-root

COPY . /app/
RUN poetry install --no-interaction --no-ansi --only main

# One cycle of the all-analysts mandate; JSON record on stdout, summary on stderr.
# Override CMD to change tickers/mandate, or pass --backtest.
ENTRYPOINT ["aihf"]
CMD ["/app/deploy/mandate.yaml", "--tickers", "AAPL,MSFT,NVDA,GOOGL,TSLA", "--model", "auto"]
