"""Formatting helpers that are safe to import from anywhere (no circular deps)."""
import json


def _label(key: str) -> str:
    """Turn a snake_case dict key into a Title Case label, stripping common suffixes."""
    return key.replace("_signal", "").replace("_analysis", "").replace("_", " ").title()


def _reasoning_to_text(reasoning: dict) -> str:
    """Convert agent reasoning dicts to a human-readable English summary.

    Handles three structural patterns:
    1. Sentiment/News: known keys (news_sentiment, insider_trading, combined_analysis)
    2. signal+details: {"profitability_signal": {"signal": "bearish", "details": "ROE: 4%..."}}
    3. signal+confidence[+metrics]: {"trend_following": {"signal": "bearish", "confidence": 25, ...}}
    """
    parts = []

    # ── Sentiment agent: insider_trading + news_sentiment + combined_analysis ──
    if "insider_trading" in reasoning and isinstance(reasoning["insider_trading"], dict):
        it = reasoning["insider_trading"]
        m = it.get("metrics", {})
        total = m.get("total_trades", 0)
        bull = m.get("bullish_trades", 0)
        bear = m.get("bearish_trades", 0)
        sig = it.get("signal", "neutral").capitalize()
        conf = it.get("confidence", 0)
        parts.append(f"Insiders ({sig} {conf}%): {total} trades, {bull}↑ {bear}↓")

    if "news_sentiment" in reasoning and isinstance(reasoning["news_sentiment"], dict):
        ns = reasoning["news_sentiment"]
        m = ns.get("metrics", {})
        total = m.get("total_articles", 0)
        bull = m.get("bullish_articles", 0)
        bear = m.get("bearish_articles", 0)
        neutral = m.get("neutral_articles", 0)
        llm = m.get("articles_classified_by_llm", 0)
        sig = ns.get("signal", "neutral").capitalize()
        conf = ns.get("confidence", 0)
        art = f"{total} articles: {bull}↑ {bear}↓ {neutral}~" + (f" ({llm} by LLM)" if llm else "")
        parts.append(f"News ({sig} {conf:.0f}%): {art}")

    if "combined_analysis" in reasoning and isinstance(reasoning["combined_analysis"], dict):
        det = reasoning["combined_analysis"].get("signal_determination", "")
        if det:
            parts.append(det)

    if parts:
        return "; ".join(parts)

    # ── Generic: each value is a sub-dict with "signal" key ──
    for key, val in reasoning.items():
        if not isinstance(val, dict):
            continue
        sig = val.get("signal", "")
        if not sig:
            continue
        label = _label(key)
        conf = val.get("confidence")
        details = val.get("details", "")

        if details:
            # Clean up multi-line details (e.g. valuation analyst adds \n)
            details = " ".join(details.split())
            parts.append(f"{label} ({sig.capitalize()}): {details}")
        elif conf is not None:
            # Technical analyst pattern: signal + confidence + metrics
            metrics = val.get("metrics", {})
            key_metrics = []
            for mk, mv in metrics.items():
                if isinstance(mv, float) and mv != 0:
                    key_metrics.append(f"{mk.replace('_', ' ')}={mv:.2f}")
            mstr = ", ".join(key_metrics[:3])  # show at most 3 metrics
            entry = f"{label}: {sig.capitalize()} ({conf}%)"
            if mstr:
                entry += f" [{mstr}]"
            parts.append(entry)
        else:
            parts.append(f"{label}: {sig.capitalize()}")

    return "; ".join(parts) if parts else json.dumps(reasoning)
