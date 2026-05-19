"""Build a `SnapshotReport` for a single ticker.

Uses yfinance for both price history and fundamentals/analyst data. All
network failures degrade gracefully — missing fields appear as N/A rather
than crashing the run.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd

from src.analysis import indicators as ind
from src.analysis.verdicts import (
    IndicatorRow,
    MetricRow,
    Verdict,
    aggregate_verdict,
    analyst_verdict,
    overall_verdict,
    signal_bollinger,
    signal_macd,
    signal_rsi,
    signal_volume,
    signal_vs_sma,
    verdict_debt_equity,
    verdict_ev_ebitda,
    verdict_fcf_yield,
    verdict_forward_pe,
    verdict_pe,
    verdict_peg,
    verdict_revenue_growth,
    verdict_roe,
    verdict_roic,
)

warnings.filterwarnings("ignore", category=FutureWarning)


@dataclass
class PriceReturn:
    label: str
    ticker_return: Optional[float]
    spx_return: Optional[float]

    @property
    def relative(self) -> Optional[float]:
        if self.ticker_return is None or self.spx_return is None:
            return None
        if math.isnan(self.ticker_return) or math.isnan(self.spx_return):
            return None
        return self.ticker_return - self.spx_return


@dataclass
class AnalystPanel:
    total_analysts: Optional[int]
    pct_strong_buy: Optional[float]
    pct_buy: Optional[float]
    pct_hold: Optional[float]
    pct_sell: Optional[float]
    pct_strong_sell: Optional[float]
    mean_target: Optional[float]
    median_target: Optional[float]
    high_target: Optional[float]
    low_target: Optional[float]
    upside_pct: Optional[float]
    consensus_label: Optional[str]
    recent_actions_note: Optional[str] = None


@dataclass
class SnapshotReport:
    ticker: str
    company_name: str
    sector: Optional[str]
    industry: Optional[str]
    current_price: Optional[float]
    market_cap: Optional[float]
    timestamp: datetime
    week_52_high: Optional[float]
    week_52_low: Optional[float]

    price_returns: list[PriceReturn]
    fundamental_metrics: list[MetricRow]
    fundamental_verdict: Verdict
    fundamental_confidence: float

    technical_indicators: list[IndicatorRow]
    technical_verdict: Verdict
    technical_confidence: float

    analyst: AnalystPanel
    analyst_verdict_label: Verdict

    overall_verdict_label: Verdict
    composite_score: float  # 0-100
    composite_confidence: float  # 0-1

    synthesis: str
    data_warnings: list[str] = field(default_factory=list)
    # Last ~90 trading-day closes (oldest -> newest) for sparkline rendering
    price_sparkline: list[float] = field(default_factory=list)

    # Populated lazily by the orchestrator (src.analysis.combined.deep_analyze).
    # Kept on this dataclass so the renderer has one place to look.
    backtest: object | None = None   # BacktestSummary
    agents: object | None = None     # AgentRunResult
    final_verdict: object | None = None  # FinalRecommendation


# ----------------------------------------------------------------------------
# Data fetch
# ----------------------------------------------------------------------------


def _safe_get(info: dict, *keys, default=None):
    for k in keys:
        v = info.get(k)
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            return v
    return default


def _compute_roe_3y_avg(ticker_obj) -> Optional[float]:
    """Approximate 3-year average ROE = avg(net_income_i / equity_i) over last 3 fiscal years."""
    try:
        income = ticker_obj.income_stmt
        balance = ticker_obj.balance_sheet
        if income is None or balance is None or income.empty or balance.empty:
            return None
        # Income index labels can vary; try common keys
        ni_row = None
        for key in ("Net Income", "Net Income Common Stockholders", "Net Income From Continuing Operation Net Minority Interest"):
            if key in income.index:
                ni_row = income.loc[key]
                break
        eq_row = None
        for key in ("Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"):
            if key in balance.index:
                eq_row = balance.loc[key]
                break
        if ni_row is None or eq_row is None:
            return None
        # Align columns (dates)
        cols = list(ni_row.index)[:3]
        roes = []
        for c in cols:
            if c in eq_row.index:
                ni = ni_row[c]
                eq = eq_row[c]
                if eq and not pd.isna(eq) and eq != 0:
                    roes.append(float(ni) / float(eq))
        if not roes:
            return None
        return sum(roes) / len(roes)
    except Exception:
        return None


def _compute_revenue_cagr_3y(ticker_obj) -> Optional[float]:
    try:
        income = ticker_obj.income_stmt
        if income is None or income.empty:
            return None
        rev_row = None
        for key in ("Total Revenue", "Revenue", "Operating Revenue"):
            if key in income.index:
                rev_row = income.loc[key]
                break
        if rev_row is None or len(rev_row) < 4:
            return None
        # income_stmt has most-recent year first; columns are dates descending
        latest = float(rev_row.iloc[0])
        three_back = float(rev_row.iloc[3]) if len(rev_row) >= 4 else float(rev_row.iloc[-1])
        if three_back <= 0:
            return None
        years = 3
        return (latest / three_back) ** (1 / years) - 1
    except Exception:
        return None


def _compute_fcf_yield(ticker_obj, market_cap: Optional[float]) -> Optional[float]:
    if not market_cap or market_cap <= 0:
        return None
    try:
        cf = ticker_obj.cashflow
        if cf is None or cf.empty:
            return None
        # FCF ≈ Operating Cash Flow − CapEx (CapEx is usually negative)
        ocf = None
        capex = None
        for key in ("Operating Cash Flow", "Cash Flow From Operating Activities"):
            if key in cf.index:
                ocf = float(cf.loc[key].iloc[0])
                break
        for key in ("Capital Expenditure", "Capital Expenditures"):
            if key in cf.index:
                capex = float(cf.loc[key].iloc[0])
                break
        # Some providers include FCF directly
        if "Free Cash Flow" in cf.index:
            fcf = float(cf.loc["Free Cash Flow"].iloc[0])
        elif ocf is not None and capex is not None:
            fcf = ocf + capex  # capex is negative
        else:
            return None
        return fcf / market_cap
    except Exception:
        return None


def _build_analyst_panel(info: dict, current_price: Optional[float]) -> AnalystPanel:
    rec_key = _safe_get(info, "recommendationKey")
    mean_target = _safe_get(info, "targetMeanPrice")
    median_target = _safe_get(info, "targetMedianPrice")
    high_target = _safe_get(info, "targetHighPrice")
    low_target = _safe_get(info, "targetLowPrice")
    total = _safe_get(info, "numberOfAnalystOpinions")

    # yfinance .info doesn't break out counts; pull from recommendations_summary later if needed
    return AnalystPanel(
        total_analysts=total,
        pct_strong_buy=None,
        pct_buy=None,
        pct_hold=None,
        pct_sell=None,
        pct_strong_sell=None,
        mean_target=mean_target,
        median_target=median_target,
        high_target=high_target,
        low_target=low_target,
        upside_pct=(
            (mean_target / current_price - 1) if mean_target and current_price else None
        ),
        consensus_label=rec_key.replace("_", " ").title() if rec_key else None,
    )


def _enrich_analyst_with_breakdown(ticker_obj, panel: AnalystPanel) -> AnalystPanel:
    """Populate per-rating percentages from recommendations_summary if available."""
    try:
        rs = getattr(ticker_obj, "recommendations_summary", None)
        # yfinance may also expose `.upgrades_downgrades` / `.recommendations`
        if rs is not None and not rs.empty:
            # Newer yfinance returns DataFrame with cols: period, strongBuy, buy, hold, sell, strongSell
            latest = rs.iloc[0]
            cols = {c.lower(): c for c in rs.columns}
            sb = latest.get(cols.get("strongbuy", "strongBuy"), 0) or 0
            b = latest.get(cols.get("buy", "buy"), 0) or 0
            h = latest.get(cols.get("hold", "hold"), 0) or 0
            s = latest.get(cols.get("sell", "sell"), 0) or 0
            ss = latest.get(cols.get("strongsell", "strongSell"), 0) or 0
            total = sb + b + h + s + ss
            if total > 0:
                panel.total_analysts = int(total)
                panel.pct_strong_buy = sb / total
                panel.pct_buy = b / total
                panel.pct_hold = h / total
                panel.pct_sell = s / total
                panel.pct_strong_sell = ss / total
    except Exception:
        pass
    # Recent action note
    try:
        ud = getattr(ticker_obj, "upgrades_downgrades", None)
        if ud is not None and not ud.empty:
            latest = ud.iloc[0]
            firm = latest.get("Firm") or latest.get("firm") or "Analyst"
            action = latest.get("Action") or latest.get("action") or ""
            to_grade = latest.get("ToGrade") or latest.get("toGrade") or ""
            try:
                when = ud.index[0].strftime("%Y-%m-%d")
            except Exception:
                when = ""
            panel.recent_actions_note = f"{firm}: {action} → {to_grade} ({when})".strip(": -")
    except Exception:
        pass
    return panel


# ----------------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------------


def generate_snapshot(ticker: str) -> SnapshotReport:
    """Build a SnapshotReport for `ticker`. Returns a report with N/A entries on failure rather than raising."""
    import yfinance as yf  # lazy import — only imported when this runs

    warnings_list: list[str] = []
    ticker = ticker.upper().strip()
    yf_ticker = yf.Ticker(ticker)

    # --- Price history (3y for 3Y return; we'll also need shorter periods, but 3y covers all) -----
    try:
        # 5y window so the 756-trading-day 3Y lookback always has data
        hist = yf_ticker.history(period="5y", auto_adjust=True)
    except Exception as e:
        warnings_list.append(f"history fetch failed: {e}")
        hist = pd.DataFrame()

    try:
        spx_hist = yf.Ticker("^GSPC").history(period="5y", auto_adjust=True)
    except Exception as e:
        warnings_list.append(f"S&P 500 fetch failed: {e}")
        spx_hist = pd.DataFrame()

    close = hist["Close"] if not hist.empty else pd.Series(dtype=float)
    spx_close = spx_hist["Close"] if not spx_hist.empty else pd.Series(dtype=float)
    high = hist["High"] if not hist.empty else pd.Series(dtype=float)
    low = hist["Low"] if not hist.empty else pd.Series(dtype=float)
    volume = hist["Volume"] if not hist.empty else pd.Series(dtype=float)

    current_price = float(close.iloc[-1]) if len(close) else None

    # --- Period returns -----
    if len(close):
        ticker_returns = ind.compute_period_returns(close)
    else:
        ticker_returns = {k: float("nan") for k in ind.PERIOD_DAYS}
    spx_returns = ind.compute_period_returns(spx_close) if len(spx_close) else {
        k: float("nan") for k in ind.PERIOD_DAYS
    }
    price_returns = [
        PriceReturn(label=label, ticker_return=ticker_returns[label], spx_return=spx_returns[label])
        for label in ind.PERIOD_DAYS
    ]

    # --- Company info / fundamentals -----
    try:
        info = yf_ticker.info or {}
    except Exception as e:
        warnings_list.append(f"info fetch failed: {e}")
        info = {}

    company_name = _safe_get(info, "longName", "shortName", default=ticker)
    sector = _safe_get(info, "sector")
    industry = _safe_get(info, "industry")
    market_cap = _safe_get(info, "marketCap")
    week_52_high = _safe_get(info, "fiftyTwoWeekHigh")
    week_52_low = _safe_get(info, "fiftyTwoWeekLow")

    pe = _safe_get(info, "trailingPE")
    fpe = _safe_get(info, "forwardPE")
    peg = _safe_get(info, "trailingPegRatio", "pegRatio")
    ev_ebitda = _safe_get(info, "enterpriseToEbitda")
    debt_eq = _safe_get(info, "debtToEquity")
    if debt_eq is not None and debt_eq > 5:
        # yfinance often returns D/E as a percentage (e.g. 152.3 means 1.523)
        debt_eq = debt_eq / 100.0
    roe = _safe_get(info, "returnOnEquity")
    roa = _safe_get(info, "returnOnAssets")
    revenue_growth_ttm = _safe_get(info, "revenueGrowth")

    # Computed extras
    roe_3y = _compute_roe_3y_avg(yf_ticker)
    rev_cagr_3y = _compute_revenue_cagr_3y(yf_ticker)
    fcf_yield_val = _compute_fcf_yield(yf_ticker, market_cap)
    # ROIC proxy: ROE * (1 - debt_share). Imperfect but better than nothing.
    roic_proxy: Optional[float] = None
    if roe is not None and debt_eq is not None:
        try:
            equity_share = 1 / (1 + debt_eq) if debt_eq >= 0 else 1
            roic_proxy = roe * equity_share
        except Exception:
            roic_proxy = None
    if roic_proxy is None:
        roic_proxy = roe  # fall back

    # --- Build fundamental metric rows -----
    def _row(name: str, value, unit: str, fn) -> MetricRow:
        v, why = fn(value)
        return MetricRow(name=name, value=value, unit=unit, verdict=v, rationale=why)

    fundamental_metrics: list[MetricRow] = [
        _row("P/E (TTM)", pe, "x", verdict_pe),
        MetricRow(
            name="Forward P/E",
            value=fpe,
            unit="x",
            verdict=verdict_forward_pe(fpe, pe)[0],
            rationale=verdict_forward_pe(fpe, pe)[1],
        ),
        _row("PEG", peg, "x", verdict_peg),
        _row("EV/EBITDA", ev_ebitda, "x", verdict_ev_ebitda),
        _row("Debt / Equity", debt_eq, "x", verdict_debt_equity),
        _row("ROE (TTM)", roe, "%", verdict_roe),
        _row("ROE (3Y avg)", roe_3y, "%", verdict_roe),
        _row("ROIC (proxy)", roic_proxy, "%", verdict_roic),
        _row("FCF Yield", fcf_yield_val, "%", verdict_fcf_yield),
        _row("Revenue Growth (3Y CAGR)", rev_cagr_3y, "%", verdict_revenue_growth),
    ]
    fundamental_v, fundamental_conf = aggregate_verdict(fundamental_metrics)

    # --- Technical indicators -----
    technical_indicators: list[IndicatorRow] = []
    if len(close) >= 200:
        rsi_series = ind.rsi(close, 14)
        rsi_val = float(rsi_series.iloc[-1]) if len(rsi_series) else float("nan")
        macd_line, sig_line, hist_line = ind.macd(close)
        macd_v = float(macd_line.iloc[-1]) if len(macd_line) else float("nan")
        sig_v = float(sig_line.iloc[-1]) if len(sig_line) else float("nan")
        hist_v = float(hist_line.iloc[-1]) if len(hist_line) else float("nan")
        sma50 = ind.sma(close, 50)
        sma200 = ind.sma(close, 200)
        sma50_v = float(sma50.iloc[-1]) if not pd.isna(sma50.iloc[-1]) else float("nan")
        sma200_v = float(sma200.iloc[-1]) if not pd.isna(sma200.iloc[-1]) else float("nan")
        # Slope: simple 20-day delta of SMA
        sma200_slope = None
        if len(sma200.dropna()) > 20:
            sma200_slope = float(sma200.iloc[-1] - sma200.iloc[-21])
        bb_low, bb_mid, bb_up = ind.bollinger(close, 20, 2.0)
        bb_low_v = float(bb_low.iloc[-1]) if not pd.isna(bb_low.iloc[-1]) else float("nan")
        bb_up_v = float(bb_up.iloc[-1]) if not pd.isna(bb_up.iloc[-1]) else float("nan")
        rel_vol = ind.relative_volume(volume, 50)
        pct_today = (
            (float(close.iloc[-1]) / float(close.iloc[-2]) - 1) if len(close) >= 2 else None
        )

        def _ind(name: str, state: str, sig_fn_result: tuple[Verdict, str]) -> IndicatorRow:
            v, why = sig_fn_result
            return IndicatorRow(name=name, state=state, signal=v, rationale=why)

        technical_indicators.append(_ind("RSI (14)", f"{rsi_val:.1f}", signal_rsi(rsi_val)))
        technical_indicators.append(
            _ind(
                "MACD",
                f"MACD {macd_v:.3f} / Signal {sig_v:.3f} / Hist {hist_v:+.3f}",
                signal_macd(macd_v, sig_v, hist_v),
            )
        )
        technical_indicators.append(
            _ind(
                "Price vs SMA 50",
                f"${current_price:.2f} vs ${sma50_v:.2f}",
                signal_vs_sma(current_price, sma50_v, None),
            )
        )
        technical_indicators.append(
            _ind(
                "Price vs SMA 200 + slope",
                f"${current_price:.2f} vs ${sma200_v:.2f} (slope {sma200_slope:+.2f})"
                if sma200_slope is not None
                else f"${current_price:.2f} vs ${sma200_v:.2f}",
                signal_vs_sma(current_price, sma200_v, sma200_slope),
            )
        )
        technical_indicators.append(
            _ind(
                "Bollinger Bands (20, 2σ)",
                f"low ${bb_low_v:.2f} / up ${bb_up_v:.2f}",
                signal_bollinger(current_price, bb_low_v, bb_up_v),
            )
        )
        technical_indicators.append(
            _ind(
                "Volume vs 50d avg",
                f"{rel_vol:.2f}x",
                signal_volume(rel_vol, pct_today),
            )
        )
    else:
        warnings_list.append(f"Insufficient price history for technicals (have {len(close)} days, need 200)")
    technical_v, technical_conf = aggregate_verdict(technical_indicators, key="signal")

    # --- Analyst panel -----
    analyst = _build_analyst_panel(info, current_price)
    analyst = _enrich_analyst_with_breakdown(yf_ticker, analyst)
    pct_buy_combined = (
        (analyst.pct_strong_buy or 0) + (analyst.pct_buy or 0) if analyst.pct_buy is not None else None
    )
    pct_sell_combined = (
        (analyst.pct_sell or 0) + (analyst.pct_strong_sell or 0) if analyst.pct_sell is not None else None
    )
    analyst_v = analyst_verdict(pct_buy_combined, pct_sell_combined)

    # --- Macro proxy (lightweight: based on S&P 200-day trend) -----
    macro_v: Verdict = "HOLD"
    if len(spx_close) >= 200:
        spx_sma200 = ind.sma(spx_close, 200).iloc[-1]
        if not pd.isna(spx_sma200):
            if spx_close.iloc[-1] > spx_sma200:
                macro_v = "BUY"
            elif spx_close.iloc[-1] < spx_sma200 * 0.95:
                macro_v = "SELL"

    # --- Overall verdict -----
    overall_v, score_100, comp_conf = overall_verdict(
        fundamental=fundamental_v,
        technical=technical_v,
        analyst=analyst_v,
        macro=macro_v,
    )

    # --- Synthesis paragraph (rule-based, no LLM) -----
    synthesis_parts = [
        f"Composite score {score_100:.0f}/100 → {overall_v}."
    ]
    if fundamental_v != "N/A":
        synthesis_parts.append(
            f"Fundamentals: {fundamental_v.lower()} (confidence {fundamental_conf:.0%}) — "
            f"driven by {sum(1 for m in fundamental_metrics if m.verdict == 'BUY')} buy-tagged metrics "
            f"vs {sum(1 for m in fundamental_metrics if m.verdict == 'SELL')} sell-tagged."
        )
    if technical_v != "N/A":
        synthesis_parts.append(
            f"Technicals: {technical_v.lower()} (confidence {technical_conf:.0%}); "
            f"price {'above' if current_price and len(close) >= 200 and current_price > ind.sma(close, 200).iloc[-1] else 'at/below'} 200-day SMA."
        )
    if analyst_v != "N/A":
        if analyst.upside_pct is not None:
            synthesis_parts.append(
                f"Analysts: {analyst_v.lower()}, mean target implies {analyst.upside_pct:+.1%} from current."
            )
        else:
            synthesis_parts.append(f"Analysts: {analyst_v.lower()}.")
    synthesis_parts.append(
        f"Macro tilt ({macro_v.lower()}) reflects S&P 500 200-day trend."
    )

    sparkline = (
        [float(x) for x in close.tail(90).tolist() if pd.notna(x)] if len(close) else []
    )

    # Run technical backtest (fast, deterministic — reuses price/volume already pulled)
    backtest_summary = None
    try:
        from src.analysis.backtest import run_backtest as _run_bt
        if len(close):
            backtest_summary = _run_bt(close, volume, spx_close if len(spx_close) else None)
    except Exception as _e:
        warnings_list.append(f"backtest failed: {_e}")

    return SnapshotReport(
        ticker=ticker,
        company_name=company_name,
        sector=sector,
        industry=industry,
        current_price=current_price,
        market_cap=market_cap,
        timestamp=datetime.now(),
        week_52_high=week_52_high,
        week_52_low=week_52_low,
        price_returns=price_returns,
        fundamental_metrics=fundamental_metrics,
        fundamental_verdict=fundamental_v,
        fundamental_confidence=fundamental_conf,
        technical_indicators=technical_indicators,
        technical_verdict=technical_v,
        technical_confidence=technical_conf,
        analyst=analyst,
        analyst_verdict_label=analyst_v,
        overall_verdict_label=overall_v,
        composite_score=score_100,
        composite_confidence=comp_conf,
        synthesis=" ".join(synthesis_parts),
        data_warnings=warnings_list,
        price_sparkline=sparkline,
        backtest=backtest_summary,
    )
