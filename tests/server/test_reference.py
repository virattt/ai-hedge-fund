"""Reference data endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_analysts_returns_canonical_set(client: TestClient) -> None:
    response = client.get("/api/analysts")
    assert response.status_code == 200
    items = response.json()
    keys = {item["key"] for item in items}
    # Minimum expected set (subset check — resilient to future additions).
    expected_minimum = {
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
        # Added upstream: new analysts
        "aswath_damodaran",
        "michael_burry",
        "peter_lynch",
        "rakesh_jhunjhunwala",
    }
    assert expected_minimum <= keys
    # Order is monotonic, no gaps.
    orders = sorted(item["order"] for item in items)
    assert orders == list(range(len(items)))


def test_list_models_returns_grouped_options(client: TestClient) -> None:
    response = client.get("/api/models")
    assert response.status_code == 200
    items = response.json()
    providers = {item["provider"] for item in items}
    # Core providers that must always be present.
    # Note: upstream renamed "Gemini" → "Google" and added "OpenRouter".
    assert {"Anthropic", "DeepSeek", "Google", "Groq", "OpenAI"} <= providers
    # gpt-4o is canonical default — must be present.
    assert any(item["model_name"] == "gpt-4o" for item in items)
