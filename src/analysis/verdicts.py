"""Rules that map raw metrics/indicators to BUY/HOLD/SELL verdicts.

All rules are deliberately simple, transparent, and override-friendly. They
encode common heuristics — they are not the last word, just the first cut.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

Verdict = Literal["STRONG BUY", "BUY", "HOLD", "REDUCE", "SELL", "N/A"]


@dataclass
class MetricRow:
    name: str
    value: Optional[float]
    unit: str  # e.g. "%", "x", ""
    verdict: Verdict
    rationale: str
    industry_median: Optional[float] = None

    def fmt_value(self) -> str:
        if self.value is None or self.value != self.value:  # NaN-safe
            return "N/A"
        if self.unit == "%":
            return f"{self.value:.1%}"
        if self.unit == "x":
            return f"{self.value:.2f}x"
        return f"{self.value:.2f}"


@dataclass
class IndicatorRow:
    name: str
    state: str  # human-readable state, e.g. "62.4 (neutral)"
    signal: Verdict
    rationale: str


# ---- Fundamental verdict rules ---------------------------------------------


def verdict_pe(pe: Optional[float]) -> tuple[Verdict, str]:
    if pe is None or pe != pe or pe <= 0:
        return "N/A", "Negative or missing earnings"
    if pe < 15:
        return "BUY", "P/E < 15 — statistically cheap (Graham threshold)"
    if pe <= 25:
        return "HOLD", "P/E 15–25 — fair range for quality"
    if pe <= 40:
        return "REDUCE", "P/E 25–40 — premium pricing in growth"
    return "SELL", "P/E > 40 — richly valued; needs exceptional growth"


def verdict_forward_pe(fpe: Optional[float], pe_ttm: Optional[float]) -> tuple[Verdict, str]:
    base, reason = verdict_pe(fpe)
    if fpe and pe_ttm and fpe < pe_ttm:
        return base, f"{reason}; forward < trailing (margin expansion expected)"
    return base, reason


def verdict_peg(peg: Optional[float]) -> tuple[Verdict, str]:
    if peg is None or peg != peg or peg <= 0:
        return "N/A", "Missing growth estimate"
    if peg < 1.0:
        return "BUY", "PEG < 1 — Lynch: growth on sale"
    if peg <= 2.0:
        return "HOLD", "PEG 1–2 — fairly priced for growth"
    return "SELL", "PEG > 2 — paying too much for the growth"


def verdict_ev_ebitda(ev_ebitda: Optional[float]) -> tuple[Verdict, str]:
    if ev_ebitda is None or ev_ebitda != ev_ebitda or ev_ebitda <= 0:
        return "N/A", "Missing or negative EBITDA"
    if ev_ebitda < 10:
        return "BUY", "EV/EBITDA < 10 — cheap"
    if ev_ebitda <= 15:
        return "HOLD", "EV/EBITDA 10–15 — fair"
    return "SELL", "EV/EBITDA > 15 — expensive"


def verdict_debt_equity(de: Optional[float]) -> tuple[Verdict, str]:
    if de is None or de != de:
        return "N/A", "Missing debt data"
    if de < 0.5:
        return "BUY", "D/E < 0.5 — fortress balance sheet"
    if de <= 1.0:
        return "HOLD", "D/E 0.5–1.0 — moderate leverage"
    return "SELL", "D/E > 1.0 — elevated leverage risk"


def verdict_roe(roe: Optional[float]) -> tuple[Verdict, str]:
    if roe is None or roe != roe:
        return "N/A", "Missing ROE"
    if roe >= 0.20:
        return "BUY", "ROE ≥ 20% — exceptional"
    if roe >= 0.15:
        return "BUY", "ROE 15–20% — strong"
    if roe >= 0.10:
        return "HOLD", "ROE 10–15% — average"
    return "SELL", "ROE < 10% — subpar capital efficiency"


def verdict_roic(roic: Optional[float]) -> tuple[Verdict, str]:
    if roic is None or roic != roic:
        return "N/A", "Missing ROIC"
    if roic >= 0.20:
        return "BUY", "ROIC ≥ 20% — wide-moat economics"
    if roic >= 0.15:
        return "BUY", "ROIC 15–20% — strong"
    if roic >= 0.10:
        return "HOLD", "ROIC 10–15% — above WACC, average quality"
    return "SELL", "ROIC < 10% — likely destroying value vs WACC"


def verdict_fcf_yield(fcf_yield: Optional[float]) -> tuple[Verdict, str]:
    if fcf_yield is None or fcf_yield != fcf_yield:
        return "N/A", "Missing FCF data"
    if fcf_yield >= 0.06:
        return "BUY", "FCF yield ≥ 6% — attractive"
    if fcf_yield >= 0.03:
        return "HOLD", "FCF yield 3–6% — OK"
    return "SELL", "FCF yield < 3% — weak"


def verdict_revenue_growth(g: Optional[float]) -> tuple[Verdict, str]:
    if g is None or g != g:
        return "N/A", "Missing revenue history"
    if g >= 0.15:
        return "BUY", "Revenue CAGR ≥ 15% — excellent"
    if g >= 0.08:
        return "HOLD", "Revenue CAGR 8–15% — solid"
    if g >= 0.03:
        return "HOLD", "Revenue CAGR 3–8% — mature"
    return "SELL", "Revenue CAGR < 3% — stagnant"


# ---- Technical indicator rules ---------------------------------------------


def signal_rsi(rsi_value: Optional[float]) -> tuple[Verdict, str]:
    if rsi_value is None or rsi_value != rsi_value:
        return "N/A", "Missing RSI"
    if rsi_value < 30:
        return "BUY", f"RSI {rsi_value:.1f} — oversold"
    if rsi_value > 70:
        return "SELL", f"RSI {rsi_value:.1f} — overbought"
    return "HOLD", f"RSI {rsi_value:.1f} — neutral zone"


def signal_macd(macd_line: float, signal_line: float, hist: float) -> tuple[Verdict, str]:
    if any(v != v for v in (macd_line, signal_line, hist)):
        return "N/A", "Missing MACD"
    if macd_line > signal_line and hist > 0:
        return "BUY", "MACD above signal; positive histogram"
    if macd_line < signal_line and hist < 0:
        return "SELL", "MACD below signal; negative histogram"
    return "HOLD", "MACD near signal — momentum neutral"


def signal_vs_sma(price: float, sma_value: Optional[float], slope: Optional[float]) -> tuple[Verdict, str]:
    if sma_value is None or sma_value != sma_value or sma_value <= 0:
        return "N/A", "Missing SMA"
    pct = (price - sma_value) / sma_value
    slope_word = ""
    if slope is not None and slope == slope:
        slope_word = " & rising" if slope > 0 else " & falling"
    if pct > 0 and (slope is None or slope > 0):
        return "BUY", f"Price {pct:+.1%} above SMA{slope_word}"
    if pct < 0 and (slope is None or slope < 0):
        return "SELL", f"Price {pct:+.1%} below SMA{slope_word}"
    return "HOLD", f"Price {pct:+.1%} vs SMA{slope_word}"


def signal_bollinger(
    price: float, lower: Optional[float], upper: Optional[float]
) -> tuple[Verdict, str]:
    if lower is None or upper is None or lower != lower or upper != upper:
        return "N/A", "Missing Bollinger bands"
    band_width = upper - lower
    if band_width <= 0:
        return "N/A", "Degenerate band width"
    position = (price - lower) / band_width  # 0 = at lower, 1 = at upper
    if position <= 0.2:
        return "BUY", "Near lower band — potential bounce"
    if position >= 0.8:
        return "SELL", "Near upper band — overextended"
    return "HOLD", f"Mid-band ({position*100:.0f}% of width)"


def signal_volume(rel_vol: Optional[float], pct_change_today: Optional[float]) -> tuple[Verdict, str]:
    if rel_vol is None or rel_vol != rel_vol:
        return "N/A", "Missing volume data"
    if rel_vol >= 1.5 and (pct_change_today is None or pct_change_today >= 0):
        return "BUY", f"{rel_vol:.1f}x volume on up move — accumulation"
    if rel_vol >= 1.5 and pct_change_today is not None and pct_change_today < 0:
        return "SELL", f"{rel_vol:.1f}x volume on down move — distribution"
    if rel_vol < 0.7:
        return "HOLD", f"{rel_vol:.1f}x volume — quiet"
    return "HOLD", f"{rel_vol:.1f}x volume — normal"


# ---- Analyst consensus rules -----------------------------------------------


def analyst_verdict(pct_buy_combined: Optional[float], pct_sell_combined: Optional[float]) -> Verdict:
    """pct_buy_combined = % Strong Buy + % Buy; pct_sell_combined = % Sell + % Strong Sell."""
    if pct_buy_combined is None or pct_buy_combined != pct_buy_combined:
        return "N/A"
    if pct_buy_combined >= 0.60:
        return "BUY"
    if pct_sell_combined is not None and pct_sell_combined >= 0.30:
        return "SELL"
    return "HOLD"


# ---- Composite scoring ------------------------------------------------------


_VERDICT_TO_SCORE = {
    "BUY": 1.0,
    "STRONG BUY": 1.0,
    "HOLD": 0.0,
    "REDUCE": -0.5,
    "SELL": -1.0,
    "N/A": 0.0,
}


def verdict_score(v: Verdict) -> float:
    return _VERDICT_TO_SCORE.get(v, 0.0)


def aggregate_verdict(rows: list, key: str = "verdict") -> tuple[Verdict, float]:
    """Aggregate a list of rows (MetricRow or IndicatorRow) into a single verdict + confidence (0-1)."""
    if not rows:
        return "N/A", 0.0
    scored = [verdict_score(getattr(r, key)) for r in rows]
    valid = [s for s, r in zip(scored, rows) if getattr(r, key) != "N/A"]
    if not valid:
        return "N/A", 0.0
    avg = sum(valid) / len(valid)
    confidence = len(valid) / len(rows)
    if avg >= 0.5:
        return "BUY", confidence
    if avg <= -0.5:
        return "SELL", confidence
    return "HOLD", confidence


def overall_verdict(
    fundamental: Verdict,
    technical: Verdict,
    analyst: Verdict,
    macro: Verdict = "HOLD",
    weights: tuple[float, float, float, float] = (0.40, 0.30, 0.15, 0.15),
) -> tuple[Verdict, float, float]:
    """Returns (verdict, composite_score_0_to_100, confidence_0_to_1)."""
    w_fund, w_tech, w_an, w_macro = weights
    score = (
        w_fund * verdict_score(fundamental)
        + w_tech * verdict_score(technical)
        + w_an * verdict_score(analyst)
        + w_macro * verdict_score(macro)
    )
    # Map [-1, 1] -> [0, 100]
    score_100 = (score + 1) * 50

    if score_100 >= 75:
        v = "STRONG BUY"
    elif score_100 >= 60:
        v = "BUY"
    elif score_100 >= 40:
        v = "HOLD"
    elif score_100 >= 25:
        v = "REDUCE"
    else:
        v = "SELL"

    # Confidence: how aligned are the components
    components = [fundamental, technical, analyst, macro]
    valid = [c for c in components if c != "N/A"]
    if not valid:
        confidence = 0.0
    else:
        scores = [verdict_score(c) for c in valid]
        # Confidence is the absolute mean — higher absolute value = more aligned
        confidence = min(1.0, abs(sum(scores) / len(scores)) + 0.4)

    return v, score_100, confidence
