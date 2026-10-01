"""Where user data lives: ~/.hedge-fund/.

Everything the user owns — mandates, paper funds and their ledgers,
backtest results, API caches, and the .env key file — lives under one home
directory, outside the package. The package directory stays read-only code,
so a pipx install behaves exactly like a checkout.

    mandates/<name>.yaml           templates: the desk, no state
    paper/<name>/                  a deployed fund: fund.yaml, ledger/, broker.json,
                                   control.json, events.jsonl
    research/<fund>-<start>-<end>-<stamp>.json   backtest results, disposable

Textual-free and import-light on purpose: every layer (CLI, TUI, caches)
anchors its paths here, and nothing here may import them back.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

USER_DIR = Path.home() / ".hedge-fund"
MANDATES_DIR = USER_DIR / "mandates"
PAPER_DIR = USER_DIR / "paper"
RESEARCH_DIR = USER_DIR / "research"
CACHE_DIR = USER_DIR / "cache"
ENV_PATH = USER_DIR / ".env"

# The example mandate ships inside the package; it is copied out (never read
# in place) so users edit their copy, not the install.
EXAMPLE_MANDATE = Path(__file__).resolve().parent / "fund" / "example.yaml"


def ensure_mandates_dir() -> Path:
    """Create the mandates dir on first use, seeded with the example."""
    if not MANDATES_DIR.exists():
        MANDATES_DIR.mkdir(parents=True)
        shutil.copy(EXAMPLE_MANDATE, MANDATES_DIR / "example.yaml")
    return MANDATES_DIR


def write_atomic(path: Path, text: str) -> None:
    """Write *text* to *path* via a sibling temp file and rename, so a crash
    mid-write leaves the old file intact rather than a truncated one."""
    path = Path(path)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)
