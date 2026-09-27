"""Market-cap breakpoints — size as a percentile, not dollars.

A published monthly table gives every 5th percentile of listed US market
cap. Placing a company's filed market cap against the row for a past month
gives its size rank the way a factor model would report it: "above the 95th
percentile", never "$3.2T". The rank is stationary (the breakpoints grow
with the market) and survivorship-free (each row was computed from every
firm alive that month).

Point-in-time: the breakpoints for month M use end-of-month-M prices, so on
any day inside M they are not yet knowable. A filing in month M is placed
against the latest published row strictly before M.

The file is fetched into ~/.hedge-fund/cache/ and refreshed when it ages past
a month. It is third-party data and is not vendored.
"""

from __future__ import annotations

import io
import threading
import time
import zipfile
from datetime import date as _date
from pathlib import Path
from typing import Callable

import requests

from hedge_fund.paths import CACHE_DIR

BREAKPOINTS_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/ME_Breakpoints_CSV.zip"
)
DEFAULT_CACHE_PATH = CACHE_DIR / "breakpoints" / "ME_Breakpoints.csv"
MAX_AGE_DAYS = 35  # the table updates monthly

_PERCENTILES = tuple(range(5, 101, 5))  # 20 columns: 5th, 10th, ..., 100th
_MILLION = 1_000_000.0


class MEBreakpoints:
    """Monthly market-cap breakpoints, indexed by YYYYMM."""

    def __init__(self, rows: dict[str, tuple[float, ...]]) -> None:
        if not rows:
            raise ValueError("breakpoints table is empty")
        self._rows = dict(rows)
        self._months = sorted(self._rows)

    @classmethod
    def parse(cls, text: str) -> MEBreakpoints:
        """Parse the CSV: a prose header, one row per month, a footer.
        Row: YYYYMM, firm count, then 20 percentiles in $ millions."""
        rows: dict[str, tuple[float, ...]] = {}
        for line in text.splitlines():
            cells = [c.strip() for c in line.split(",")]
            if len(cells) != 2 + len(_PERCENTILES) or not (cells[0].isdigit() and len(cells[0]) == 6):
                continue
            rows[cells[0]] = tuple(float(c) for c in cells[2:])
        return cls(rows)

    @property
    def latest_month(self) -> str:
        return self._months[-1]

    def row_for(self, filing_date: str) -> tuple[str, tuple[float, ...]] | None:
        """The latest published row strictly before the filing month."""
        filed = _date.fromisoformat(filing_date[:10])
        cutoff = f"{filed.year}{filed.month:02d}"
        eligible = [m for m in self._months if m < cutoff]
        if not eligible:
            return None
        month = eligible[-1]
        return month, self._rows[month]

    def size_percentile(self, market_cap: float | None, filing_date: str) -> int | None:
        """Highest percentile breakpoint the market cap (in dollars) meets or
        exceeds, in steps of 5, capped at 95. 0 means below the 5th
        percentile. None when there is no market cap or no published row.

        The cap is for the blind prompt's sake: the 100th breakpoint is the
        single largest firm in the table, so "above it" names a handful of
        mega-caps. "At or above the 95th" is a few dozen companies.
        """
        if market_cap is None or market_cap <= 0:
            return None
        row = self.row_for(filing_date)
        if row is None:
            return None
        _, thresholds = row
        millions = market_cap / _MILLION
        exceeded = sum(1 for t in thresholds if millions >= t)
        return min(exceeded, 19) * 5


def fetch_breakpoints_csv(url: str = BREAKPOINTS_URL, timeout: float = 30.0) -> str:
    """Download the zip and return the CSV text inside it."""
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise ValueError(f"{url}: no CSV inside the archive")
        return archive.read(names[0]).decode("utf-8", errors="replace")


def load_breakpoints(
    cache_path: Path | str = DEFAULT_CACHE_PATH,
    *,
    max_age_days: int = MAX_AGE_DAYS,
    fetch: Callable[[], str] = fetch_breakpoints_csv,
) -> MEBreakpoints:
    """Read the cached CSV, refreshing it when stale or missing.

    A stale cache that cannot be refreshed is still used: the rows a
    backtest looks up are months old regardless. No cache and no fetch is
    an error — a blind prompt must not silently change shape.
    """
    path = Path(cache_path)
    fresh = path.exists() and (time.time() - path.stat().st_mtime) < max_age_days * 86400
    if not fresh:
        try:
            text = fetch()
        except Exception:
            if not path.exists():
                raise
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    return MEBreakpoints.parse(path.read_text())


_shared: MEBreakpoints | None = None
_shared_lock = threading.Lock()


def shared_breakpoints() -> MEBreakpoints:
    """Process-wide table, loaded once. Blind agents on many threads
    (the TUI warms them in parallel) share it."""
    global _shared
    with _shared_lock:
        if _shared is None:
            _shared = load_breakpoints()
        return _shared
