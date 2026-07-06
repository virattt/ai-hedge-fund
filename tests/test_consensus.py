"""Tests for the consensus aggregation module."""

import pytest

from src.consensus.models import AgentContribution, ConsensusSignal, ConsensusResult
from src.consensus.aggregation import (
    aggregate_signals,
    compute_agreement,
    detect_outliers,
    build_consensus_result,
    _signal_to_numeric,
    _numeric_to_signal,
)


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def unanimous_bullish():
    """All agents agree — bullish."""
    return [
        AgentContribution(agent_name="buffett", signal="bullish", confidence=90, reasoning="Great moat"),
        AgentContribution(agent_name="munger", signal="bullish", confidence=85, reasoning="Fair price"),
        AgentContribution(agent_name="lynch", signal="bullish", confidence=80, reasoning="Growth story"),
    ]


@pytest.fixture
def unanimous_bearish():
    """All agents agree — bearish."""
    return [
        AgentContribution(agent_name="buffett", signal="bearish", confidence=70, reasoning="Overvalued"),
        AgentContribution(agent_name="burry", signal="bearish", confidence=95, reasoning="Bubble"),
        AgentContribution(agent_name="taleb", signal="bearish", confidence=90, reasoning="Tail risk"),
    ]


@pytest.fixture
def mixed_signals():
    """Agents disagree — bullish vs bearish split."""
    return [
        AgentContribution(agent_name="wood", signal="bullish", confidence=80, reasoning="Innovation"),
        AgentContribution(agent_name="buffett", signal="bearish", confidence=75, reasoning="Overvalued"),
        AgentContribution(agent_name="burry", signal="bearish", confidence=90, reasoning="Crash coming"),
    ]


@pytest.fixture
def neutral_mixed():
    """Mix with neutral signals."""
    return [
        AgentContribution(agent_name="damodaran", signal="neutral", confidence=60, reasoning="Fairly priced"),
        AgentContribution(agent_name="munger", signal="bullish", confidence=50, reasoning="OK value"),
        AgentContribution(agent_name="taleb", signal="neutral", confidence=70, reasoning="Uncertain"),
    ]


# ── signal_to_numeric / numeric_to_signal ──────────────────────────

def test_signal_to_numeric_bullish():
    assert _signal_to_numeric("bullish") == 1.0
    assert _signal_to_numeric("BULLISH") == 1.0


def test_signal_to_numeric_bearish():
    assert _signal_to_numeric("bearish") == -1.0


def test_signal_to_numeric_neutral():
    assert _signal_to_numeric("neutral") == 0.0
    assert _signal_to_numeric("unknown") == 0.0


def test_numeric_to_signal():
    assert _numeric_to_signal(0.8) == "bullish"
    assert _numeric_to_signal(-0.9) == "bearish"
    assert _numeric_to_signal(0.0) == "neutral"
    assert _numeric_to_signal(0.15) == "neutral"  # within deadband


# ── aggregate_signals ──────────────────────────────────────────────

class TestAggregateWeighted:
    """Weighted strategy: signal × confidence weighted average."""

    def test_unanimous_bullish(self, unanimous_bullish):
        result = aggregate_signals(unanimous_bullish, strategy="weighted")
        assert result.signal == "bullish"
        assert result.score > 0.5
        assert result.agreement > 0.9
        assert len(result.outliers) == 0

    def test_unanimous_bearish(self, unanimous_bearish):
        result = aggregate_signals(unanimous_bearish, strategy="weighted")
        assert result.signal == "bearish"
        assert result.score < -0.5
        assert result.agreement > 0.9

    def test_mixed_signals(self, mixed_signals):
        result = aggregate_signals(mixed_signals, strategy="weighted")
        # Bearish camp has higher total confidence (75+90 > 80)
        assert result.signal == "bearish"
        assert result.score < 0
        # Disagreement should lower agreement
        assert result.agreement < 0.6

    def test_neutral_mixed(self, neutral_mixed):
        result = aggregate_signals(neutral_mixed, strategy="weighted")
        # With one bullish at low confidence and two neutrals → neutral or slight bullish
        assert result.signal in ("neutral", "bullish")
        assert -0.3 < result.score < 0.6

    def test_single_agent(self):
        contributions = [AgentContribution(agent_name="buffett", signal="bullish", confidence=100)]
        result = aggregate_signals(contributions, strategy="weighted")
        assert result.signal == "bullish"
        assert result.agreement == 1.0  # single agent = full agreement

    def test_empty_contributions_raises(self):
        with pytest.raises(ValueError, match="At least one agent contribution"):
            aggregate_signals([], strategy="weighted")


