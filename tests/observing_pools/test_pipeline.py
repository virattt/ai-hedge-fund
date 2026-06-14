"""Integration test for the refresh pipeline with a stubbed analyst committee.

No LLM calls, no network — the stub returns deterministic signals so we can
assert ranking order, the REQUIRED-floor exclusion, persistence of the
reproducible breakdown, the loud cost ceiling, and dry-run no-op behavior.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.storage.models as m
from src.observing_pools.agents_bridge import COMPONENT_ANALYST_KEYS
from src.observing_pools.pipeline import RefreshConfig, refresh_pool

UNIVERSE = "data/universes/ai_seed.csv"
_VALUE_KEYS = set(COMPONENT_ANALYST_KEYS["value_investor"])


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    m.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_stub(quality: dict[str, int], drop_value_for: frozenset[str] = frozenset()):
    """Deterministic run_analysts: all-bullish at per-ticker confidence=quality.

    Omitting the value-investor agents for a ticker leaves value_investor=None →
    composite None → data_unavailable (tests the REQUIRED floor).
    """

    def stub(tickers, selected, end_date):
        signals: dict[str, dict] = {f"{k}_agent": {} for k in selected}
        for t in tickers:
            q = quality.get(t, 50)
            for k in selected:
                if t in drop_value_for and k in _VALUE_KEYS:
                    continue
                signals[f"{k}_agent"][t] = {"signal": "bullish", "confidence": q, "reasoning": "stub"}
        return signals, {"calls": len(selected) * len(tickers)}

    return stub


def test_refresh_ranks_and_persists(session):
    stub = make_stub(quality={"NVDA": 90, "MSFT": 80, "GOOGL": 70}, drop_value_for=frozenset({"AI"}))
    config = RefreshConfig(platform_key="ai", universe_csv=UNIVERSE, top_n=5, token_budget=10_000)

    run = refresh_pool(session, config, stub, end_date="2026-06-12")
    session.commit()

    assert run.status == m.RefreshRunStatus.COMPLETE.value
    assert run.candidate_count == 25  # all AI-labeled seeds

    ranked = session.query(m.ObservationPoolEntry).filter(m.ObservationPoolEntry.rank.isnot(None)).order_by(m.ObservationPoolEntry.rank).all()
    assert len(ranked) == 5  # top_n
    assert [e.ticker for e in ranked[:3]] == ["NVDA", "MSFT", "GOOGL"]  # higher confidence ranks higher
    assert ranked[0].rank == 1

    # Reproducible breakdown + formula version persisted (PRD B3).
    top = ranked[0]
    assert top.composite_formula_version == "v3-4comp"
    assert top.score_breakdown["formula_version"] == "v3-4comp"
    assert "serenity_bottleneck" not in top.score_breakdown.get("weights", {})  # excluded in 4comp
    assert top.value_investor_score is not None and top.innovation_growth_score is not None

    # The ticker with no value-investor signals is excluded, not scored 0 (REQUIRED floor).
    ai_entry = session.query(m.ObservationPoolEntry).filter_by(ticker="AI", platform_key="ai").one()
    assert ai_entry.status == m.PoolEntryStatus.DATA_UNAVAILABLE.value
    assert ai_entry.composite_score is None and ai_entry.rank is None


def test_cost_ceiling_marks_partial(session):
    stub = make_stub(quality={"NVDA": 90})
    # committee(16) * 25 tickers = 400 calls; budget 10 → breach.
    config = RefreshConfig(platform_key="ai", universe_csv=UNIVERSE, top_n=5, token_budget=10)
    run = refresh_pool(session, config, stub, end_date="2026-06-12")
    session.commit()
    assert run.status == m.RefreshRunStatus.PARTIAL.value
    assert "token budget exceeded" in (run.error or "")


def test_dry_run_mutates_nothing(session):
    stub = make_stub(quality={"NVDA": 90})
    config = RefreshConfig(platform_key="ai", universe_csv=UNIVERSE, top_n=5, dry_run=True)
    run = refresh_pool(session, config, stub, end_date="2026-06-12")
    session.commit()
    assert run.id is None  # never added to the session
    assert session.query(m.ObservationPoolEntry).count() == 0
    assert session.query(m.CandidateSecurity).count() == 0
