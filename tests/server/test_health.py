"""Smoke test for /api/healthz."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_healthz_returns_ok(client: TestClient) -> None:
    response = client.get("/api/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "providers_configured" in body
    # The keys we expose, not whether they have values
    expected = {
        "anthropic",
        "deepseek",
        "google",
        "groq",
        "openai",
        "financial_datasets",
    }
    assert expected <= set(body["providers_configured"].keys())
    assert isinstance(body["db_ok"], bool)