class TestAggregateMajority:
    """Majority vote: pick the signal with most votes."""

    def test_bullish_majority(self):
        contribs = [
            AgentContribution(agent_name="a", signal="bullish", confidence=50),
            AgentContribution(agent_name="b", signal="bullish", confidence=30),
            AgentContribution(agent_name="c", signal="bearish", confidence=90),
        ]
        result = aggregate_signals(contribs, strategy="majority")
        assert result.signal == "bullish"  # 2/3 bullish

    def test_bearish_majority(self):
        contribs = [
            AgentContribution(agent_name="a", signal="bearish", confidence=50),
            AgentContribution(agent_name="b", signal="bearish", confidence=50),
            AgentContribution(agent_name="c", signal="bullish", confidence=50),
            AgentContribution(agent_name="d", signal="neutral", confidence=50),
        ]
        result = aggregate_signals(contribs, strategy="majority")
        assert result.signal == "bearish"


class TestAggregateMean:
    """Simple average of numeric signals."""

    def test_all_bullish(self, unanimous_bullish):
        result = aggregate_signals(unanimous_bullish, strategy="mean")
        assert result.signal == "bullish"
        assert result.score == 1.0

    def test_two_bearish_one_bullish(self):
        contribs = [
            AgentContribution(agent_name="a", signal="bearish", confidence=50),
            AgentContribution(agent_name="b", signal="bearish", confidence=50),
            AgentContribution(agent_name="c", signal="bullish", confidence=50),
        ]
        result = aggregate_signals(contribs, strategy="mean")
        assert result.signal == "bearish"
        assert result.score == pytest.approx(-0.3333, abs=0.01)


# ── compute_agreement ──────────────────────────────────────────────

def test_agreement_perfect_unanimous(unanimous_bullish):
    assert compute_agreement(unanimous_bullish) > 0.95


def test_agreement_total_disagreement():
    """Half bullish, half bearish = max disagreement."""
    contribs = [
        AgentContribution(agent_name="a", signal="bullish", confidence=50),
        AgentContribution(agent_name="b", signal="bearish", confidence=50),
    ]
    assert compute_agreement(contribs) == 0.0


def test_agreement_single_agent():
    contribs = [AgentContribution(agent_name="a", signal="bullish", confidence=50)]
    assert compute_agreement(contribs) == 1.0


def test_agreement_majority_strategy():
    contribs = [
        AgentContribution(agent_name="a", signal="bullish", confidence=50),
        AgentContribution(agent_name="b", signal="bullish", confidence=50),
        AgentContribution(agent_name="c", signal="bearish", confidence=50),
    ]
    assert compute_agreement(contribs, strategy="majority") == pytest.approx(2 / 3, abs=0.01)


# ── detect_outliers ────────────────────────────────────────────────

def test_no_outliers_when_unanimous(unanimous_bullish):
    assert detect_outliers(unanimous_bullish) == []


def test_no_outliers_with_two_agents():
    """Need at least 3 agents to detect outliers."""
    contribs = [
        AgentContribution(agent_name="a", signal="bullish", confidence=50),
        AgentContribution(agent_name="b", signal="bearish", confidence=50),
    ]
    assert detect_outliers(contribs) == []


