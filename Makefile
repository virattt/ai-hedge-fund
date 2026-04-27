.PHONY: help install dev api test lint format typecheck ci docker-build docker-up docker-down clean

UV := $(shell command -v uv 2>/dev/null || echo "${HOME}/.local/bin/uv")
RUN := $(UV) run

help:
	@echo "ai-hedge-fund — common dev tasks"
	@echo ""
	@echo "  make install         Sync Python deps via uv"
	@echo "  make dev             Run uvicorn with --reload on :8000"
	@echo "  make api             Run uvicorn (no reload)"
	@echo "  make test            Run pytest"
	@echo "  make lint            ruff check"
	@echo "  make format          ruff format"
	@echo "  make typecheck       mypy on server/"
	@echo "  make ci              lint + typecheck + test"
	@echo "  make docker-build    Build the Docker image"
	@echo "  make docker-up       Bring up the API container"
	@echo "  make docker-down     Stop the API container"
	@echo "  make clean           Remove build artifacts and test caches"

install:
	$(UV) sync --extra dev --python 3.13

dev:
	$(RUN) uvicorn server.main:app --reload --host 127.0.0.1 --port 8000

api:
	$(RUN) uvicorn server.main:app --host 0.0.0.0 --port 8000

test:
	$(RUN) pytest -q

lint:
	$(RUN) ruff check .

format:
	$(RUN) ruff format .
	$(RUN) ruff check --fix .

typecheck:
	$(RUN) mypy server

ci: lint typecheck test

docker-build:
	docker build -t ai-hedge-fund:dev .

docker-up:
	docker compose up -d

docker-down:
	docker compose down

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
