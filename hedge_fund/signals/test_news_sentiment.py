"""Tests for NewsSentimentModel — scorer injected, no FinBERT or API calls."""

from __future__ import annotations

import pytest

from hedge_fund.data.models import CompanyNews
from hedge_fund.signals import ALPHA_MODEL_REGISTRY, NewsSentimentModel, QuantModel
from hedge_fund.signals.news_sentiment import _label_score


class MockFDClient:
    """Returns canned news and records the requested window."""

    def __init__(self, news=None):
        self._news = news or []
        self.calls = []

    def get_news(self, ticker, end_date, start_date=None, limit=1000):
        self.calls.append((ticker, end_date, start_date, limit))
        return self._news


def _news(title, date="2025-08-01"):
    return CompanyNews(ticker="TEST", title=title, source="wire", date=date)


def _keyword_scorer(titles):
    """+1 for 'beat', -1 for 'miss', else 0 — stands in for FinBERT."""
    return [1.0 if "beat" in t else -1.0 if "miss" in t else 0.0 for t in titles]


def _model(**kw):
    return NewsSentimentModel(scorer=_keyword_scorer, **kw)


class TestInterface:
    def test_is_quant_model_and_registered(self):
        assert issubclass(NewsSentimentModel, QuantModel)
        assert ALPHA_MODEL_REGISTRY["news_sentiment"] is NewsSentimentModel
        assert NewsSentimentModel(scorer=_keyword_scorer).name == "news_sentiment"

    def test_label_score(self):
        probs = [{"label": "positive", "score": 0.7},
                 {"label": "negative", "score": 0.1},
                 {"label": "neutral", "score": 0.2}]
        assert _label_score(probs) == pytest.approx(0.6)


class TestPredict:
    def test_positive_news_is_bullish(self):
        fd = MockFDClient([_news("a beat"), _news("b beat"), _news("c beat")])
        sig = _model().predict("TEST", "2025-08-01", fd)
        assert sig.value == 1.0
        assert sig.model_name == "news_sentiment"
        assert sig.metadata["articles"] == 3
        assert "abstained" not in sig.metadata

    def test_negative_news_is_bearish(self):
        fd = MockFDClient([_news("a miss"), _news("b miss"), _news("c miss")])
        assert _model().predict("TEST", "2025-08-01", fd).value == -1.0

    def test_mixed_news_averages(self):
        fd = MockFDClient([_news("a beat"), _news("b beat"), _news("c miss"), _news("d flat")])
        sig = _model().predict("TEST", "2025-08-01", fd)
        assert sig.value == pytest.approx(0.25)
        assert sig.metadata["positive"] == 2 and sig.metadata["negative"] == 1

    def test_requests_lookback_window(self):
        fd = MockFDClient()
        _model(lookback_days=7).predict("TEST", "2025-08-08", fd)
        assert fd.calls == [("TEST", "2025-08-08", "2025-08-01", 100)]


class TestAbstain:
    def test_empty_feed_abstains(self):
        sig = _model().predict("TEST", "2025-08-01", MockFDClient([]))
        assert sig.value == 0.0
        assert sig.metadata["abstained"] is True

    def test_below_min_articles_abstains(self):
        fd = MockFDClient([_news("a beat"), _news("b beat")])
        sig = _model(min_articles=3).predict("TEST", "2025-08-01", fd)
        assert sig.value == 0.0 and sig.metadata["abstained"] is True


class TestPointInTime:
    def test_future_and_stale_and_undated_dropped(self):
        fd = MockFDClient([
            _news("in window beat", "2025-08-01"),
            _news("future miss", "2025-08-02"),    # after as_of: lookahead
            _news("stale miss", "2025-07-01"),     # before the window
            _news("undated miss", None),
        ])
        sig = _model(min_articles=1).predict("TEST", "2025-08-01", fd)
        assert sig.metadata["articles"] == 1
        assert sig.value == 1.0

    def test_duplicate_titles_counted_once(self):
        fd = MockFDClient([_news("same beat"), _news("same beat"), _news("other miss")])
        sig = _model(min_articles=1).predict("TEST", "2025-08-01", fd)
        assert sig.metadata["articles"] == 2


class TestScoreCache:
    def test_each_headline_scored_once(self):
        seen = []

        def scorer(titles):
            seen.extend(titles)
            return [0.5] * len(titles)

        model = NewsSentimentModel(scorer=scorer, min_articles=1)
        fd = MockFDClient([_news("x"), _news("y")])
        model.predict("TEST", "2025-08-01", fd)
        model.predict("TEST", "2025-08-02", fd)
        assert sorted(seen) == ["x", "y"]


def test_missing_finbert_raises_clear_error(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "transformers":
            raise ImportError("no transformers")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    fd = MockFDClient([_news("a"), _news("b"), _news("c")])
    with pytest.raises(ImportError, match="pip install transformers torch"):
        NewsSentimentModel().predict("TEST", "2025-08-01", fd)
