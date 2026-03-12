#!/bin/bash
# Refresh price caches for all sectors. Run from project root.
# Requires: poetry, POLYGON_API_KEY or similar for price data

set -e
cd "$(dirname "$0")/.."

echo "Refreshing all sector price caches..."
echo ""

# SPY for regime detection (broad market)
poetry run python -m autoresearch.cache_signals --tickers SPY --prices-only --prices-path prices_benchmark.json

# Sector tickers from SECTOR_CONFIG in portfolio_backtest.py
poetry run python -m autoresearch.cache_signals --tickers MU,WDC,STX --prices-only --prices-path prices_memory.json
poetry run python -m autoresearch.cache_signals --tickers LITE,COHR --prices-only --prices-path prices_photonics.json
poetry run python -m autoresearch.cache_signals --tickers AAPL,NVDA,MSFT,GOOGL,TSLA --prices-only --prices-path prices.json
poetry run python -m autoresearch.cache_signals --tickers AMAT,ASML,LRCX,KLAC,TEL --prices-only --prices-path prices_equipment.json
poetry run python -m autoresearch.cache_signals --tickers MSFT,AMZN,GOOGL,META,ORCL,PLTR --prices-only --prices-path prices_platform.json
poetry run python -m autoresearch.cache_signals --tickers TSM,GFS,UMC --prices-only --prices-path prices_foundry.json
poetry run python -m autoresearch.cache_signals --tickers VRT,CEG,EQT --prices-only --prices-path prices_power_infra.json
poetry run python -m autoresearch.cache_signals --tickers XOM,CVX,OXY,SLB,EOG --prices-only --prices-path prices_energy.json
poetry run python -m autoresearch.cache_signals --tickers ANET,AVGO,MRVL --prices-only --prices-path prices_networking.json
poetry run python -m autoresearch.cache_signals --tickers COIN,HOOD,CRCL --prices-only --prices-path prices_tokenization.json
poetry run python -m autoresearch.cache_signals --tickers JNJ,UNH,PFE,ABBV,LLY --prices-only --prices-path prices_healthcare.json

echo ""
echo "All prices refreshed. Run: poetry run python -m autoresearch.portfolio_backtest --weights oos"
