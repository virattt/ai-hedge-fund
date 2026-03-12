from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "_entrypoint.py"

spec = importlib.util.spec_from_file_location("_entrypoint", MODULE_PATH)
entrypoint = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(entrypoint)


def test_ensure_project_root_on_path_inserts_repo_root(monkeypatch):
    script_path = PROJECT_ROOT / "src" / "main.py"
    monkeypatch.setattr(sys, "path", ["/tmp/fake-site-packages", str(script_path.parent)])

    entrypoint.ensure_project_root_on_path(str(script_path))

    assert sys.path[0] == str(PROJECT_ROOT)
    assert str(script_path.parent) in sys.path


def test_ensure_project_root_on_path_is_idempotent(monkeypatch):
    script_path = PROJECT_ROOT / "src" / "backtester.py"
    monkeypatch.setattr(sys, "path", [str(PROJECT_ROOT), str(script_path.parent)])

    entrypoint.ensure_project_root_on_path(str(script_path))

    assert sys.path.count(str(PROJECT_ROOT)) == 1
