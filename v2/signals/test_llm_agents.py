"""LLMAgent + BuffettAgent tests — fake LLM and data client, no network."""

import json

import pytest

from v2.data.client import FDClientError
from v2.data.models import FinancialMetrics
from v2.llm import PromptCache, extract_json
from v2.llm.client import LLMParseError
from v2.models import Signal
from v2.signals import BuffettAgent


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeLLM:
    """Canned-response LLM; counts calls; can raise instead."""

    model = "fake-model"

    def __init__(self, response="", error=None):
        self._response = response
        self._error = error
        self.calls = 0

    def complete(self, system, user):
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._response


class MockDataClient:
    def __init__(self, metrics=None, error=None):
        self._metrics = metrics or []
        self._error = error

    def get_financial_metrics(self, ticker, end_date, period="ttm", limit=10):
        if self._error is not None:
            raise self._error
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


BULLISH = json.dumps({"signal": "bullish", "confidence": 80, "reasoning": "Wonderful business."})


def _agent(tmp_path, llm):
    return BuffettAgent(llm=llm, cache=PromptCache(tmp_path / "llm"))


# ---------------------------------------------------------------------------
# Signal folding
# ---------------------------------------------------------------------------

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
    assert sig.model_name == "buffett"
    assert sig.value == pytest.approx(expected)
    assert sig.metadata["abstained"] is False


# ---------------------------------------------------------------------------
# Failure contract
# ---------------------------------------------------------------------------

def test_malformed_json_abstains(tmp_path):
    agent = _agent(tmp_path, FakeLLM("I am bullish, trust me."))
    sig = agent.predict("TEST", "2025-01-15", MockDataClient(metrics=_history()))
    assert sig.value == 0.0
    assert sig.metadata["abstained"] is True


def test_llm_error_abstains(tmp_path):
    agent = _agent(tmp_path, FakeLLM(error=TimeoutError("llm timed out")))
    sig = agent.predict("TEST", "2025-01-15", MockDataClient(metrics=_history()))
    assert sig.value == 0.0
    assert sig.metadata["abstained"] is True
    assert "timed out" in sig.metadata["abstain_reason"]


def test_insufficient_data_abstains(tmp_path):
    agent = _agent(tmp_path, FakeLLM(BULLISH))
    sig = agent.predict("TEST", "2025-01-15", MockDataClient(metrics=_history(2)))
    assert sig.value == 0.0
    assert sig.metadata["abstained"] is True


def test_data_layer_error_propagates(tmp_path):
    """Fail loud: an infrastructure failure must NOT become a neutral view."""
    client = MockDataClient(error=FDClientError("API down", status_code=500))
    agent = _agent(tmp_path, FakeLLM(BULLISH))
    with pytest.raises(FDClientError):
        agent.predict("TEST", "2025-01-15", client)


# ---------------------------------------------------------------------------
# Cache = persistence
# ---------------------------------------------------------------------------

def test_cache_hit_skips_llm_call(tmp_path):
    llm = FakeLLM(BULLISH)
    client = MockDataClient(metrics=_history())
    agent = _agent(tmp_path, llm)

    first = agent.predict("TEST", "2025-01-15", client)
    second = agent.predict("TEST", "2025-01-15", client)

    assert llm.calls == 1  # second predict served from cache
    assert first.value == second.value
    assert first.metadata["cached"] is False
    assert second.metadata["cached"] is True


def test_new_as_of_same_data_hits_cache(tmp_path):
    """A new date with unchanged fundamentals must be free: the snapshot
    renders identically, so the prompt cache hits — no second LLM call."""
    llm = FakeLLM(BULLISH)
    client = MockDataClient(metrics=_history())
    agent = _agent(tmp_path, llm)

    first = agent.predict("TEST", "2025-01-15", client)
    second = agent.predict("TEST", "2025-02-20", client)

    assert llm.calls == 1
    assert second.metadata["cached"] is True
    assert second.date == "2025-02-20"  # Signal date is the predict arg, not the cache's
    assert first.metadata["snapshot_hash"] == second.metadata["snapshot_hash"]


def test_new_filing_forces_new_llm_call(tmp_path):
    """A new filing changes the snapshot — the agent must re-reason."""
    llm = FakeLLM(BULLISH)
    agent = _agent(tmp_path, llm)

    first = agent.predict("TEST", "2025-01-15", MockDataClient(metrics=_history(7)))
    second = agent.predict("TEST", "2025-02-20", MockDataClient(metrics=_history(8)))

    assert llm.calls == 2
    assert first.metadata["snapshot_hash"] != second.metadata["snapshot_hash"]


def test_prompt_and_response_persisted(tmp_path):
    agent = _agent(tmp_path, FakeLLM(BULLISH))
    agent.predict("TEST", "2025-01-15", MockDataClient(metrics=_history()))

    records = list((tmp_path / "llm").glob("*.json"))
    assert len(records) == 1
    record = json.loads(records[0].read_text())
    assert record["agent"] == "buffett"
    assert "You are Warren Buffett" in record["system"]
    assert "2024-12-31" in record["user"]  # the rendered snapshot
    assert record["response"] == BULLISH
    assert record["parsed"]["signal"] == "bullish"


def test_failed_parse_still_persists_response(tmp_path):
    agent = _agent(tmp_path, FakeLLM("garbage"))
    agent.predict("TEST", "2025-01-15", MockDataClient(metrics=_history()))

    records = list((tmp_path / "llm").glob("*.json"))
    assert len(records) == 1
    record = json.loads(records[0].read_text())
    assert record["response"] == "garbage"
    assert "parse_error" in record


# ---------------------------------------------------------------------------
# extract_json
# ---------------------------------------------------------------------------

def test_extract_json_fenced():
    assert extract_json('here:\n```json\n{"a": 1}\n```\ndone') == {"a": 1}


def test_extract_json_bare():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_embedded():
    assert extract_json('Sure! {"a": {"b": 2}} hope that helps') == {"a": {"b": 2}}


def test_extract_json_raises_on_garbage():
    with pytest.raises(LLMParseError):
        extract_json("no json here at all")
