"""Validation-layer tests for ``POST /api/runs``.

These do *not* invoke the real ``run_hedge_fund`` (that requires LLM API
keys + financialdatasets.ai). They exercise A3 (ticker validation) and date
canonicalization in ``server/schemas.py``.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

_DEFAULT_BODY = {
    "tickers": ["AAPL"],
    "selected_analysts": ["technical_analyst"],
    "model_name": "gpt-4o",
    "model_provider": "OpenAI",
}


def test_rejects_invalid_ticker(client: TestClient) -> None:
    body = {**_DEFAULT_BODY, "tickers": ["AAPL\nBREAKOUT"]}
    response = client.post("/api/runs", json=body)
    assert response.status_code == 422
    assert "invalid ticker symbol" in response.text


def test_rejects_lowercase_garbage_ticker(client: TestClient) -> None:
    body = {**_DEFAULT_BODY, "tickers": ["???"]}
    response = client.post("/api/runs", json=body)
    assert response.status_code == 422


def test_accepts_dotted_and_dashed_tickers(client: TestClient, monkeypatch) -> None:
    """BRK.B, RDS-A etc. are real symbols; must not be rejected by validation."""
    # Stub the actual run executor so we don't hit LLMs.
    from server.services import run_service

    async def _fake_execute(req, session):  # noqa: ARG001
        from datetime import UTC, datetime

        from server.schemas import RunSummary

        return RunSummary(
            id="stub",
            status="done",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            duration_ms=1,
            config=req,
        )

    monkeypatch.setattr(run_service, "execute_analyze_run", _fake_execute)
    # Re-import so the patched symbol is resolved on the route.
    monkeypatch.setattr("server.api.runs.execute_analyze_run", run_service.execute_analyze_run)

    body = {**_DEFAULT_BODY, "tickers": ["BRK.B", "RDS-A"]}
    response = client.post("/api/runs", json=body)
    assert response.status_code == 201, response.text


def test_rejects_inverted_date_range(client: TestClient) -> None:
    body = {**_DEFAULT_BODY, "start_date": "2025-12-31", "end_date": "2024-01-01"}
    response = client.post("/api/runs", json=body)
    assert response.status_code == 422
    assert "start_date must not be after end_date" in response.text


def test_rejects_malformed_date(client: TestClient) -> None:
    body = {**_DEFAULT_BODY, "start_date": "not-a-date"}
    response = client.post("/api/runs", json=body)
    assert response.status_code == 422
