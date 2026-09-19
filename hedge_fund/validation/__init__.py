"""Validation-gate scaffold — CPCV splits and a PBO hook.

Educational use only. This validation gate is a research scaffold
(CPCV / PBO hooks), not a trading green-light and not investment advice.
A report here does not authorize live capital, auto-promotion, or real trading.

Public surface:

- ``run_validation_gate`` — returns / equity curve / saved backtest JSON
  → ``ValidationReport`` (CPCV fold summaries + PBO placeholder/hook)
- ``cpcv_splits`` — combinatorial purged / embargoed index splits
- ``estimate_pbo`` — tiny CSCV rank PBO when several trials exist;
  documented single-series heuristic otherwise

This is not the research lab and not auto-promotion. Those hang off this
report later. ``python -m hedge_fund.validation path/to/backtest.json``
runs the gate offline.
"""

from hedge_fund.validation.cpcv import CPCVSplit, cpcv_splits, period_sharpe
from hedge_fund.validation.gate import (
    equity_to_returns,
    load_backtest_returns,
    run_validation_gate,
)
from hedge_fund.validation.models import (
    EDUCATIONAL_DISCLAIMER,
    CPCVFold,
    CPCVResult,
    PBOResult,
    ValidationReport,
)
from hedge_fund.validation.pbo import estimate_pbo

__all__ = [
    "EDUCATIONAL_DISCLAIMER",
    "CPCVFold",
    "CPCVResult",
    "CPCVSplit",
    "PBOResult",
    "ValidationReport",
    "cpcv_splits",
    "equity_to_returns",
    "estimate_pbo",
    "load_backtest_returns",
    "period_sharpe",
    "run_validation_gate",
]
