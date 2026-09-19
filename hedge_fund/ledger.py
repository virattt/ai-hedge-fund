"""Persistent ledger — CycleRecord receipts, write and read.

Every live-clock paper run writes a receipt (cash, positions, NAV, every
thesis). The next run loads the newest CycleRecord for that mandate and
seeds PaperBroker from the ending book, so NAV is a track record instead
of a reset to the mandate's capital.

Backtests do not read the ledger. They open a fresh SimBroker at the
mandate's capital and carry the book only across ticks inside that run.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from hedge_fund.brokers.paper import PaperBroker
from hedge_fund.pipeline.models import CycleRecord


def run_receipt_paths(fund_name: str, directory: Path) -> list[Path]:
    """This mandate's `{name}-run-*.json` receipts, newest first by mtime."""
    paths = list(directory.glob(f"{fund_name}-run-*.json"))
    return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)


def latest_run_receipt(fund_name: str, directory: Path) -> Path | None:
    """Newest run receipt for *fund_name*, or None if it has never run."""
    paths = run_receipt_paths(fund_name, directory)
    return paths[0] if paths else None


def load_cycle_record(
    path: Path,
    *,
    expected_fund: str | None = None,
) -> CycleRecord:
    """Load a CycleRecord. Corrupt or incompatible receipts raise.

    A backtest result sitting on a run-receipt path is incompatible — it
    is not a CycleRecord. A fund-name mismatch against *expected_fund*
    is incompatible. JSON or schema failures are corrupt. The caller must
    not skip to an older file; the newest receipt is the book.
    """
    try:
        text = path.read_text()
    except OSError as exc:
        raise ValueError(f"corrupt receipt {path}: {exc}") from exc

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"corrupt receipt {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"corrupt receipt {path}: expected a JSON object")

    if "metrics" in raw and "records" in raw:
        raise ValueError(
            f"incompatible receipt {path}: expected a CycleRecord, "
            f"got a backtest result"
        )

    try:
        record = CycleRecord.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"corrupt receipt {path}: {exc}") from exc

    if expected_fund is not None and record.fund != expected_fund:
        raise ValueError(
            f"incompatible receipt {path}: fund {record.fund!r} "
            f"does not match mandate {expected_fund!r}"
        )
    return record


def save_cycle_record(record: CycleRecord, directory: Path) -> Path:
    """Write *record* as this mandate's newest run receipt. Returns the path."""
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    path = directory / f"{record.fund}-run-{stamp}.json"
    path.write_text(record.model_dump_json(indent=2))
    return path


def broker_for_run(
    fund_name: str,
    capital: float,
    directory: Path,
) -> tuple[PaperBroker, CycleRecord | None]:
    """Open a PaperBroker for a live-clock paper run of *fund_name*.

    If a prior CycleRecord exists, the broker is seeded from that ending
    book (cash + signed shares). If not, it opens at *capital*. The newest
    receipt is the only candidate — a corrupt or incompatible file raises
    rather than falling back to capital or to an older receipt.
    """
    path = latest_run_receipt(fund_name, directory)
    if path is None:
        return PaperBroker(cash=capital), None
    record = load_cycle_record(path, expected_fund=fund_name)
    return PaperBroker(cash=record.cash, positions=record.positions), record
