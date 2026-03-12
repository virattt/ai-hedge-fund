# Autoresearch Program — Healthcare Sector (JNJ, UNH, PFE, ABBV, LLY)

Maximize Sharpe for healthcare by tuning `params_healthcare.py`.

**Baseline to beat:** `val_sharpe=0.3864, val_return=+12.19%, OOS=2.71`

```bash
poetry run python -m autoresearch.evaluate --params autoresearch.params_healthcare
poetry run python -m autoresearch.evaluate --params autoresearch.params_healthcare --start 2025-08-01 --end 2026-03-07
```
