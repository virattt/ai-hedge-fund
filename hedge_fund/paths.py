"""Where user data lives: ~/.hedge-fund/.

Everything the user owns — mandates, run/backtest receipts, API caches, and
the .env key file — lives under one home directory, outside the package. The
package directory stays read-only code, so a pipx install behaves exactly
like a checkout.

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

# The example mandate ships inside the package; it is copied out (never read
# in place) so users edit their copy, not the install.
EXAMPLE_MANDATE = Path(__file__).resolve().parent / "fund" / "example.yaml"


def ensure_mandates_dir() -> Path:
    """Create the mandates dir on first use, seeded with the example."""
    if MANDATES_DIR.exists() and not MANDATES_DIR.is_dir():
        raise NotADirectoryError(
            f"Mandates path exists and is not a directory: {MANDATES_DIR}"
        )
    MANDATES_DIR.mkdir(parents=True, exist_ok=True)
    example_copy = MANDATES_DIR / "example.yaml"
    if not example_copy.exists():
        shutil.copy(EXAMPLE_MANDATE, example_copy)
    return MANDATES_DIR
