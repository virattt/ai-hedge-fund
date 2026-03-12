#!/usr/bin/env bash
# Overnight autoresearch loop for memory sector (MU, WDC, STX)
# Usage: ./autoresearch/run_overnight_memory.sh
#
# Point an AI agent at program_memory.md and have it execute the loop.
#
# Current baseline: val_sharpe=2.6128, val_return=+264.15%, OOS=2.98

set -e
cd "$(dirname "$0")/.."

echo "=== Memory Overnight Autoresearch ==="
echo "Baseline: sharpe=2.6128 | Run: poetry run python -m autoresearch.evaluate --params autoresearch.params_memory"
echo "OOS check: poetry run python -m autoresearch.evaluate --params autoresearch.params_memory --start 2025-08-01 --end 2026-03-07"
echo ""
echo "Read program_memory.md for the full loop."
echo ""

poetry run python -m autoresearch.evaluate --params autoresearch.params_memory 2>/dev/null | grep val_sharpe || true
