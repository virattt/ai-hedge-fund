"""PaperBroker — SimBroker's fills, persisted to disk between ticks.

A paper fund's book must outlive the process that placed its orders, and it
must be a SECOND book: the ledger says what the fund believes it holds, the
broker says what it actually holds, and `advance` reconciles the two before
every session. Keeping them in separate files is what makes that check mean
something — a single file could never disagree with itself.

Fills are SimBroker's: complete, at the order's reference price (the
execution session's close). The file is rewritten atomically after every
fill, so a crash between two fills leaves a book that is exactly the fills
that happened — and the next tick's reconciliation will refuse to trade on
it until someone looks.
"""

from __future__ import annotations

import json
from pathlib import Path

from hedge_fund.brokers.models import Fill, Order
from hedge_fund.brokers.sim import SimBroker
from hedge_fund.paths import write_atomic


class PaperBroker(SimBroker):
    """A SimBroker whose book lives in a JSON file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        try:
            data = json.loads(self._path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"{self._path}: cannot read the paper broker's book: {exc}") from exc
        super().__init__(cash=float(data["cash"]))
        self._shares = {
            ticker: int(shares) for ticker, shares in data.get("shares", {}).items()
            if int(shares) != 0
        }

    @classmethod
    def create(cls, path: str | Path, cash: float) -> PaperBroker:
        """Open a new, empty book at *path*. Refuses to overwrite one."""
        path = Path(path)
        if path.exists():
            raise FileExistsError(f"{path}: a paper broker book already exists")
        path.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(path, json.dumps({"cash": cash, "shares": {}}, indent=2))
        return cls(path)

    @classmethod
    def restore(cls, path: str | Path, cash: float, shares: dict[str, int]) -> PaperBroker:
        """Rewrite the book wholesale to a known state. Only a redo does this,
        to put the book back where the ledger says it was before the session
        being run again; the fills of that session are discarded with it."""
        write_atomic(Path(path), json.dumps({
            "cash": cash, "shares": {t: s for t, s in sorted(shares.items()) if s != 0},
        }, indent=2))
        return cls(path)

    @property
    def path(self) -> Path:
        return self._path

    def place_order(self, order: Order) -> Fill:
        fill = super().place_order(order)
        self._save()
        return fill

    def _save(self) -> None:
        write_atomic(self._path, json.dumps({
            "cash": self._cash,
            "shares": dict(sorted(self._shares.items())),
        }, indent=2))
