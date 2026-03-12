#!/usr/bin/env bash
# Overnight autoresearch loop for equipment sector
# Usage: ./autoresearch/run_overnight_equipment.sh
# Or: bash autoresearch/run_overnight_equipment.sh
#
# This script runs the equipment autoresearch loop. Point an AI agent (Claude, Cursor, etc.)
# at program_equipment.md and have it execute this loop for 8+ hours.
#
# Current baseline to beat: val_sharpe=1.8589, val_return=+94.96%, OOS=2.35

set -e
cd "$(dirname "$0")/.."

echo "=== Equipment Overnight Autoresearch ==="
echo "Baseline: sharpe=1.8464 | Run: poetry run python -m autoresearch.evaluate --params autoresearch.params_equipment"
echo "OOS check: poetry run python -m autoresearch.evaluate --params autoresearch.params_equipment --start 2025-08-01 --end 2026-03-07"
echo ""
echo "Read program_equipment.md for the full loop. Key commands:"
echo "  poetry run python -m autoresearch.evaluate --params autoresearch.params_equipment"
echo "  git checkout autoresearch/params_equipment.py   # revert bad change"
echo "  git add autoresearch/params_equipment.py autoresearch/results_equipment.tsv && git commit -m 'autoresearch[equip]: ...'"
echo ""
echo "Still untried: BOLLINGER_WINDOW 25/30, MOM_6M 0.1, RISK_EXTREME_VOL 0.4/0.6, VOL_HIGH_REGIME, ADX 35/45"
echo ""

# Quick sanity check
poetry run python -m autoresearch.evaluate --params autoresearch.params_equipment 2>/dev/null | grep val_sharpe || true
