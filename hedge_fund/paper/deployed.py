"""A deployed fund: a mandate pointed at a universe, with a home on disk.

A mandate is the desk and names no tickers. Deploying it fixes the universe
and gives it a directory that the ledger, the broker's book and the kill
switch live in. The mandate is snapshotted into fund.yaml: a paper fund's
rules must not drift under it between ticks, and `execute_decision` refuses
to execute a decision made under a different spec.
"""

from __future__ import annotations

import re
from datetime import date as _date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from hedge_fund.brokers.paper import PaperBroker
from hedge_fund.fund import FundSpec, normalize_universe
from hedge_fund.paper.ledger import Ledger
from hedge_fund.paths import PAPER_DIR

FUND_FILE = "fund.yaml"
BROKER_FILE = "broker.json"

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class DeployedFund(BaseModel):
    """What fund.yaml holds."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = 2
    name: str
    spec: FundSpec                      # snapshot of the mandate at deploy time
    universe: list[str]
    broker: Literal["paper"] = "paper"
    created: str                        # YYYY-MM-DD


def validate_fund_name(name: str) -> str:
    """A fund name is a directory name: no separators, nothing hidden."""
    if not _NAME.fullmatch(name) or name in (".", ".."):
        raise ValueError(
            f"invalid fund name {name!r}: use letters, digits, '.', '_' or '-', "
            "starting with a letter or digit"
        )
    return name


def deploy(
    name: str, spec: FundSpec, universe: list[str], *, root: Path = PAPER_DIR,
) -> Path:
    """Create paper/<name>/ with an empty ledger and a book seeded with the
    mandate's capital. Returns the fund's directory. Refuses to overwrite."""
    validate_fund_name(name)
    universe = normalize_universe(universe)
    directory = Path(root) / name
    if directory.exists():
        raise FileExistsError(f"paper fund {name!r} already exists at {directory}")
    deployed = DeployedFund(
        name=name, spec=spec, universe=universe, created=_date.today().isoformat(),
    )
    directory.mkdir(parents=True)
    (directory / FUND_FILE).write_text(
        yaml.safe_dump(deployed.model_dump(), sort_keys=False)
    )
    PaperBroker.create(directory / BROKER_FILE, spec.capital)
    Ledger(directory).init()
    return directory


def load_deployed(directory: str | Path) -> DeployedFund:
    """Read paper/<name>/fund.yaml, raising ValueError with the path on any problem."""
    path = Path(directory) / FUND_FILE
    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f"{path}: cannot read the deployed fund: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: the deployed fund must be a YAML mapping")
    try:
        return DeployedFund.model_validate(data)
    except ValidationError as exc:
        errors = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise ValueError(f"{path}: {errors}") from exc


def list_deployed(root: Path = PAPER_DIR) -> list[Path]:
    """Every fund directory under *root*, in name order."""
    root = Path(root)
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir() if (p / FUND_FILE).is_file())
