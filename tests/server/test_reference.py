"""Reference data endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_analysts_returns_canonical_set(client: TestClient) -> None:
    response = client.get("/api/analysts")
    assert response.status_code == 200
    items = response.json()
    keys = {item["key"] for item in items}
    expected = {
        "ben_graham",
        "bill_ackman",
        "cathie_wood",
        "charlie_munger",
        "phil_fisher",
        "stanley_druckenmiller",
        "warren_buffett",
        "technical_analyst",
        "fundamentals_analyst",
        "sentiment_analyst",
        "valuation_analyst",
    }
    assert keys == expected
    # Order is monotonic, no gaps.
    orders = sorted(item["order"] for item in items)
    assert orders == list(range(len(items)))


def test_list_models_returns_grouped_options(client: TestClient) -> None:
    response = client.get("/api/models")
    assert response.status_code == 200
    items = response.json()
    providers = {item["provider"] for item in items}
    # All five providers represented.
    assert {"Anthropic", "DeepSeek", "Gemini", "Groq", "OpenAI"} <= providers
    # gpt-4o is canonical default — must be present.
    assert any(item["model_name"] == "gpt-4o" for item in items)
