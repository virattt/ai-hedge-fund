"""Run the event study engine. Screen-record friendly output.

Usage: poetry run python -m hedge_fund.event_study
"""

from __future__ import annotations

import sys
import time

from hedge_fund.data import FDClient
from hedge_fund.event_study import compute_car


TICKERS = [
    # Tech (21)
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "NFLX", "CRM", "ADBE",
    "ORCL", "INTC", "AMD", "CSCO", "IBM", "UBER", "SHOP", "SNOW", "PLTR", "PANW", "CRWD",
    # Financials (15)
    "JPM", "GS", "BAC", "WFC", "MS", "C", "BLK", "SCHW", "AXP", "COF",
    "USB", "PNC", "TFC", "BK", "CME",
    # Healthcare (15)
    "JNJ", "PFE", "UNH", "MRK", "LLY", "ABBV", "TMO", "ABT", "BMY", "AMGN",
    "GILD", "ISRG", "VRTX", "REGN", "MDT",
    # Energy (8)
    "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX",
    # Consumer / Retail (15)
    "HD", "LOW", "COST", "WMT", "KO", "PEP", "MCD", "SBUX", "NKE", "TGT",
    "TJX", "ROST", "DG", "DLTR", "YUM",
    # Industrials (10)
    "CAT", "DE", "HON", "UPS", "RTX", "BA", "LMT", "GE", "MMM", "UNP",
    # Media / Telecom (7)
    "DIS", "CMCSA", "T", "VZ", "TMUS", "CHTR", "WBD",
    # Other (10)
    "V", "MA", "PYPL", "NEE", "D", "SO", "DUK", "ABNB", "COIN", "NOW",
]
EARNINGS_LIMIT = 8

GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[90m"
RESET = "\033[0m"


def progress(text: str) -> None:
    sys.stdout.write(f"\r{text}")
    sys.stdout.flush()


def typed(text: str, delay: float = 0.02) -> None:
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\n")
    sys.stdout.flush()


def color_car(v: float | None) -> str:
    if v is None:
        return f"{DIM}{'N/A':>8}{RESET}"
    pct = v * 100
    s = f"{pct:+7.2f}%"
    c = GREEN if pct >= 0 else RED
    return f"{c}{s}{RESET}"


def color_eps(s: str | None) -> str:
    if s == "BEAT":
        return f"{GREEN}BEAT{RESET}"
    if s == "MISS":
        return f"{RED}MISS{RESET}"
    if s == "MEET":
        return "MEET"
    return f"{DIM}   -{RESET}"


def main() -> None:
    import logging
    logging.getLogger("hedge_fund.data.client").setLevel(logging.ERROR)

    n = len(TICKERS)

    # Fetch with progress
    progress(f"Fetching data... [0/{n}]")
    with FDClient() as fd:
        from datetime import date
        spy_prices = fd.get_prices("SPY", "2023-01-01", date.today().isoformat())
        spy_closes = {p.time[:10]: p.close for p in spy_prices}

        from hedge_fund.event_study.engine import _compute_ticker_events
        all_events = []
        for i, ticker in enumerate(TICKERS):
            progress(f"Fetching data... [{i + 1}/{n}] {ticker}")
            events = _compute_ticker_events(ticker, fd, spy_closes, earnings_limit=EARNINGS_LIMIT)
            all_events.extend(events)

    # Filter to labeled events only
    all_events = [e for e in all_events if e.eps_surprise is not None]

    # Aggregate
    from hedge_fund.event_study.engine import _aggregate
    aggregates = _aggregate(all_events, 10_000, 42)

    # Clear progress line
    sys.stdout.write("\r" + " " * 60 + "\r")
    sys.stdout.flush()

    typed(f"Event Study: {len(all_events)} earnings events across {len(set(e.ticker for e in all_events))} tickers")
    print()

    print(f"  {'Ticker':<6} {'Date':<12} {'Type':<6} {'EPS':<4}  {'CAR[0,1]':>8} {'CAR[0,5]':>8} {'CAR[0,20]':>8}   {'Beta':>5} {'R2':>5}")
    print(f"  {'-' * 78}")

    for e in sorted(all_events, key=lambda x: (x.ticker, x.event_date)):
        eps = color_eps(e.eps_surprise)
        c1 = color_car(e.car_0_1)
        c5 = color_car(e.car_0_5)
        c20 = color_car(e.car_0_20)

        print(
            f"  {e.ticker:<6} {e.event_date:<12} {e.source_type:<6} {eps}"
            f"  {c1} {c5} {c20}"
            f"   {e.market_model.beta:5.2f} {e.market_model.r_squared:5.2f}"
        )
        time.sleep(0.6)

    print()
    typed(f"{len(all_events)} events. Done.")


if __name__ == "__main__":
    from hedge_fund.tui.keys import apply_credentials
    apply_credentials()
    main()
