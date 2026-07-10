"""Ask any analyst for a point-in-time view on a ticker.

Usage::

    poetry run python -m v2.analyze NVDA
    poetry run python -m v2.analyze NVDA --date 2024-06-01
    poetry run python -m v2.analyze AAPL --date 2025-08-01 --agent pead

The date is the as-of date: the analyst may only use data that was publicly
filed by then. Try the same ticker on two different dates.
"""

from __future__ import annotations

import argparse
from datetime import date as _date

from dotenv import load_dotenv

from v2.data import FDClient
from v2.signals import ALPHA_MODEL_REGISTRY


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="python -m v2.analyze",
        description="Point-in-time analyst view on a ticker.",
    )
    parser.add_argument("ticker", help="ticker symbol, e.g. NVDA")
    parser.add_argument(
        "--date",
        default=_date.today().isoformat(),
        help="as-of date YYYY-MM-DD (default: today). The analyst only sees "
        "data filed by this date.",
    )
    parser.add_argument(
        "--agent",
        default="buffett",
        choices=sorted(ALPHA_MODEL_REGISTRY),
        help="which analyst to ask (default: buffett)",
    )
    args = parser.parse_args()

    model = ALPHA_MODEL_REGISTRY[args.agent]()
    with FDClient() as fd:
        signal = model.predict(args.ticker.upper(), args.date, fd)

    bar = "─" * 62
    direction = "BULLISH" if signal.value > 0 else "BEARISH" if signal.value < 0 else "NEUTRAL"
    print(bar)
    print(f"  {args.agent.upper()} on {signal.ticker}   (as of {signal.date})")
    print(bar)
    print(f"  view:        {direction}  ({signal.value:+.2f})")
    if signal.metadata.get("confidence") is not None:
        print(f"  confidence:  {signal.metadata['confidence']:.0f}/100")
    if signal.metadata.get("model"):
        cached = "  [cached]" if signal.metadata.get("cached") else ""
        print(f"  model:       {signal.metadata['model']}{cached}")
    print(bar)
    if signal.reasoning:
        print(f"  {signal.reasoning}")
        print(bar)


if __name__ == "__main__":
    main()
