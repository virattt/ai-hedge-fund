"""
Run the RenTec quant agent on the Iran second-order plays:
INDA (India), EWJ (Japan), EWT (Taiwan), UNG (Natural Gas), MCHI (China)

Fetches real ETF price data from Yahoo Finance and injects it into the
in-memory cache so the RenTec agent's quantitative sub-analyses have data
to work with (the default financialdatasets.ai API doesn't cover ETFs).

Based on the Hormuz escalation thesis from outputs/iran-second-order-plays/.
"""
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

import yfinance as yf

from src.data.cache import get_cache
from src.data.models import Price
from src.main import run_hedge_fund

# ── Config ──────────────────────────────────────────────────────────────────
tickers = ["APD", "LIN", "CF", "NTR", "MOS", "LYB", "DOW", "CENX", "AA", "FRO", "STNG", "ERII", "WEAT", "DBA"]
end_date = "2026-03-26"
start_date = "2025-03-26"

# Approximate market caps (USD) for these ETFs' underlying indices as of late March 2026
# Used so the EV-gap and LMSR analyses don't bail out on missing market_cap.
APPROX_MARKET_CAPS = {
    "INDA": 2.0e12,   # India broad market ~$2T
    "EWJ":  5.5e12,   # Japan broad market ~$5.5T
    "EWT":  1.8e12,   # Taiwan market ~$1.8T
    "UNG":  0.5e9,    # UNG fund AUM ~$500M
    "MCHI": 11.0e12,  # China broad market ~$11T
    "TSM":  0.9e12,   # TSMC ADR ~$900B
    "APD":  65e9,     # Air Products ~$65B
    "LIN":  200e9,    # Linde ~$200B
    "CF":   16e9,     # CF Industries ~$16B
    "NTR":  25e9,     # Nutrien ~$25B
    "MOS":  10e9,     # Mosaic ~$10B
    "LYB":  20e9,     # LyondellBasell ~$20B
    "DOW":  28e9,     # Dow ~$28B
    "CENX": 2e9,      # Century Aluminum ~$2B
    "AA":   10e9,     # Alcoa ~$10B
    "FRO":  4e9,      # Frontline ~$4B
    "STNG": 3.5e9,    # Scorpio Tankers ~$3.5B
    "ERII": 1.5e9,    # Energy Recovery ~$1.5B
    "WEAT": 0.2e9,    # Teucrium Wheat ETF ~$200M
    "DBA":  0.8e9,    # Invesco DB Ag ~$800M
}

cache = get_cache()

# ── Fetch Yahoo Finance data and inject into cache ──────────────────────────
print("Fetching ETF data from Yahoo Finance...")

for ticker in tickers:
    print(f"  {ticker}...", end=" ", flush=True)
    yticker = yf.Ticker(ticker)

    # --- Price data ---
    hist = yticker.history(start=start_date, end=end_date, auto_adjust=False)
    if hist.empty:
        print("NO DATA")
        continue

    prices = []
    for date, row in hist.iterrows():
        prices.append(Price(
            time=date.strftime("%Y-%m-%d"),
            open=round(float(row["Open"]), 2),
            close=round(float(row["Close"]), 2),
            high=round(float(row["High"]), 2),
            low=round(float(row["Low"]), 2),
            volume=int(row["Volume"]),
        ))

    # Cache with the exact key format get_prices() expects
    price_cache_key = f"{ticker}_{start_date}_{end_date}"
    cache.set_prices(price_cache_key, [p.model_dump() for p in prices])

    # The agent computes its own start_date = end_date - 365 days, which may
    # differ by a day from ours, so also cache a few nearby key variants.
    for delta in [-1, 0, 1]:
        alt_start = (datetime.fromisoformat(end_date) - timedelta(days=365 + delta)).date().isoformat()
        alt_key = f"{ticker}_{alt_start}_{end_date}"
        cache.set_prices(alt_key, [p.model_dump() for p in prices])

    # --- Synthetic financial metrics (so EV-gap & market_cap don't bail) ---
    last_close = prices[-1].close
    shares_outstanding = int(APPROX_MARKET_CAPS[ticker] / last_close) if last_close > 0 else 1

    synthetic_metrics = {
        "ticker": ticker,
        "report_period": end_date,
        "period": "ttm",
        "currency": "USD",
        "market_cap": APPROX_MARKET_CAPS[ticker],
        "enterprise_value": None,
        "price_to_earnings_ratio": None,
        "price_to_book_ratio": None,
        "price_to_sales_ratio": None,
        "enterprise_value_to_ebitda_ratio": None,
        "enterprise_value_to_revenue_ratio": None,
        "free_cash_flow_yield": None,
        "peg_ratio": None,
        "gross_margin": None,
        "operating_margin": None,
        "net_margin": None,
        "return_on_equity": None,
        "return_on_assets": None,
        "return_on_invested_capital": None,
        "asset_turnover": None,
        "inventory_turnover": None,
        "receivables_turnover": None,
        "days_sales_outstanding": None,
        "operating_cycle": None,
        "working_capital_turnover": None,
        "current_ratio": None,
        "quick_ratio": None,
        "cash_ratio": None,
        "operating_cash_flow_ratio": None,
        "debt_to_equity": None,
        "debt_to_assets": None,
        "interest_coverage": None,
        "revenue_growth": None,
        "earnings_growth": None,
        "book_value_growth": None,
        "earnings_per_share_growth": None,
        "free_cash_flow_growth": None,
        "operating_income_growth": None,
        "ebitda_growth": None,
        "payout_ratio": None,
        "earnings_per_share": None,
        "book_value_per_share": None,
        "free_cash_flow_per_share": None,
    }

    # Cache financial metrics with key variants the agent might use
    for period in ["ttm", "annual"]:
        for limit in [5, 10]:
            metrics_key = f"{ticker}_{period}_{end_date}_{limit}"
            cache.set_financial_metrics(metrics_key, [synthetic_metrics])

    print(f"{len(prices)} days cached, last close ${last_close}")

print()

# ── Run the hedge fund ──────────────────────────────────────────────────────
portfolio = {
    "cash": 100000.0,
    "margin_requirement": 0.0,
    "margin_used": 0.0,
    "positions": {
        t: {"long": 0, "short": 0, "long_cost_basis": 0.0, "short_cost_basis": 0.0, "short_margin_used": 0.0}
        for t in tickers
    },
    "realized_gains": {t: {"long": 0.0, "short": 0.0} for t in tickers},
}

result = run_hedge_fund(
    tickers=tickers,
    start_date=start_date,
    end_date=end_date,
    portfolio=portfolio,
    show_reasoning=True,
    selected_analysts=["nassim_taleb"],
    model_name="claude-sonnet-4-5-20250929",
    model_provider="Anthropic",
)

print("\n\n===== NASSIM TALEB STRANGLE ANALYSIS: IRAN SECOND-ORDER PLAYS =====")
print(json.dumps(result, indent=2, default=str))
