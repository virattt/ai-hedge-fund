"""Persist and load universe snapshots (data/universe/YYYY-MM-DD.json)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from integrations.universe.models import UniverseSnapshot

_SNAPSHOT_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")


def snapshot_path(output_dir: str | Path, as_of: str) -> Path:
    return Path(output_dir) / f"{as_of}.json"


def save_universe(snapshot: UniverseSnapshot, output_dir: str | Path) -> Path:
    path = snapshot_path(output_dir, snapshot.as_of)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_universe(path: str | Path) -> UniverseSnapshot:
    raw = Path(path).read_text(encoding="utf-8")
    return UniverseSnapshot(**json.loads(raw))


def load_latest_universe(output_dir: str | Path) -> UniverseSnapshot | None:
    directory = Path(output_dir)
    if not directory.is_dir():
        return None
    candidates = sorted(
        (p for p in directory.iterdir() if _SNAPSHOT_NAME.match(p.name)),
        key=lambda p: p.name,
    )
    if not candidates:
        return None
    return load_universe(candidates[-1])


def resolve_universe_tickers(arg: str, output_dir: str | Path) -> list[str]:
    """Resolve a ``--universe`` CLI value to a ticker list.

    ``latest`` loads the newest snapshot in *output_dir*; anything else is
    treated as a path to a snapshot file.
    """
    if arg.strip().lower() == "latest":
        snapshot = load_latest_universe(output_dir)
        if snapshot is None:
            raise ValueError(
                f"No universe snapshots found in {output_dir}. "
                "Run `alpaca-fund universe build` first."
            )
    else:
        path = Path(arg)
        if not path.is_file():
            raise ValueError(f"Universe snapshot not found: {arg}")
        snapshot = load_universe(path)
    if not snapshot.tickers:
        raise ValueError(f"Universe snapshot {snapshot.as_of} contains no tickers.")
    return list(snapshot.tickers)