def test_outlier_detected():
    """One bear among many bulls should be flagged."""
    contribs = [
        AgentContribution(agent_name="bull1", signal="bullish", confidence=80),
        AgentContribution(agent_name="bull2", signal="bullish", confidence=75),
        AgentContribution(agent_name="bull3", signal="bullish", confidence=70),
        AgentContribution(agent_name="bear", signal="bearish", confidence=60),
        AgentContribution(agent_name="bull4", signal="bullish", confidence=65),
    ]
    outliers = detect_outliers(contribs)
    assert "bear" in outliers
    # All bulls should NOT be outliers
    for name in ["bull1", "bull2", "bull3", "bull4"]:
        assert name not in outliers


def test_no_outlier_when_balanced(mixed_signals):
    """With a balanced split, no clear outlier."""
    outliers = detect_outliers(mixed_signals)
    assert len(outliers) == 0


# ── Agent weights ──────────────────────────────────────────────────

def test_agent_weights():
    """Custom weights should influence the consensus."""
    contribs = [
        AgentContribution(agent_name="buffett", signal="bullish", confidence=40),
        AgentContribution(agent_name="burry", signal="bearish", confidence=90),
    ]
    # Without weights: bearish wins (90 vs 40 → score ≈ -0.38, clearly bearish)
    no_weight = aggregate_signals(contribs, strategy="weighted")
    assert no_weight.signal == "bearish"
    assert no_weight.score < -0.2

    # With Buffett 10x weight: bullish now dominates
    weighted = aggregate_signals(contribs, strategy="weighted", weights={"buffett": 10.0, "burry": 1.0})
    assert weighted.signal == "bullish"
    assert weighted.score > 0.2


# ── build_consensus_result ─────────────────────────────────────────

def test_build_consensus_result_multiple_tickers():
    signals_by_ticker = {
        "AAPL": [
            AgentContribution(agent_name="buffett", signal="bullish", confidence=80),
            AgentContribution(agent_name="munger", signal="bullish", confidence=75),
        ],
        "TSLA": [
            AgentContribution(agent_name="wood", signal="bullish", confidence=90),
            AgentContribution(agent_name="burry", signal="bearish", confidence=95),
        ],
    }
    result = build_consensus_result(signals_by_ticker, strategy="weighted")

    assert len(result.signals) == 2
    assert result.signals["AAPL"].signal == "bullish"
    assert result.signals["AAPL"].agreement > 0.9
    assert result.signals["AAPL"].confidence > 70

    assert result.signals["TSLA"].agreement < 0.5  # strong disagreement

    assert "AAPL" in result.summary
    assert "TSLA" in result.summary


def test_build_consensus_empty_ticker():
    result = build_consensus_result({"EMPTY": []})
    assert result.signals["EMPTY"].signal == "neutral"
    assert result.signals["EMPTY"].score == 0.0
    assert result.signals["EMPTY"].confidence == 0.0


def test_contributions_preserved():
    contribs = [
        AgentContribution(agent_name="buffett", signal="bullish", confidence=80, reasoning="Moat"),
        AgentContribution(agent_name="munger", signal="bullish", confidence=75, reasoning="Quality"),
    ]
    result = aggregate_signals(contribs)
    assert len(result.contributions) == 2
    assert result.contributions[0].reasoning == "Moat"
    assert result.contributions[1].reasoning == "Quality"


# ── Edge cases ─────────────────────────────────────────────────────

def test_zero_confidence():
    """Zero-confidence signals should contribute zero weight."""
    contribs = [
        AgentContribution(agent_name="a", signal="bullish", confidence=0),
        AgentContribution(agent_name="b", signal="bearish", confidence=50),
    ]
    result = aggregate_signals(contribs, strategy="weighted")
    assert result.signal == "bearish"  # only B counts


def test_all_zero_confidence():
    """All zero confidence = neutral."""
    contribs = [
        AgentContribution(agent_name="a", signal="bullish", confidence=0),
        AgentContribution(agent_name="b", signal="bearish", confidence=0),
    ]
    result = aggregate_signals(contribs, strategy="weighted")
    assert result.signal == "neutral"
    assert result.score == 0.0
