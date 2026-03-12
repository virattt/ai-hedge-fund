#!/bin/bash
# Daily paper trading run. Reads autoresearch/daily_config.json.
# Override with env: REFRESH_PRICES, DRY_RUN, DAILY_ALERT_URL.
# Cron: 0 16 * * 1-5 cd /path/to/ai-hedge-fund && ./autoresearch/run_daily.sh >> autoresearch/logs/daily.log 2>&1

set -e
cd "$(dirname "$0")/.."
exec poetry run python -m autoresearch.run_daily
