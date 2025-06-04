# 0002 - Enable Crypto Asset Class

## Context

The platform originally supported only equity trading using daily OHLCV data. Expanding to spot crypto pairs requires new data sources, risk constraints, and agent logic.

## Decision

Introduce a feature flag `ASSET_CLASS` defaulting to `EQUITY`. When set to `CRYPTO`, the system routes price data through CCXT, adds crypto specific analysts, and adjusts risk management.

## Consequences

- Maintains backward compatibility with equity workflows.
- Adds dependencies on `ccxt` and `pycoingecko`.
- CI runs test suites for both asset classes.
