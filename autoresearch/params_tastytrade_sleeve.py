"""
autoresearch/params_tastytrade_sleeve.py — Tastytrade sleeve experiment params.

This module starts from the global `autoresearch.params` defaults and then:
- Narrows the backtest universe to the tastytrade AI infra sleeve.
- Turns ON the first-wave fundamental / event filters.
- Points factor lookups at the `tastytrade_sleeve_long` caches.

Run with:

    poetry run python -m autoresearch.evaluate \
      --params autoresearch.params_tastytrade_sleeve \
      --prices-path prices_tastytrade_sleeve_long.json \
      --tickers ASML,AMAT

You can later expand `BACKTEST_TICKERS` to the full sleeve universe.
"""

from autoresearch.params import *  # noqa: F401,F403


# ─────────────────────────────────────────────────────────────
# Sleeve-specific overrides
# ─────────────────────────────────────────────────────────────

# Start by experimenting on the core choke points; expand as desired.
BACKTEST_TICKERS = ["ASML", "AMAT"]

# Use the tastytrade sleeve caches for fundamentals/events.
FACTOR_CACHE_PREFIX = "tastytrade_sleeve_long"

# Turn on the first-wave factor filters, but start with gentle thresholds so
# we don't zero out all trades for this small test universe.
USE_VALUE_FILTER = True
USE_QUALITY_FILTER = True
USE_INSIDER_FILTER = True

# Soften the thresholds relative to the global defaults for experimentation.
MIN_VALUE_SCORE = 0.1
MIN_QUALITY_SCORE = 0.1
INSIDER_NET_SELL_THRESHOLD = -0.1
INSIDER_SIZE_MULTIPLIER = 0.7

