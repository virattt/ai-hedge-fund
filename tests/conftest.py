"""Test fixtures.

Server tests run against an isolated in-memory SQLite to avoid touching the
real ``./data/runs.db``.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True, scope="session")
def _isolated_db() -> Iterator[None]:
    """Force every test to use an in-memory SQLite by default."""
    os.environ.setdefault("AHF_DB_URL", "sqlite:///:memory:")
    os.environ.setdefault("AHF_LOG_LEVEL", "WARNING")
    yield
