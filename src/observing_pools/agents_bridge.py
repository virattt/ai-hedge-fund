"""Map ai-hedge-fund analyst signals → composite component scores (PRD v4 §11.2).

ai-hedge-fund agents write ``analyst_signals[agent_id][ticker] = {signal,
confidence, reasoning}`` where ``agent_id = f"{analyst_key}_agent"`` and signal ∈
{bullish, bearish, neutral}. This module aggregates those into the five composite
components. The *blended* design (the plan's key challenge): a value axis and a
separate innovation/growth axis both contribute — value cannot veto innovation.

The empty/unparseable path is flagged ``degraded=True`` and EXCLUDED from the
component mean (recorded in the breakdown but contributing no score), so a failed
analyst cannot inflate a component to a neutral 50 and outrank a genuinely
bearish candidate (PRD v4-review must-fix: degraded must not rank).
"""

from src.observing_pools.scoring import AgentSignal, mean_or_none, signal_to_score

# component → analyst keys (agent_id = f"{key}_agent"). Risk Manager emits no
# signal (haircut only, deferred to expansion phase) so it is absent here.
COMPONENT_ANALYST_KEYS: dict[str, tuple[str, ...]] = {
    "value_investor": (
        "warren_buffett",
        "charlie_munger",
        "ben_graham",
        "mohnish_pabrai",
        "phil_fisher",
        "peter_lynch",
        "aswath_damodaran",
        "valuation_analyst",
        "fundamentals_analyst",
    ),
    "innovation_growth": ("cathie_wood", "growth_analyst"),
    "risk_adjusted_momentum": (
        "technical_analyst",
        "sentiment_analyst",
        "news_sentiment_analyst",
        "michael_burry",
        "stanley_druckenmiller",
    ),
}

_VALID_SIGNALS = {s.value for s in AgentSignal}


def committee_analyst_keys() -> list[str]:
    """The de-duplicated set of analyst keys to run for a full blended composite."""
    seen: dict[str, None] = {}
    for keys in COMPONENT_ANALYST_KEYS.values():
        for k in keys:
            seen.setdefault(k, None)
    return list(seen)


def _safe_agent_score(raw: dict | None) -> tuple[float, bool]:
    """One agent's {signal, confidence} → (0-100 score, degraded?).

    Unknown/missing signal → neutral (score 50) + degraded=True.
    """
    if not raw or raw.get("signal") not in _VALID_SIGNALS:
        return 50.0, True
    confidence = raw.get("confidence", 50)
    try:
        return signal_to_score(raw["signal"], confidence), False
    except (ValueError, TypeError):
        return 50.0, True


def component_scores(
    analyst_signals: dict[str, dict[str, dict]],
    ticker: str,
    *,
    platform_fit_score: float | None,
) -> tuple[dict[str, float | None], dict]:
    """Aggregate one ticker's agent signals into component scores + a breakdown.

    Returns ({component: score_or_None}, breakdown_json). ``platform_fit`` comes
    from the deterministic classifier (passed in), not from agents.
    """
    components: dict[str, float | None] = {"platform_fit": platform_fit_score}
    breakdown: dict = {"platform_fit": {"value": platform_fit_score, "source": "classifier"}, "components": {}}

    for component, analyst_keys in COMPONENT_ANALYST_KEYS.items():
        per_agent: dict[str, dict] = {}
        scores: list[float | None] = []
        for key in analyst_keys:
            raw = analyst_signals.get(f"{key}_agent", {}).get(ticker)
            if raw is None:
                continue  # agent not run / no signal for this ticker → omit (not zero)
            score, degraded = _safe_agent_score(raw)
            if not degraded:
                scores.append(score)  # degraded → recorded below but excluded from the mean
            per_agent[key] = {
                "signal": raw.get("signal") if not degraded else AgentSignal.NEUTRAL.value,
                "confidence": raw.get("confidence"),
                "score": round(score, 2),
                "degraded": degraded,
            }
        value = mean_or_none(scores)
        components[component] = value
        breakdown["components"][component] = {"value": value, "agents": per_agent}

    return components, breakdown
