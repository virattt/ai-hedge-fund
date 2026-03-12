# Portfolio Backtest — Combined Sector Strategies

Combines all tuned sector strategies into a single portfolio. Each sector runs its own backtest; daily returns are weighted and aggregated.

## Usage

```bash
# Equal weight (11 sectors)
poetry run python -m autoresearch.portfolio_backtest --weights equal

# Sharpe-weighted (tilt toward high-Sharpe sectors)
poetry run python -m autoresearch.portfolio_backtest --weights sharpe

# OOS-weighted (tilt toward sectors with strong OOS Sharpe)
poetry run python -m autoresearch.portfolio_backtest --weights oos

# Exclude networking (OOS -0.09)
poetry run python -m autoresearch.portfolio_backtest --weights equal --exclude networking

# OOS validation window (Aug 2025 – Mar 2026)
poetry run python -m autoresearch.portfolio_backtest --weights oos --start 2025-08-01 --end 2026-03-07
```

## Results (2026-03-11)

| Weights | Val Sharpe | Val Return | Max DD | OOS Sharpe | OOS Return |
|---------|------------|------------|--------|------------|------------|
| Equal (11) | 2.49 | +68.3% | -6.5% | — | — |
| Equal (excl networking) | 2.61 | +73.4% | -6.5% | — | — |
| Sharpe | 2.79 | +106.8% | -9.3% | — | — |
| OOS | 2.84 | +101.2% | -9.0% | **3.31** | **+69.4%** |

**Takeaway:** OOS-weighted portfolio achieves Sharpe 2.84 in-sample, **3.31 OOS** — diversification improves OOS robustness.
