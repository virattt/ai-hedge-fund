"""NewsAnalystAgent + NewsSnapshot tests — fake LLM and data client, no network."""

import json

import pytest

from hedge_fund.data.client import FDClientError
from hedge_fund.data.models import CompanyNews
from hedge_fund.features.news import build_news_snapshot
from hedge_fund.features.snapshot import InsufficientData
from hedge_fund.llm import PromptCache
from hedge_fund.signals import ALPHA_MODEL_REGISTRY, LLMAgent, NewsAnalystAgent


class FakeLLM:
    model = "fake-model"

    def __init__(self, response=""):
        self._response = response
        self.calls = 0
        self.last_user = None

    def complete(self, system, user):
        self.calls += 1
        self.last_user = user
        return self._response


class MockDataClient:
    def __init__(self, news=None, error=None):
        self._news = news or []
        self._error = error

    def get_news(self, ticker, end_date, start_date=None, limit=1000):
        if self._error is not None:
            raise self._error
        return self._news


def _news(title, date="2025-08-01", source="wire"):
    return CompanyNews(ticker="TEST", title=title, source=source, date=date)


def _feed():
    return [_news("Guidance raised", "2025-08-01"),
            _news("New product launch", "2025-07-30"),
            _news("CFO departs", "2025-07-29")]


BEARISH = json.dumps({"signal": "bearish", "confidence": 70, "reasoning": "CFO exit."})


def _agent(tmp_path, llm, **kw):
    return NewsAnalystAgent(llm=llm, cache=PromptCache(tmp_path / "llm"), **kw)


def test_registered_llm_agent():
    assert ALPHA_MODEL_REGISTRY["news_analyst"] is NewsAnalystAgent
    assert issubclass(NewsAnalystAgent, LLMAgent)


def test_predict_folds_signal_and_prompts_with_headlines(tmp_path):
    llm = FakeLLM(BEARISH)
    sig = _agent(tmp_path, llm).predict("TEST", "2025-08-01", MockDataClient(_feed()))

    assert sig.model_name == "news_analyst"
    assert sig.value == pytest.approx(-0.7)
    assert sig.metadata["abstained"] is False
    assert "Guidance raised" in llm.last_user and "CFO departs" in llm.last_user


def test_unchanged_headlines_hit_cache_across_dates(tmp_path):
    llm = FakeLLM(BEARISH)
    agent = _agent(tmp_path, llm)
    client = MockDataClient(_feed())
    agent.predict("TEST", "2025-08-01", client)
    second = agent.predict("TEST", "2025-08-02", client)   # same headlines, next day
    assert llm.calls == 1
    assert second.metadata["cached"] is True


def test_empty_feed_abstains_without_llm_call(tmp_path):
    llm = FakeLLM(BEARISH)
    sig = _agent(tmp_path, llm).predict("TEST", "2025-08-01", MockDataClient([]))
    assert sig.value == 0.0
    assert sig.metadata["abstained"] is True
    assert llm.calls == 0


def test_data_layer_error_propagates(tmp_path):
    client = MockDataClient(error=FDClientError("API down", status_code=500))
    with pytest.raises(FDClientError):
        _agent(tmp_path, FakeLLM(BEARISH)).predict("TEST", "2025-08-01", client)


class TestNewsSnapshot:
    def test_point_in_time_dedupe_and_order(self):
        client = MockDataClient([
            _news("old", "2025-07-30"),
            _news("new", "2025-08-01"),
            _news("new", "2025-08-01"),            # duplicate
            _news("future", "2025-08-02"),         # lookahead
            _news("stale", "2025-07-01"),          # outside window
            _news("undated", None),
        ])
        snap = build_news_snapshot("TEST", "2025-08-01", client, min_headlines=1)
        assert [h.title for h in snap.headlines] == ["new", "old"]

    def test_too_few_raises_insufficient_data(self):
        with pytest.raises(InsufficientData):
            build_news_snapshot("TEST", "2025-08-01", MockDataClient([_news("a")]))

    def test_hash_and_render_exclude_as_of(self):
        client = MockDataClient(_feed())
        a = build_news_snapshot("TEST", "2025-08-01", client)
        b = build_news_snapshot("TEST", "2025-08-02", client)
        assert a.content_hash == b.content_hash
        assert a.render() == b.render()
        assert "2025-08-02" not in b.render()
