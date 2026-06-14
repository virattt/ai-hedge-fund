"""Unit tests for the observing-pool scoring contract (PRD v4 §11, §17).

Tests encode *why* the math matters: no KeyError on any signal, confidence
clamping, the REQUIRED floor that excludes (never zero-scores) incomplete
entries, the versioned 4-comp vs 5-comp formulas, and the F2 anti-gaming
bootstrap (no reward for absent evidence).
"""

import pytest

from src.observing_pools.scoring import (
    FORMULA_4COMP,
    FORMULA_5COMP,
    AgentSignal,
    build_components,
    composite,
    mean_or_none,
    signal_to_score,
    validate_weights,
)


class TestSignalToScore:
    @pytest.mark.parametrize(
        "signal,confidence,expected",
        [
            (AgentSignal.NEUTRAL, 100, 50.0),
            (AgentSignal.NEUTRAL, 0, 50.0),
            (AgentSignal.BULLISH, 100, 100.0),
            (AgentSignal.BEARISH, 100, 0.0),
            (AgentSignal.BULLISH, 50, 75.0),
            (AgentSignal.BEARISH, 50, 25.0),
        ],
    )
    def test_every_signal_maps(self, signal, confidence, expected):
        assert signal_to_score(signal, confidence) == expected

    def test_confidence_clamped_high_and_low(self):
        assert signal_to_score(AgentSignal.BULLISH, 150) == 100.0  # clamp 150→100
        assert signal_to_score(AgentSignal.BULLISH, -10) == 50.0  # clamp -10→0

    def test_string_signal_is_coerced(self):
        # Agents emit raw strings; the function must accept them.
        assert signal_to_score("bullish", 100) == 100.0

    def test_int_and_float_confidence(self):
        assert signal_to_score(AgentSignal.BULLISH, 80) == 90.0
        assert signal_to_score(AgentSignal.BULLISH, 80.0) == 90.0

    def test_invalid_signal_raises_not_keyerror(self):
        # "watch"/"degraded"/"insufficient-evidence" must never reach this fn;
        # if they do, it's a loud ValueError, never a silent KeyError.
        with pytest.raises(ValueError):
            signal_to_score("watch", 50)


class TestMeanOrNone:
    def test_empty_is_none(self):
        assert mean_or_none([]) is None
        assert mean_or_none([None, None]) is None

    def test_skips_none(self):
        assert mean_or_none([50.0, None, 100.0]) == 75.0


class TestValidateWeights:
    def test_valid_passes(self):
        validate_weights({"platform_fit": 0.25, "value_investor": 0.30, "x": 0.45})

    def test_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            validate_weights({"platform_fit": 0.5, "value_investor": 1.5})

    def test_zero_sum_rejected(self):
        with pytest.raises(ValueError):
            validate_weights({"platform_fit": 0.0, "value_investor": 0.0})

    def test_required_weight_zero_rejected(self):
        with pytest.raises(ValueError):
            validate_weights({"platform_fit": 0.0, "value_investor": 0.3})


# Shared component values used across composite tests.
_VALUES = {"platform_fit": 90.0, "value_investor": 40.0, "innovation_growth": 80.0, "risk_adjusted_momentum": 60.0}
# 4-comp expected: (.25*90+.30*40+.20*80+.10*60)/.85 = 56.5/.85
_FOURCOMP_EXPECTED = 56.5 / 0.85


class TestComposite:
    def test_4comp_blended(self):
        comps = build_components(_VALUES, formula_version=FORMULA_4COMP)
        assert "serenity_bottleneck" not in comps  # excluded by design in Phase 5
        result = composite(comps, pool_serenity_median=None, formula_version=FORMULA_4COMP)
        assert result == pytest.approx(_FOURCOMP_EXPECTED)

    def test_required_missing_returns_none(self):
        vals = {**_VALUES, "value_investor": None}
        comps = build_components(vals, formula_version=FORMULA_4COMP)
        # data_unavailable → excluded from ranking, NOT scored 0.
        assert composite(comps, pool_serenity_median=None, formula_version=FORMULA_4COMP) is None

    def test_5comp_serenity_missing_zero_graded_drops_uniformly(self):
        # No graded entries in pool (median None) → serenity dropped for everyone;
        # result equals the 4-comp result over the same present components.
        vals = {**_VALUES, "serenity_bottleneck": None}
        comps = build_components(vals, formula_version=FORMULA_5COMP)
        result = composite(comps, pool_serenity_median=None, formula_version=FORMULA_5COMP)
        assert result == pytest.approx(_FOURCOMP_EXPECTED)

    def test_5comp_serenity_missing_imputes_median(self):
        vals = {**_VALUES, "serenity_bottleneck": None}
        comps = build_components(vals, formula_version=FORMULA_5COMP)
        # median 70 imputed: (56.5 + .15*70)/1.0 = 67.0
        result = composite(comps, pool_serenity_median=70.0, formula_version=FORMULA_5COMP)
        assert result == pytest.approx(67.0)

    def test_5comp_serenity_present_used(self):
        vals = {**_VALUES, "serenity_bottleneck": 30.0}
        comps = build_components(vals, formula_version=FORMULA_5COMP)
        # (56.5 + .15*30)/1.0 = 61.0
        result = composite(comps, pool_serenity_median=None, formula_version=FORMULA_5COMP)
        assert result == pytest.approx(61.0)

    def test_weak_evidence_beats_absent_evidence(self):
        # The anti-gaming invariant: once a pool has graded entries, weak < neutral.
        vals_weak = {**_VALUES, "serenity_bottleneck": 20.0}
        vals_absent = {**_VALUES, "serenity_bottleneck": None}
        weak = composite(build_components(vals_weak, formula_version=FORMULA_5COMP), pool_serenity_median=50.0, formula_version=FORMULA_5COMP)
        absent = composite(build_components(vals_absent, formula_version=FORMULA_5COMP), pool_serenity_median=50.0, formula_version=FORMULA_5COMP)
        assert weak < absent  # absent imputes to neutral median (50) > weak (20)

    def test_divide_by_zero_guard(self):
        # Present REQUIRED but total present weight 0 → None, not ZeroDivisionError.
        comps = {"platform_fit": (0.0, 90.0), "value_investor": (0.0, 40.0)}
        assert composite(comps, pool_serenity_median=None, formula_version=FORMULA_4COMP) is None
