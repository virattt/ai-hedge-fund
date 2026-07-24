"""FYI Deep Fundamental Agent — Piotroski, Altman Z, DuPont, earnings quality. Informational only."""
import json

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.graph.state import AgentState
from src.tools.api import get_financial_metrics, search_line_items
from src.utils.api_key import get_api_key_from_state
from src.utils.llm import call_llm
from src.utils.progress import progress


class DeepFundamentalOutput(BaseModel):
    summary: str = Field(description="3 sentences of deep fundamental narrative")
    quality_verdict: str = Field(description="1 sentence on overall business quality")
    risk_flags: str = Field(description="1 sentence on key fundamental risks or red flags")


def _safe(val, default=None):
    try:
        if val is None:
            return default
        f = float(val)
        return default if (f != f) else f  # NaN check
    except (TypeError, ValueError):
        return default


def _piotroski_fscore(cur, prev) -> tuple[int, dict]:
    """Compute Piotroski F-Score (0-9) from two periods of FinancialMetrics."""
    score = 0
    details = {}

    # ---- Profitability (4 pts) ----
    roa_cur = _safe(getattr(cur, "return_on_assets", None), 0)
    roa_prev = _safe(getattr(prev, "return_on_assets", None), 0)
    cfo = _safe(getattr(cur, "operating_cash_flow_per_share", None))
    total_assets = _safe(getattr(cur, "total_assets", None))

    f1 = int(roa_cur > 0) if roa_cur is not None else 0
    score += f1; details["F1_roa_positive"] = f1

    # CFO > 0
    cfo_positive = 0
    if cfo is not None:
        cfo_positive = int(cfo > 0)
    elif total_assets and total_assets > 0:
        ocf = _safe(getattr(cur, "free_cash_flow_per_share", None))
        if ocf is not None:
            cfo_positive = int(ocf > 0)
    score += cfo_positive; details["F2_cfo_positive"] = cfo_positive

    f3 = int(roa_cur > roa_prev) if (roa_cur is not None and roa_prev is not None) else 0
    score += f3; details["F3_roa_improving"] = f3

    # Accruals: CFO/Assets > ROA  (quality of earnings)
    if cfo is not None and total_assets and total_assets > 0 and roa_cur is not None:
        cfo_ratio = cfo / total_assets
        f4 = int(cfo_ratio > roa_cur)
    else:
        f4 = 0
    score += f4; details["F4_accruals_low"] = f4

    # ---- Leverage / Liquidity (3 pts) ----
    de_cur = _safe(getattr(cur, "debt_to_equity", None))
    de_prev = _safe(getattr(prev, "debt_to_equity", None))
    f5 = int(de_cur < de_prev) if (de_cur is not None and de_prev is not None) else 0
    score += f5; details["F5_leverage_lower"] = f5

    cr_cur = _safe(getattr(cur, "current_ratio", None))
    cr_prev = _safe(getattr(prev, "current_ratio", None))
    f6 = int(cr_cur > cr_prev) if (cr_cur is not None and cr_prev is not None) else 0
    score += f6; details["F6_liquidity_improving"] = f6

    # No new dilution (shares outstanding stable or declining)
    shares_cur = _safe(getattr(cur, "shares_outstanding", None))
    shares_prev = _safe(getattr(prev, "shares_outstanding", None))
    f7 = int(shares_cur <= shares_prev) if (shares_cur and shares_prev) else 0
    score += f7; details["F7_no_dilution"] = f7

    # ---- Operating Efficiency (2 pts) ----
    gm_cur = _safe(getattr(cur, "gross_margin", None))
    gm_prev = _safe(getattr(prev, "gross_margin", None))
    f8 = int(gm_cur > gm_prev) if (gm_cur is not None and gm_prev is not None) else 0
    score += f8; details["F8_gross_margin_up"] = f8

    at_cur = _safe(getattr(cur, "asset_turnover", None))
    at_prev = _safe(getattr(prev, "asset_turnover", None))
    f9 = int(at_cur > at_prev) if (at_cur is not None and at_prev is not None) else 0
    score += f9; details["F9_asset_turnover_up"] = f9

    return score, details


