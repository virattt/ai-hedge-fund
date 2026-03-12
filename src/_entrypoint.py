from __future__ import annotations

import sys
from pathlib import Path


def ensure_project_root_on_path(current_file: str) -> None:
    """Allow direct `python src/<script>.py` entrypoints to import the `src` package."""
    project_root = Path(current_file).resolve().parents[1]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
