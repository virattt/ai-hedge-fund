"""Persistent user-level settings for the Strategist dashboard.

Lives at ``~/.strategist/settings.json`` (overridable via ``STRATEGIST_DATA_DIR``
env var). One JSON file, no DB, so you can ``git init`` the directory if
you want versioned history of your settings.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


DATA_DIR = Path(os.environ.get("STRATEGIST_DATA_DIR", str(Path.home() / ".strategist")))
SETTINGS_FILE = DATA_DIR / "settings.json"


@dataclass
class Settings:
    # Save behaviour
    auto_save_enabled: bool = False
    auto_save_default_tag: str = "auto"

    # Auto-run the AI investor council on every ticker view (off by default —
    # adds 30-60s per ticker but produces the fullest possible report).
    auto_run_council: bool = False

    # Tagging defaults
    available_tags: list[str] = field(
        default_factory=lambda: ["research", "watchlist", "decision", "position-entered", "auto"]
    )

    # Data source preference (in priority order). The first one whose env var
    # is set will be tried first; others are fallbacks.
    data_source_priority: list[str] = field(
        default_factory=lambda: ["financial_datasets", "fmp", "yfinance"]
    )

    # Default analyst panel for deep analysis. Empty list = all.
    default_analysts: list[str] = field(default_factory=list)


def load_settings() -> Settings:
    if not SETTINGS_FILE.exists():
        return Settings()
    try:
        raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        # Only carry forward fields the current Settings dataclass knows about
        valid = {k: v for k, v in raw.items() if k in Settings.__dataclass_fields__}
        return Settings(**valid)
    except Exception:
        return Settings()


def save_settings(s: Settings) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(asdict(s), indent=2), encoding="utf-8")


def detected_data_sources() -> dict[str, bool]:
    """Which data sources have credentials available right now."""
    return {
        "yfinance": True,
        "financial_datasets": bool(os.environ.get("FINANCIAL_DATASETS_API_KEY")),
        "fmp": bool(
            os.environ.get("FMP_API_KEY") or os.environ.get("FINANCIAL_MODELING_PREP_API_KEY")
        ),
        "polygon": bool(os.environ.get("POLYGON_API_KEY")),
    }