def _altman_z(metrics) -> tuple[float | None, str]:
    """Approximate Altman Z-Score for public companies using available metrics."""
    try:
        # Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
        cr = _safe(getattr(metrics, "current_ratio", None))
        total_assets = _safe(getattr(metrics, "total_assets", None))
        roe = _safe(getattr(metrics, "return_on_equity", None))
        roa = _safe(getattr(metrics, "return_on_assets", None))
        de = _safe(getattr(metrics, "debt_to_equity", None))
        at = _safe(getattr(metrics, "asset_turnover", None))
        ret_earn_ratio = _safe(getattr(metrics, "retained_earnings_to_assets", None))

        if None in [cr, roa, at]:
            return None, "insufficient data"

        # X1 = Working capital / Total assets ≈ (CR-1)/CR  (approx if CA and TA not direct)
        x1 = (cr - 1) / cr if cr and cr > 0 else 0
        # X2 = Retained earnings / Total assets (use roe as proxy if not available)
        x2 = ret_earn_ratio if ret_earn_ratio is not None else (_safe(roe, 0) * 0.3)
        # X3 = EBIT / Total assets ≈ ROA + interest effect  (approx ROA + 0.02)
        x3 = _safe(roa, 0) + 0.02
        # X4 = Market cap / Total liabilities ≈ 1 / debt_to_equity  (book-based proxy)
        x4 = (1 / de) if de and de > 0 else 5.0
        # X5 = Revenue / Total assets = asset turnover
        x5 = _safe(at, 0)

        z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5

        if z > 2.99:
            zone = "Safe Zone (Z > 2.99)"
        elif z > 1.81:
            zone = "Grey Zone (1.81 < Z < 2.99)"
        else:
            zone = "Distress Zone (Z < 1.81)"

        return round(z, 2), zone
    except Exception:
        return None, "calculation error"


def _dupont_3factor(metrics) -> dict:
    """3-factor DuPont: ROE = Net Margin × Asset Turnover × Equity Multiplier."""
    nm = _safe(getattr(metrics, "net_margin", None))
    at = _safe(getattr(metrics, "asset_turnover", None))
    de = _safe(getattr(metrics, "debt_to_equity", None))
    roe = _safe(getattr(metrics, "return_on_equity", None))

    equity_multiplier = (1 + de) if de is not None else None
    reconstructed_roe = None
    if nm and at and equity_multiplier:
        reconstructed_roe = nm * at * equity_multiplier

    return {
        "net_profit_margin": round(nm, 4) if nm else None,
        "asset_turnover": round(at, 4) if at else None,
        "equity_multiplier": round(equity_multiplier, 4) if equity_multiplier else None,
        "roe_reported": round(roe, 4) if roe else None,
        "roe_dupont_reconstructed": round(reconstructed_roe, 4) if reconstructed_roe else None,
    }


def _sustainable_growth_rate(metrics) -> float | None:
    """SGR = ROE × retention ratio.  Retention = 1 - payout."""
    roe = _safe(getattr(metrics, "return_on_equity", None))
    payout = _safe(getattr(metrics, "dividend_payout_ratio", None), 0)
    if roe is None:
        return None
    retention = 1 - min(max(payout, 0), 1)
    return round(roe * retention * 100, 2)


