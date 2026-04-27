"""Per-test FastAPI client + DB fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    # Import lazily so AHF_DB_URL from session-scoped fixture is honoured.
    from server.db.session import init_db
    from server.main import create_app

    init_db()
    return create_app()


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c
