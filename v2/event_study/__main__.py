"""Run the event study engine. Screen-record friendly output.

Usage: poetry run python -m v2.event_study
"""

from __future__ import annotations

import sys
import time

from v2.data import FDClient
from v2.event_study import compute_car


TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "TSLA"]
EARNINGS_LIMIT = 8

GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[90m"
RESET = "\033[0m"


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
    typed("Computing CARs...")
    print()

    with FDClient() as fd:
        result = compute_car(TICKERS, fd, earnings_limit=EARNINGS_LIMIT, rng_seed=42)

    print(f"  {'Ticker':<6} {'Date':<12} {'Type':<6} {'EPS':<4}  {'CAR[0,1]':>8} {'CAR[0,5]':>8} {'CAR[0,20]':>8}   {'Beta':>5} {'R2':>5}")
    print(f"  {'-' * 78}")

    for e in sorted(result.events, key=lambda x: (x.ticker, x.event_date)):
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
    typed(f"{len(result.events)} events across {len(set(e.ticker for e in result.events))} tickers.")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