def fyi_deep_fundamental_agent(state: AgentState, agent_id: str = "fyi_deep_fundamental_agent"):
    """
    FYI-only comprehensive fundamental analysis.
    Computes Piotroski F-Score, Altman Z-Score, DuPont decomposition,
    earnings quality, and sustainable growth rate.
    Does NOT influence trading decisions.
    """
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")

    deep_fa = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching financial data")

        # Get 2 periods for Piotroski (current + prior year)
        metrics_list = get_financial_metrics(ticker, end_date, period="ttm", limit=4, api_key=api_key)
        if not metrics_list or len(metrics_list) < 2:
            deep_fa[ticker] = {
                "signal": "neutral", "confidence": 40,
                "summary": "Insufficient financial data for deep analysis.",
                "quality_verdict": "", "risk_flags": "", "reasoning": "",
            }
            continue

        cur_m, prev_m = metrics_list[0], metrics_list[1]

        progress.update_status(agent_id, ticker, "Computing quality scores")

        piotroski, pio_details = _piotroski_fscore(cur_m, prev_m)
        altman_z, altman_zone = _altman_z(cur_m)
        dupont = _dupont_3factor(cur_m)
        sgr = _sustainable_growth_rate(cur_m)

        # Key metrics snapshot
        snapshot = {
            "ticker": ticker,
            "piotroski_f_score": f"{piotroski}/9",
            "piotroski_details": pio_details,
            "altman_z_score": altman_z,
            "altman_zone": altman_zone,
            "dupont_analysis": dupont,
            "sustainable_growth_rate_pct": sgr,
            "return_on_equity": _safe(getattr(cur_m, "return_on_equity", None)),
            "return_on_assets": _safe(getattr(cur_m, "return_on_assets", None)),
            "return_on_invested_capital": _safe(getattr(cur_m, "return_on_invested_capital", None)),
            "gross_margin": _safe(getattr(cur_m, "gross_margin", None)),
            "operating_margin": _safe(getattr(cur_m, "operating_margin", None)),
            "net_margin": _safe(getattr(cur_m, "net_margin", None)),
            "current_ratio": _safe(getattr(cur_m, "current_ratio", None)),
            "debt_to_equity": _safe(getattr(cur_m, "debt_to_equity", None)),
            "interest_coverage": _safe(getattr(cur_m, "interest_coverage", None)),
            "free_cash_flow_per_share": _safe(getattr(cur_m, "free_cash_flow_per_share", None)),
            "revenue_growth_yoy": _safe(getattr(cur_m, "revenue_growth", None)),
            "earnings_growth_yoy": _safe(getattr(cur_m, "earnings_per_share_growth", None)),
            "pe_ratio": _safe(getattr(cur_m, "price_to_earnings_ratio", None)),
            "pb_ratio": _safe(getattr(cur_m, "price_to_book_ratio", None)),
            "ev_to_ebitda": _safe(getattr(cur_m, "ev_to_ebitda", None)),
        }

        # Scoring for signal
        bull = 0; bear = 0

        if piotroski >= 7: bull += 3
        elif piotroski >= 5: bull += 1
        elif piotroski <= 2: bear += 3
        elif piotroski <= 4: bear += 1

        if altman_z:
            if altman_z > 2.99: bull += 2
            elif altman_z < 1.81: bear += 3

        roe = _safe(getattr(cur_m, "return_on_equity", None), 0)
        if roe > 0.20: bull += 2
        elif roe < 0.05: bear += 1

        gm = _safe(getattr(cur_m, "gross_margin", None), 0)
        if gm > 0.40: bull += 1
        elif gm < 0.15: bear += 1

        de = _safe(getattr(cur_m, "debt_to_equity", None), 0)
        if de > 2.0: bear += 1
        elif de < 0.5: bull += 1

        rev_g = _safe(getattr(cur_m, "revenue_growth", None), 0)
        if rev_g > 0.10: bull += 1
        elif rev_g < 0: bear += 2

        total = bull + bear
        net = (bull - bear) / max(total, 1)
        if net > 0.2:
            signal = "bullish"; confidence = min(int(50 + net * 45), 92)
        elif net < -0.2:
            signal = "bearish"; confidence = min(int(50 + abs(net) * 45), 92)
        else:
            signal = "neutral"; confidence = 50

        progress.update_status(agent_id, ticker, "Generating deep FA narrative")

        template = ChatPromptTemplate.from_messages([
            ("system",
             "You are a top-tier fundamental analyst (CFA). Given comprehensive quant metrics, "
             "write deep, specific, insightful fundamental analysis. "
             "summary = 3 sentences (business quality, capital efficiency, key concern). "
             "quality_verdict = 1 sentence final verdict on business quality. "
             "risk_flags = 1 sentence on the biggest fundamental risk. "
             "Use exact numbers. No filler."),
            ("human", "Fundamental data:\n{data}\n\nsignal={signal}, confidence={confidence}"),
        ])

        prompt = template.invoke({
            "data": json.dumps({k: v for k, v in snapshot.items() if v is not None}, indent=2),
            "signal": signal,
            "confidence": confidence,
        })

        out = call_llm(prompt=prompt, pydantic_model=DeepFundamentalOutput, agent_name=agent_id, state=state)

        deep_fa[ticker] = {
            "signal": signal,
            "confidence": confidence,
            "summary": (out.summary if out else "Deep FA unavailable."),
            "quality_verdict": (out.quality_verdict if out else ""),
            "risk_flags": (out.risk_flags if out else ""),
            "reasoning": (out.summary if out else ""),
            "metrics": snapshot,
        }
        progress.update_status(agent_id, ticker, "Done")

    message = HumanMessage(content=json.dumps(deep_fa, default=str), name=agent_id)
    state["data"]["analyst_signals"][agent_id] = deep_fa
    progress.update_status(agent_id, None, "Done")
    return {"messages": state["messages"] + [message], "data": data}
