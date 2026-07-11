"""EveillardAgent tests — fake LLM and data client, no network.

Mirrors the BuffettAgent test approach: the LLMAgent machinery is already
covered in test_llm_agents.py, so here we assert only what is specific to this
persona — its name, that it plugs into the shared value-folding contract, and
that its system prompt actually carries Eveillard's philosophy.
"""

import json

import pytest

from v2.data.models import FinancialMetrics
from v2.llm import PromptCache
from v2.models import Signal
from v2.signals import ALPHA_MODEL_REGISTRY, EveillardAgent


class FakeLLM:
    """Canned-response LLM; counts calls."""

    model = "fake-model"

    def __init__(self, response=""):
        self._response = response
        self.calls = 0

    def complete(self, system, user):
        self.calls += 1
        return self._response


class MockDataClient:
    def __init__(self, metrics=None):
        self._metrics = metrics or []

    def get_financial_metrics(self, ticker, end_date, period="ttm", limit=10):
        return self._metrics

    def get_company_facts(self, ticker):
        return None


def _history(n=8):
    quarters = ["2024-12-31", "2024-09-30", "2024-06-30", "2024-03-31",
                "2023-12-31", "2023-09-30", "2023-06-30", "2023-03-31"]
    return [
        FinancialMetrics(
            ticker="TEST", report_period=q, period="ttm", filing_date=q,
            return_on_equity=0.2, gross_margin=0.4, book_value_per_share=10.0,
            market_cap=1e9,
        )
        for q in quarters[:n]
    ]


def _agent(tmp_path, llm):
    return EveillardAgent(llm=llm, cache=PromptCache(tmp_path / "llm"))


def test_registered_in_registry():
    assert ALPHA_MODEL_REGISTRY["eveillard"] is EveillardAgent


def test_name():
    assert EveillardAgent(llm=FakeLLM(), cache=None).name == "eveillard"


def test_system_prompt_is_eveillard():
    prompt = EveillardAgent(llm=FakeLLM(), cache=None).get_system_prompt()
    assert "Eveillard" in prompt
    assert "margin of safety" in prompt.lower()


@pytest.mark.parametrize("signal,confidence,expected", [
    ("bullish", 80, 0.8),
    ("bearish", 60, -0.6),
    ("neutral", 90, 0.0),
])
def test_value_folding(tmp_path, signal, confidence, expected):
    response = json.dumps({"signal": signal, "confidence": confidence, "reasoning": "r"})
    agent = _agent(tmp_path, FakeLLM(response))

    sig = agent.predict("TEST", "2025-01-15", MockDataClient(metrics=_history()))

    assert isinstance(sig, Signal)
    assert sig.model_name == "eveillard"
    assert sig.value == pytest.approx(expected)
    assert sig.metadata["abstained"] is False
