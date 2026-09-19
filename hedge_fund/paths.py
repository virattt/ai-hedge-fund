"""Where user data lives: ~/.hedge-fund/.

Everything the user owns — mandates, run/backtest receipts, API caches, the
scheduler kill-switch, tick keys, and the .env key file — lives under one
home directory, outside the package. The package directory stays read-only
code, so a pipx install behaves exactly like a checkout. Live-clock receipts
are `{fund}-run-*.json` next to the mandate; the next run seeds its broker
from the newest one. The scheduler writes `{fund}_{session}.tick` keys
under `ticks/` so a double-fire of the same mandate+session is a no-op.

Textual-free and import-light on purpose: every layer (CLI, TUI, caches)
anchors its paths here, and nothing here may import them back.
"""

from __future__ import annotations

import shutil
from pathlib import Path

USER_DIR = Path.home() / ".hedge-fund"
MANDATES_DIR = USER_DIR / "mandates"
CACHE_DIR = USER_DIR / "cache"
ENV_PATH = USER_DIR / ".env"
TICKS_DIR = USER_DIR / "ticks"
KILL_SWITCH_PATH = USER_DIR / "KILL"

# The example mandate ships inside the package; it is copied out (never read
# in place) so users edit their copy, not the install.
EXAMPLE_MANDATE = Path(__file__).resolve().parent / "fund" / "example.yaml"


def ensure_mandates_dir() -> Path:
    """Create the mandates dir on first use, seeded with the example."""
    if not MANDATES_DIR.exists():
        MANDATES_DIR.mkdir(parents=True)
        shutil.copy(EXAMPLE_MANDATE, MANDATES_DIR / "example.yaml")
    return MANDATES_DIR
