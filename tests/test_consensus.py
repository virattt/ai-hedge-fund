import pytest

from src.consensus import (
    AgentContribution,
    ConsensusSignal,
    aggregate_signals,
    compute_agreement,
)


def _sig(signal: str, confidence: float) -> dict:
    return {"signal": signal, "confidence": confidence}


class TestComputeAgreement:
    def test_unanimous_returns_one(self):
        assert compute_agreement({"bullish": 5.0, "bearish": 0.0, "neutral": 0.0}) == 1.0

    def test_perfect_two_way_split_returns_half(self):
        assert compute_agreement({"bullish": 3.0, "bearish": 3.0, "neutral": 0.0}) == 0.5

    def test_three_way_split_returns_third(self):
        assert compute_agreement({"bullish": 1.0, "bearish": 1.0, "neutral": 1.0}) == pytest.approx(1.0 / 3.0)

    def test_empty_returns_zero(self):
        assert compute_agreement({"bullish": 0.0, "bearish": 0.0, "neutral": 0.0}) == 0.0

    def test_weighted_majority(self):
        # 1 bullish with weight 10 beats 3 bearish with weight 1 each
        assert compute_agreement({"bullish": 10.0, "bearish": 3.0, "neutral": 0.0}) == pytest.approx(10.0 / 13.0)


class TestAggregateSignalsHappyPath:
    def test_unanimous_bullish_high_conf(self):
        signals = {
            "warren_buffett_agent": _sig("bullish", 80),
            "ben_graham_agent": _sig("bullish", 80),
            "aswath_damodaran_agent": _sig("bullish", 80),
        }
        result = aggregate_signals(signals)
        assert result.signal == "bullish"
        assert result.score == pytest.approx(0.8)
        assert result.agreement == 1.0
        assert result.confidence == pytest.approx(80.0)
        assert result.vote_breakdown == {"bullish": 3, "bearish": 0, "neutral": 0}

    def test_unanimous_bearish_high_conf(self):
        signals = {
            "a": _sig("bearish", 90),
            "b": _sig("bearish", 90),
        }
        result = aggregate_signals(signals)
        assert result.signal == "bearish"
        assert result.score == pytest.approx(-0.9)
        assert result.agreement == 1.0

    def test_all_neutral(self):
        signals = {"a": _sig("neutral", 70), "b": _sig("neutral", 70)}
        result = aggregate_signals(signals)
        assert result.signal == "neutral"
        assert result.score == 0.0
        assert result.agreement == 1.0  # all weight in neutral camp
        assert result.confidence == pytest.approx(70.0)

    def test_half_and_half_returns_neutral_low_confidence(self):
        signals = {
            "a": _sig("bullish", 80),
            "b": _sig("bullish", 80),
            "c": _sig("bearish", 80),
            "d": _sig("bearish", 80),
        }
        result = aggregate_signals(signals)
        assert result.signal == "neutral"
        assert result.score == pytest.approx(0.0)
        assert result.agreement == 0.5
        # Weighted mean conf is 80, scaled by agreement=0.5
        assert result.confidence == pytest.approx(40.0)

    def test_vote_breakdown_counts_every_agent(self):
        signals = {
            "a": _sig("bullish", 50),
            "b": _sig("bearish", 50),
            "c": _sig("neutral", 50),
            "d": _sig("bullish", 50),
        }
        result = aggregate_signals(signals)
        assert result.vote_breakdown == {"bullish": 2, "bearish": 1, "neutral": 1}


class TestAggregateSignalsWeights:
    def test_missing_weight_defaults_to_one(self):
        signals = {"a": _sig("bullish", 100), "b": _sig("bullish", 100)}
        # No weights dict supplied at all
        result = aggregate_signals(signals)
        assert result.score == pytest.approx(1.0)

    def test_high_weight_overrides_many_low_weight(self):
        signals = {
            "bull_1": _sig("bullish", 80),
            "bull_2": _sig("bullish", 80),
            "bull_3": _sig("bullish", 80),
            "bear_heavy": _sig("bearish", 80),
        }
        weights = {"bull_1": 1.0, "bull_2": 1.0, "bull_3": 1.0, "bear_heavy": 5.0}
        result = aggregate_signals(signals, weights=weights)
        # numerator = 3 * 0.8 - 1 * 5 * 0.8 = 2.4 - 4.0 = -1.6
        # denominator = 3 + 5 = 8 → score = -0.2
        assert result.score == pytest.approx(-0.2)
        assert result.signal == "bearish"

    def test_negative_weight_is_clamped_to_zero(self):
        signals = {"a": _sig("bullish", 100), "b": _sig("bearish", 100)}
        weights = {"a": 1.0, "b": -5.0}
        result = aggregate_signals(signals, weights=weights)
        # b contributes 0, a drives the score
        assert result.score == pytest.approx(1.0)
        assert result.signal == "bullish"
        assert result.contributions["b"].weight == 0.0

    def test_non_numeric_weight_falls_back_to_one(self):
        signals = {"a": _sig("bullish", 100)}
        weights = {"a": "not_a_number"}
        result = aggregate_signals(signals, weights=weights)
        assert result.contributions["a"].weight == 1.0


