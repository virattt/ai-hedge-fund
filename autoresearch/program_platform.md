# Autoresearch Program — Platform (MSFT, AMZN, GOOGL, META, ORCL, PLTR)

Maximize Sharpe for platform/enterprise AI by tuning `params_platform.py`.

**Thesis:** Hyperscalers + enterprise AI. Ref: ikigaistudio Platform 45%.

**Baseline to beat:** 1.21 val, OOS 0.33 (EMA 40, RISK_EXT 0.60, SIG 0.32)

```bash
poetry run python -m autoresearch.evaluate --params autoresearch.params_platform
```
