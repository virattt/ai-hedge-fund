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
import time
from datetime import date as _date

from dotenv import load_dotenv
from rich.console import Console

from v2.data import CachedDataClient, FDClient
from v2.features import InsufficientData
from v2.signals import ALPHA_MODEL_REGISTRY, LLMAgent


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
    ticker = args.ticker.upper()
    console = Console(stderr=True)  # spinner on stderr; results stay pipeable

    started = time.time()
    with FDClient() as raw:
        # Disk cache: the snapshot built for the spinner is re-read for free
        # inside predict, and re-asking the same (ticker, date) costs nothing.
        fd = CachedDataClient(raw)
        with console.status(
            f"[cyan]building point-in-time snapshot of {ticker} "
            f"(only data filed by {args.date})…",
            spinner="dots",
        ) as status:
            if isinstance(model, LLMAgent):
                try:
                    snapshot = model.build_snapshot(ticker, args.date, fd)
                    status.update(
                        f"[bold cyan]{args.agent}[/] is reading "
                        f"{len(snapshot.periods)} quarters of fundamentals "
                        f"and thinking…",
                        spinner="aesthetic",
                    )
                except InsufficientData:
                    pass  # predict() will produce the abstain signal
            signal = model.predict(ticker, args.date, fd)
    elapsed = time.time() - started

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
        print(f"  model:       {signal.metadata['model']}{cached}  ({elapsed:.1f}s)")
    print(bar)
    if signal.reasoning:
        print(f"  {signal.reasoning}")
        print(bar)


if __name__ == "__main__":
    main()
