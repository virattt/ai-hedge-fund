"""Saved fund configurations on disk: find them, and write a new one."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

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


def save_spec(spec: FundSpec, directory: str | Path) -> Path:
    """Write *spec* as <directory>/<name>.yaml and return the path.

    Never overwrites: raises FileExistsError when a mandate already holds the
    name, so two writers racing for it cannot silently lose one.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{spec.name}.yaml"
    with path.open("x") as output:
        output.write(yaml.safe_dump(spec.model_dump(), sort_keys=False))
    return path
