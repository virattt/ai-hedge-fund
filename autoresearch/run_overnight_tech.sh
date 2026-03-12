#!/usr/bin/env bash
# Overnight autoresearch loop for tech sector (AAPL, NVDA, MSFT, GOOGL, TSLA)
# Usage: ./autoresearch/run_overnight_tech.sh
#
# Current baseline: val_sharpe=2.0358, val_return=+59.97%, OOS=1.38

set -e
cd "$(dirname "$0")/.."

echo "=== Tech Overnight Autoresearch ==="
echo "Baseline: sharpe=2.0358 | Run: poetry run python -m autoresearch.evaluate --params autoresearch.params_tech"
echo "OOS check: poetry run python -m autoresearch.evaluate --params autoresearch.params_tech --start 2025-08-01 --end 2026-03-07"
echo ""
echo "Read program_tech.md for the full loop."
echo ""

poetry run python -m autoresearch.evaluate --params autoresearch.params_tech 2>/dev/null | grep val_sharpe || true
