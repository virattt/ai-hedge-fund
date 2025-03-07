FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    curl \
    git \ 
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 -

ENV PATH="${PATH}:/root/.local/bin"

RUN git clone https://github.com/virattt/ai-hedge-fund.git

WORKDIR /ai-hedge-fund

RUN poetry install
