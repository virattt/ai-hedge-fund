# Autoresearch Program — Networking Sector (ANET, AVGO, MRVL)

Maximize Sharpe for networking by tuning `params_networking.py`.

**Thesis:** Data center switching, custom AI ASICs. Ref: ikigaistudio "The Fund, Rebalanced" — Networking 22%.

**Baseline to beat:** `val_sharpe=0.669, val_return=+22.7%, OOS=-0.09` (EMA_LONG 40 improves OOS)

```bash
poetry run python -m autoresearch.evaluate --params autoresearch.params_networking
poetry run python -m autoresearch.evaluate --params autoresearch.params_networking --start 2025-08-01 --end 2026-03-07
```
