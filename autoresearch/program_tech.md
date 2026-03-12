# Autoresearch Program — Tech Sector (AAPL, NVDA, MSFT, GOOGL, TSLA)

Maximize Sharpe for tech by tuning `params_tech.py`.

**Baseline to beat:** `val_sharpe=2.0358, val_return=+59.97%, OOS=1.38`

```bash
poetry run python -m autoresearch.evaluate --params autoresearch.params_tech
poetry run python -m autoresearch.evaluate --params autoresearch.params_tech --start 2025-08-01 --end 2026-03-07
```
