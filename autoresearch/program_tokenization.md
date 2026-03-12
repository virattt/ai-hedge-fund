# Autoresearch Program — Tokenization Sector (COIN, HOOD, CRCL)

Maximize Sharpe for tokenization by tuning `params_tokenization.py`.

**Thesis:** Crypto infrastructure, institutional + retail. Ref: ikigaistudio "The Fund, Rebalanced" — Tokenization 7%.

**Baseline to beat:** `val_sharpe=0.580, val_return=+15.6%, OOS=0.54`

```bash
poetry run python -m autoresearch.evaluate --params autoresearch.params_tokenization
poetry run python -m autoresearch.evaluate --params autoresearch.params_tokenization --start 2025-08-01 --end 2026-03-07
```
