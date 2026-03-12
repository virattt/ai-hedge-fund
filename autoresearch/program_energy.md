# Autoresearch Program — Energy Sector (XOM, CVX, OXY, SLB, EOG)

Maximize Sharpe for energy by tuning `params_energy.py`.

**Baseline to beat:** `val_sharpe=0.6852, val_return=+19.4%, OOS=1.46`

```bash
poetry run python -m autoresearch.evaluate --params autoresearch.params_energy
poetry run python -m autoresearch.evaluate --params autoresearch.params_energy --start 2025-08-01 --end 2026-03-07
```
