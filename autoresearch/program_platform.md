# Autoresearch Program — Platform (MSFT, AMZN, GOOGL, META, ORCL, PLTR)

Maximize Sharpe for platform/enterprise AI by tuning `params_platform.py`.

**Thesis:** Hyperscalers + enterprise AI. Ref: ikigaistudio Platform 45%.

**Baseline to beat:** 0.96 (SIG 0.36 + RISK 0.38 → 1.29, OOS 0.22)

```bash
poetry run python -m autoresearch.evaluate --params autoresearch.params_platform
```
