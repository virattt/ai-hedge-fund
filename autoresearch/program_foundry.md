# Autoresearch Program — Foundry (TSM, GFS, UMC)

Maximize Sharpe for foundry by tuning `params_foundry.py`.

**Thesis:** Foundry monopoly + pure-plays. Ref: ikigaistudio TSM 14%.

**Baseline to beat:** 0.99 (RISK 0.38 → 1.03, OOS 1.22)

```bash
poetry run python -m autoresearch.evaluate --params autoresearch.params_foundry
```
