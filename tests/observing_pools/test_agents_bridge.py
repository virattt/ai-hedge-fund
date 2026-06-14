"""A degraded analyst must be EXCLUDED from its component mean, not scored 50
(PRD v4-review must-fix). Otherwise a failed/unparseable analyst contributes a
neutral 50 and can outrank a genuinely bearish candidate.
"""

from src.observing_pools.agents_bridge import component_scores


def _sig(signal, confidence=100):
    return {"signal": signal, "confidence": confidence}


def test_degraded_agent_excluded_from_component_mean():
    signals = {
        "cathie_wood_agent": {"X": _sig("bullish", 100)},          # real → 100
        "growth_analyst_agent": {"X": _sig("not-a-signal", 100)},  # degraded → excluded
    }
    comps, breakdown = component_scores(signals, "X", platform_fit_score=80.0)
    # mean of non-degraded only = 100, NOT (100 + 50) / 2 = 75
    assert comps["innovation_growth"] == 100.0
    agents = breakdown["components"]["innovation_growth"]["agents"]
    assert agents["growth_analyst"]["degraded"] is True  # still recorded for provenance


def test_all_degraded_component_is_none():
    signals = {
        "cathie_wood_agent": {"X": _sig("bad", 100)},
        "growth_analyst_agent": {"X": _sig("bad", 100)},
    }
    comps, _ = component_scores(signals, "X", platform_fit_score=80.0)
    # No real scores → component absent (data_unavailable handling upstream), not 50.
    assert comps["innovation_growth"] is None


def test_degraded_does_not_produce_a_misleading_50():
    # The exact bug: degraded must not yield a 50 that beats a real bearish (0).
    degraded = component_scores(
        {"cathie_wood_agent": {"X": _sig("bad")}, "growth_analyst_agent": {"X": _sig("bad")}},
        "X",
        platform_fit_score=None,
    )[0]["innovation_growth"]
    bearish = component_scores(
        {"cathie_wood_agent": {"Y": _sig("bearish")}, "growth_analyst_agent": {"Y": _sig("bearish")}},
        "Y",
        platform_fit_score=None,
    )[0]["innovation_growth"]
    assert degraded is None  # excluded entirely
    assert bearish == 0.0    # real bearish, not masked by a fake 50
