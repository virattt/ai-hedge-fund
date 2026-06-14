"""A provider fetch error degrades an analyst (node-boundary handler); the refresh
run must record it in ``fetch_errors`` and be marked PARTIAL — never silently
COMPLETE with an analyst missing (PRD v4 §8.2 feature-level recording).
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.storage.models as m
from src.observing_pools.pipeline import RefreshConfig, refresh_pool

UNIVERSE = "data/universes/ai_seed.csv"


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    m.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_degraded_analysts_recorded_and_partial(session):
    def stub(tickers, selected, end_date):
        signals = {f"{k}_agent": {} for k in selected}
        for t in tickers:
            for k in selected:
                signals[f"{k}_agent"][t] = {"signal": "bullish", "confidence": 80, "reasoning": "x"}
        # One analyst hit a provider fetch error during the run.
        return signals, {"calls": 1, "degraded_analysts": ["michael_burry_agent"]}

    config = RefreshConfig(platform_key="ai", universe_csv=UNIVERSE, top_n=5, token_budget=10_000)
    run = refresh_pool(session, config, stub, end_date="2026-06-12")
    session.commit()

    assert run.status == m.RefreshRunStatus.PARTIAL.value
    assert run.fetch_errors == {"degraded_analysts": ["michael_burry_agent"]}


def test_no_degraded_stays_complete(session):
    def stub(tickers, selected, end_date):
        signals = {f"{k}_agent": {} for k in selected}
        for t in tickers:
            for k in selected:
                signals[f"{k}_agent"][t] = {"signal": "bullish", "confidence": 80, "reasoning": "x"}
        return signals, {"calls": 1}  # no degraded_analysts key

    config = RefreshConfig(platform_key="ai", universe_csv=UNIVERSE, top_n=5, token_budget=10_000)
    run = refresh_pool(session, config, stub, end_date="2026-06-12")
    session.commit()

    assert run.status == m.RefreshRunStatus.COMPLETE.value
    assert run.fetch_errors is None
