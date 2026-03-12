# Autoresearch Program — EDA Sector (SNPS, CDNS)

Maximize Sharpe for EDA by tuning `params_eda.py`.

**Thesis:** Duopoly, infinite switching costs, design-starts growth. Most durable category per ikigaistudio.

**Baseline to beat:** val_sharpe=-0.14 (3-ticker: SNPS, CDNS, ARM). Strategy still negative; design-tool regime may differ from momentum/equipment.

```bash
poetry run python -m autoresearch.evaluate --params autoresearch.params_eda
poetry run python -m autoresearch.evaluate --params autoresearch.params_eda --start 2025-08-01 --end 2026-03-07
```
