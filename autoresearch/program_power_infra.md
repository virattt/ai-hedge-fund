# Autoresearch Program — Power Infrastructure (VRT, CEG, EQT)

Maximize Sharpe for power by tuning `params_power_infra.py`.

**Thesis:** Vertiv (data center thermal), Constellation (nuclear/grid), EQT (natural gas). Ref: ikigaistudio Power 16%.

**Baseline to beat:** `val_sharpe=1.08, val_return=+40.8%, OOS=0.68`

```bash
poetry run python -m autoresearch.evaluate --params autoresearch.params_power_infra
poetry run python -m autoresearch.evaluate --params autoresearch.params_power_infra --start 2025-08-01 --end 2026-03-07
```
