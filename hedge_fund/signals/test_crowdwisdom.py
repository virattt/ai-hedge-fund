"""CrowdWisdomModel tests: fake session, no network, no payment."""
from __future__ import annotations

from typing import Any

from hedge_fund.models import Signal
from hedge_fund.signals.crowdwisdom import CrowdWisdomModel


class _Response:
    def __init__(self, status: int, body: Any) -> None:
        self.status_code = status
        self._body = body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        return self._body


class _Session:
    def __init__(self, body: Any, status: int = 200) -> None:
        self.body = body
        self.status = status
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, params: Any = None, headers: Any = None, timeout: Any = None, **kwargs: Any) -> _Response:
        self.calls.append({"url": url, "params": params})
        return _Response(self.status, self.body)


def _body(value: float, session_day: str) -> dict[str, Any]:
    return {
        "data": {
            "ticker": "NVDA",
            "value": value,
            "ProCrowdSentimentScore": value * 100,
            "direction": "BULLISH" if value > 0 else "BEARISH",
            "confidence": 70,
            "session": {"date": session_day, "cycle": "daily"},
            "mentions": {"youtube": 2, "x": 8, "reddit": 0, "total": 10},
            "sources": {"youtube": 80.0, "x": 20.0, "reddit": None},
            "ProTraders": {"youtube": 3, "x": 9, "total": 12},
        },
        "as_of": session_day,
    }


def test_predict_uses_only_sessions_on_or_before_date(tmp_path, monkeypatch):
    import hedge_fund.signals.crowdwisdom as crowd

    monkeypatch.setattr(crowd, "CROWD_CACHE_DIR", tmp_path)
    session = _Session(_body(0.32, "2026-11-03"))
    model = CrowdWisdomModel(session=session)
    signal = model.predict("NVDA", "2026-11-04", data_client=None)
    assert isinstance(signal, Signal)
    assert session.calls[0]["params"] == {"as_of": "2026-11-04"}
    assert session.calls[0]["url"].endswith("/x402/consensus/NVDA")
    assert signal.value == 0.32 and signal.metadata["as_of"] == "2026-11-03"
    assert signal.components == {"youtube": 0.8, "x": 0.2}
    assert signal.horizon_days == 5
    assert signal.metadata["ProTraders"] == 12
    assert "ProCrowdSentimentScore +32" in signal.reasoning and "12 ProTraders" in signal.reasoning
    # cached: second call pays nothing
    model.predict("NVDA", "2026-11-04", data_client=None)
    assert len(session.calls) == 1


def test_abstains_when_stale_or_unavailable(tmp_path, monkeypatch):
    import hedge_fund.signals.crowdwisdom as crowd

    monkeypatch.setattr(crowd, "CROWD_CACHE_DIR", tmp_path)
    stale = CrowdWisdomModel(session=_Session(_body(0.5, "2026-10-01"))).predict("NVDA", "2026-11-04", None)
    assert stale.value == 0.0 and stale.metadata["abstained"] is True
    down = CrowdWisdomModel(session=_Session({}, status=503)).predict("NVDA", "2026-11-04", None)
    assert down.value == 0.0 and down.metadata["abstained"] is True


def test_registry_contract():
    assert CrowdWisdomModel().name == "crowdwisdom"
    assert vars(CrowdWisdomModel)["investment_approach"] == "long_short"
    assert vars(CrowdWisdomModel)["horizon_days"] == 5
