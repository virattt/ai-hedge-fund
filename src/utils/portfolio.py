"""Utilities for working with portfolio data structures."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


def merge_portfolio_structures(base_portfolio: Dict[str, Any], override: Dict[str, Any] | None) -> Dict[str, Any]:
    """Merge persisted portfolio data into a base portfolio template."""

    if not override:
        return deepcopy(base_portfolio)

    merged = deepcopy(base_portfolio)

    for key, value in override.items():
        if key in {"positions", "realized_gains"} and isinstance(value, dict):
            section = merged.setdefault(key, {})
            for ticker, ticker_payload in value.items():
                if isinstance(ticker_payload, dict):
                    existing = section.get(ticker, {})
                    if isinstance(existing, dict):
                        updated = existing.copy()
                        updated.update(ticker_payload)
                        section[ticker] = updated
                    else:
                        section[ticker] = deepcopy(ticker_payload)
                else:
                    section[ticker] = ticker_payload
        else:
            merged[key] = deepcopy(value)

    return merged


__all__ = ["merge_portfolio_structures"]

