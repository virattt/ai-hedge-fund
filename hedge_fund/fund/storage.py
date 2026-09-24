"""Read-only discovery of saved fund configurations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hedge_fund.fund.spec import FundSpec, load_spec


@dataclass(frozen=True)
class SavedFund:
    """A saved mandate, or its loading error when unavailable."""

    path: Path
    spec: FundSpec | None = None
    error: str | None = None


def discover_funds(directory: str | Path) -> list[SavedFund]:
    """List YAML mandates in filename order, retaining invalid files as errors.

    Files are read independently and never modified. A missing directory
    returns an empty list.
    """
    entries: list[SavedFund] = []
    for path in sorted(Path(directory).glob("*.yaml")):
        try:
            entries.append(SavedFund(path, spec=load_spec(path)))
        except ValueError as exc:
            entries.append(SavedFund(path, error=str(exc)))
    return entries