class TestAggregateSignalsStrategies:
    def test_majority_strategy_ignores_confidence(self):
        # 3 low-confidence bullish would lose a confidence-weighted vote
        # against 1 high-confidence bearish, but majority ignores confidence.
        signals = {
            "a": _sig("bullish", 10),
            "b": _sig("bullish", 10),
            "c": _sig("bullish", 10),
            "d": _sig("bearish", 90),
        }
        result = aggregate_signals(signals, strategy="majority")
        # score = (3*1 - 1) / 4 = 0.5
        assert result.score == pytest.approx(0.5)
        assert result.signal == "bullish"

    def test_mean_strategy_ignores_custom_weights(self):
        signals = {
            "light_bull": _sig("bullish", 100),
            "heavy_bear": _sig("bearish", 100),
        }
        weights = {"light_bull": 1.0, "heavy_bear": 100.0}
        result = aggregate_signals(signals, weights=weights, strategy="mean")
        # Both reduced to weight 1 → score = 0
        assert result.score == pytest.approx(0.0)
        assert result.contributions["heavy_bear"].weight == 1.0

    def test_weighted_strategy_uses_both_confidence_and_weight(self):
        signals = {
            "a": _sig("bullish", 50),
            "b": _sig("bullish", 50),
        }
        result = aggregate_signals(signals)
        assert result.score == pytest.approx(0.5)


class TestAggregateSignalsDeadband:
    def test_score_below_deadband_is_neutral(self):
        # Craft signals so score == 0.14
        signals = {
            "a": _sig("bullish", 50),  # +0.5
            "b": _sig("bullish", 50),  # +0.5
            "c": _sig("bearish", 36),  # -0.36
            "d": _sig("bearish", 50),  # -0.5
        }
        result = aggregate_signals(signals, neutral_deadband=0.15)
        assert result.score == pytest.approx(0.035)
        assert result.signal == "neutral"

    def test_score_above_deadband_is_directional(self):
        signals = {
            "a": _sig("bullish", 80),
            "b": _sig("bearish", 50),
        }
        # score = (0.8 - 0.5) / 2 = 0.15; with default deadband 0.15 → neutral
        # Pick a narrower deadband to verify bullish classification
        result = aggregate_signals(signals, neutral_deadband=0.1)
        assert result.score == pytest.approx(0.15)
        assert result.signal == "bullish"

    def test_zero_deadband_never_returns_neutral_on_nonzero_score(self):
        signals = {"a": _sig("bullish", 1)}
        result = aggregate_signals(signals, neutral_deadband=0.0)
        assert result.signal == "bullish"


class TestAggregateSignalsEdgeCases:
    def test_empty_signals_returns_neutral_zero_confidence(self):
        result = aggregate_signals({})
        assert result.signal == "neutral"
        assert result.score == 0.0
        assert result.confidence == 0.0
        assert result.agreement == 0.0
        assert "No valid" in result.reasoning

    def test_invalid_signal_string_is_skipped(self):
        signals = {
            "valid": _sig("bullish", 80),
            "invalid": {"signal": "strong_buy", "confidence": 90},
        }
        result = aggregate_signals(signals)
        assert "valid" in result.contributions
        assert "invalid" not in result.contributions
        assert result.score == pytest.approx(0.8)

    def test_non_dict_payload_is_skipped(self):
        signals = {
            "valid": _sig("bullish", 80),
            "broken": "not-a-dict",
        }
        result = aggregate_signals(signals)
        assert "broken" not in result.contributions

    def test_missing_confidence_coerced_to_zero(self):
        signals = {"a": {"signal": "bullish"}}  # no confidence
        result = aggregate_signals(signals)
        assert result.contributions["a"].confidence == 0.0
        assert result.score == 0.0  # conf=0 → contribution=0
        assert result.signal == "neutral"

    def test_none_confidence_coerced_to_zero(self):
        signals = {"a": {"signal": "bullish", "confidence": None}}
        result = aggregate_signals(signals)
        assert result.contributions["a"].confidence == 0.0

    def test_bad_confidence_string_coerced_to_zero(self):
        signals = {"a": {"signal": "bullish", "confidence": "very confident"}}
        result = aggregate_signals(signals)
        assert result.contributions["a"].confidence == 0.0

    def test_confidence_over_100_is_clamped(self):
        signals = {"a": _sig("bullish", 250)}
        result = aggregate_signals(signals)
        assert result.contributions["a"].confidence == 100.0
        assert result.score == pytest.approx(1.0)

    def test_confidence_below_zero_is_clamped(self):
        signals = {"a": _sig("bullish", -50)}
        result = aggregate_signals(signals)
        assert result.contributions["a"].confidence == 0.0

    def test_all_zero_confidence_unanimous_is_neutral(self):
        # Everyone says bullish but with zero confidence → no real signal
        signals = {"a": _sig("bullish", 0), "b": _sig("bullish", 0)}
        result = aggregate_signals(signals)
        assert result.score == 0.0
        assert result.signal == "neutral"
        assert result.agreement == 1.0  # they still all voted bullish
        assert result.confidence == 0.0


class TestReturnTypes:
    def test_result_is_consensus_signal(self):
        result = aggregate_signals({"a": _sig("bullish", 50)})
        assert isinstance(result, ConsensusSignal)

    def test_contributions_are_agent_contribution(self):
        result = aggregate_signals({"a": _sig("bullish", 50)})
        assert isinstance(result.contributions["a"], AgentContribution)

    def test_reasoning_mentions_top_contributors(self):
        signals = {
            "heavy_hitter": _sig("bullish", 100),
            "quiet_one": _sig("neutral", 10),
        }
        result = aggregate_signals(signals)
        assert "heavy_hitter" in result.reasoning

    def test_contribution_sum_equals_score_times_weight_sum(self):
        signals = {
            "a": _sig("bullish", 80),
            "b": _sig("bearish", 60),
            "c": _sig("neutral", 50),
        }
        weights = {"a": 2.0, "b": 1.0, "c": 1.5}
        result = aggregate_signals(signals, weights=weights)
        total_contribution = sum(c.contribution for c in result.contributions.values())
        weight_sum = sum(c.weight for c in result.contributions.values())
        assert result.score == pytest.approx(total_contribution / weight_sum)
