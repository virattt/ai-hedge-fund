"""
autoresearch/params_hl_hip3_sleeve.py — Hyperliquid HIP-3 sleeve experiment params.

This module starts from the global `autoresearch.params` defaults and then:
- Narrows the backtest universe to a small HIP-3 equity subset.
- Turns ON the first-wave fundamental / event filters.
- Points factor lookups at the `hl_hip3_sleeve_long` caches.

Run with:

    poetry run python -m autoresearch.evaluate \
      --params autoresearch.params_hl_hip3_sleeve \
      --prices-path prices_hl_hip3_sleeve_long.json \
      --tickers <subset of HIP-3 names>

You can later expand `BACKTEST_TICKERS` to the full HIP-3 sleeve.
"""

from autoresearch.params import *  # noqa: F401,F403


# ─────────────────────────────────────────────────────────────
# Sleeve-specific overrides
# ─────────────────────────────────────────────────────────────

# Start by experimenting on a small, representative subset; expand as desired.
# TODO: replace placeholders with your preferred HIP-3 core names.
BACKTEST_TICKERS = ["NVDA", "MSFT"]

# Use the Hyperliquid HIP-3 sleeve caches for fundamentals/events.
FACTOR_CACHE_PREFIX = "hl_hip3_sleeve_long"

# Turn on the first-wave factor filters using gentle thresholds so we modulate
# sizing rather than zeroing out trades.
USE_VALUE_FILTER = True
USE_QUALITY_FILTER = True
USE_INSIDER_FILTER = True

MIN_VALUE_SCORE = 0.1
MIN_QUALITY_SCORE = 0.1
INSIDER_NET_SELL_THRESHOLD = -0.1
INSIDER_SIZE_MULTIPLIER = 0.7

