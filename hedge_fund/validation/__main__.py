"""Run the validation-gate scaffold on a saved backtest JSON.

Educational use only. This validation gate is a research scaffold
(CPCV / PBO hooks), not a trading green-light and not investment advice.
A report here does not authorize live capital, auto-promotion, or real trading.

Usage::

    python -m hedge_fund.validation path/to/backtest.json
        Offline. Reads FundBacktestResult (``nav``), BacktestResult
        (``equity_curve``), or a bare ``{\"returns\": [...]}`` object.
        Prints a ValidationReport as JSON on stdout. The educational
        disclaimer is also written to stderr.

    python -m hedge_fund.validation path/to/backtest.json --n-groups 6 \\
        --n-test-groups 2 --purge 1 --embargo 1 --pbo-groups 8
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hedge_fund.validation.gate import run_validation_gate
from hedge_fund.validation.models import EDUCATIONAL_DISCLAIMER


def main(argv: list[str] | None = None) -> int:
    """CLI entry. Educational use only — not a trading green-light."""
    parser = argparse.ArgumentParser(
        prog="python -m hedge_fund.validation",
        description=(
            "Run the CPCV / PBO validation-gate scaffold on a saved "
            "backtest JSON. Educational use only — not a trading "
            "green-light and not investment advice."
        ),
    )
    parser.add_argument(
        "backtest",
        help="path to a FundBacktestResult, BacktestResult, or returns JSON",
    )
    parser.add_argument("--n-groups", type=int, default=6, help="CPCV time groups (default 6)")
    parser.add_argument(
        "--n-test-groups",
        type=int,
        default=2,
        help="CPCV test groups per fold (default 2)",
    )
    parser.add_argument(
        "--purge",
        type=int,
        default=1,
        help="train bars dropped before each test block (default 1)",
    )
    parser.add_argument(
        "--embargo",
        type=int,
        default=1,
        help="train bars dropped after each test block (default 1)",
    )
    parser.add_argument(
        "--pbo-groups",
        type=int,
        default=8,
        help="even CSCV group count for the PBO hook (default 8)",
    )
    args = parser.parse_args(argv)

    path = Path(args.backtest).expanduser()
    if not path.is_file():
        print(f"validation gate: not a file: {path}", file=sys.stderr)
        return 2

    print(EDUCATIONAL_DISCLAIMER, file=sys.stderr)
    report = run_validation_gate(
        path,
        n_groups=args.n_groups,
        n_test_groups=args.n_test_groups,
        purge=args.purge,
        embargo=args.embargo,
        pbo_groups=args.pbo_groups,
    )
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
