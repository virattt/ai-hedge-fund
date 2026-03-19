"""Integration tests for scraping REST API routes.

Uses FastAPI's TestClient with an in-memory SQLite database injected via
dependency override, following the api_keys route test pattern.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from unittest.mock import MagicMock, patch

from app.backend.database.connection import Base, get_db
from app.backend.database.models import ScrapeResult, ScrapingWebsite
from app.backend.main import app


# ---------------------------------------------------------------------------
# Test database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def test_engine() -> Generator[Engine, None, None]:
    """Create an in-memory SQLite engine for route tests."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_db(test_engine: Engine) -> Generator[Session, None, None]:
    """Yield an isolated database session that rolls back after each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(test_db: Session) -> Generator[TestClient, None, None]:
    """Return a TestClient with the real DB replaced by the in-memory session."""

    def override_get_db() -> Generator[Session, None, None]:
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _create_website_in_db(db: Session, url: str = "https://example.com", name: str = "Example") -> ScrapingWebsite:
    """Insert a website directly into the test DB."""
    website = ScrapingWebsite(url=url, name=name)
    db.add(website)
    db.commit()
    db.refresh(website)
    return website


def _create_result_in_db(db: Session, website_id: int, content: str = "hello", status: str = "success") -> ScrapeResult:
    """Insert a scrape result directly into the test DB."""
    result = ScrapeResult(
        website_id=website_id,
        content=content,
        content_length=len(content.encode()),
        status=status,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


# ---------------------------------------------------------------------------
# 3.1.1 – POST /scraping/websites returns 201
# ---------------------------------------------------------------------------


def test_create_website_endpoint_returns_201(client: TestClient) -> None:
    """POST with a valid payload returns 201 and the created website data."""
    payload = {"url": "https://example.com", "name": "Example Site"}
    response = client.post("/scraping/websites", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["url"] == "https://example.com"
    assert data["name"] == "Example Site"
    assert data["scrape_status"] == "idle"
    assert "id" in data


# ---------------------------------------------------------------------------
# 3.1.2 – SSRF rejection returns 422
# ---------------------------------------------------------------------------


def test_create_website_endpoint_rejects_ssrf(client: TestClient) -> None:
    """POST with a cloud-metadata URL is rejected with 422 (validation error)."""
    payload = {"url": "http://169.254.169.254/latest/", "name": "Metadata"}
    response = client.post("/scraping/websites", json=payload)

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 3.1.3 – GET /scraping/websites returns all websites
# ---------------------------------------------------------------------------


def test_list_websites_endpoint_returns_all(client: TestClient, test_db: Session) -> None:
    """GET /scraping/websites returns all active websites."""
    _create_website_in_db(test_db, url="https://alpha.com", name="Alpha")
    _create_website_in_db(test_db, url="https://beta.com", name="Beta")

    response = client.get("/scraping/websites")

    assert response.status_code == 200
    data = response.json()
    names = [w["name"] for w in data]
    assert "Alpha" in names
    assert "Beta" in names


# ---------------------------------------------------------------------------
# 3.1.4 – GET /scraping/websites/{id} returns 200
# ---------------------------------------------------------------------------


def test_get_website_endpoint_returns_200(client: TestClient, test_db: Session) -> None:
    """GET /scraping/websites/{id} returns the website when it exists."""
    website = _create_website_in_db(test_db, url="https://specific.com", name="Specific")

    response = client.get(f"/scraping/websites/{website.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == website.id
    assert data["url"] == "https://specific.com"
    assert data["name"] == "Specific"


# ---------------------------------------------------------------------------
# 3.1.5 – GET /scraping/websites/{id} returns 404 for missing id
# ---------------------------------------------------------------------------


def test_get_website_endpoint_returns_404_for_missing(client: TestClient) -> None:
    """GET /scraping/websites/9999 returns 404 when website does not exist."""
    response = client.get("/scraping/websites/9999")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 3.1.6 – DELETE /scraping/websites/{id} returns 404 for missing id
# ---------------------------------------------------------------------------


def test_delete_website_endpoint_returns_404_for_missing(client: TestClient) -> None:
    """DELETE with a non-existent ID returns 404."""
    response = client.delete("/scraping/websites/9999")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 3.1.7 – POST /scraping/websites/{id}/scrape returns 202
# ---------------------------------------------------------------------------


def test_trigger_scrape_returns_202(client: TestClient, test_db: Session) -> None:
    """Triggering a scrape on an idle website returns 202 and sets status to in_progress."""
    website = _create_website_in_db(test_db)

    response = client.post(f"/scraping/websites/{website.id}/scrape")

    assert response.status_code == 202
    data = response.json()
    assert data["website_id"] == website.id

    # Verify website status was set to in_progress in the DB
    test_db.refresh(website)
    assert website.scrape_status == "in_progress"


# ---------------------------------------------------------------------------
# 3.1.8 – POST /scraping/websites/{id}/scrape returns 409 if already in_progress
# ---------------------------------------------------------------------------


def test_trigger_scrape_returns_409_if_already_in_progress(client: TestClient, test_db: Session) -> None:
    """Triggering a scrape when already in_progress returns 409 Conflict."""
    website = _create_website_in_db(test_db)
    website.scrape_status = "in_progress"
    test_db.commit()

    response = client.post(f"/scraping/websites/{website.id}/scrape")

    assert response.status_code == 409


# ---------------------------------------------------------------------------
# 3.1.9 – GET /scraping/websites/{id}/results respects limit
# ---------------------------------------------------------------------------


def test_get_results_returns_paginated(client: TestClient, test_db: Session) -> None:
    """GET /scraping/websites/{id}/results with limit returns correct count."""
    website = _create_website_in_db(test_db)
    for i in range(10):
        _create_result_in_db(test_db, website_id=website.id, content=f"content {i}")

    response = client.get(f"/scraping/websites/{website.id}/results?limit=5")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5


# ---------------------------------------------------------------------------
# 3.1.10 – GET /scraping/results/{result_id} returns full content
# ---------------------------------------------------------------------------


def test_get_result_detail_returns_full_content(client: TestClient, test_db: Session) -> None:
    """GET /scraping/results/{id} returns the full content in the response."""
    website = _create_website_in_db(test_db)
    full_content = "This is the full scraped content for the detail endpoint."
    result = _create_result_in_db(test_db, website_id=website.id, content=full_content)

    response = client.get(f"/scraping/results/{result.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["content"] == full_content
    assert data["id"] == result.id
    assert data["website_id"] == website.id


# ---------------------------------------------------------------------------
# 500-error exception handler branch tests
# ---------------------------------------------------------------------------


def test_create_website_returns_500_on_unexpected_exception(client: TestClient) -> None:
    """POST /scraping/websites returns 500 when the repository raises unexpectedly."""
    with patch("app.backend.routes.scraping.ScrapingRepository") as mock_repo_cls:
        mock_repo_cls.return_value.create_website.side_effect = RuntimeError("db exploded")
        response = client.post("/scraping/websites", json={"url": "https://example.com", "name": "Test"})
    assert response.status_code == 500


def test_list_websites_returns_500_on_unexpected_exception(client: TestClient) -> None:
    """GET /scraping/websites returns 500 when the repository raises unexpectedly."""
    with patch("app.backend.routes.scraping.ScrapingRepository") as mock_repo_cls:
        mock_repo_cls.return_value.get_all_websites.side_effect = RuntimeError("db exploded")
        response = client.get("/scraping/websites")
    assert response.status_code == 500


def test_get_website_returns_500_on_unexpected_exception(client: TestClient) -> None:
    """GET /scraping/websites/{id} returns 500 when the repository raises unexpectedly."""
    with patch("app.backend.routes.scraping.ScrapingRepository") as mock_repo_cls:
        mock_repo_cls.return_value.get_website_by_id.side_effect = RuntimeError("db exploded")
        response = client.get("/scraping/websites/1")
    assert response.status_code == 500


def test_update_website_returns_500_on_unexpected_exception(client: TestClient) -> None:
    """PUT /scraping/websites/{id} returns 500 when the repository raises unexpectedly."""
    with patch("app.backend.routes.scraping.ScrapingRepository") as mock_repo_cls:
        mock_repo_cls.return_value.get_website_by_id.side_effect = RuntimeError("db exploded")
        response = client.put("/scraping/websites/1", json={"name": "Updated"})
    assert response.status_code == 500


def test_delete_website_returns_500_on_unexpected_exception(client: TestClient) -> None:
    """DELETE /scraping/websites/{id} returns 500 when the repository raises unexpectedly."""
    with patch("app.backend.routes.scraping.ScrapingRepository") as mock_repo_cls:
        mock_repo_cls.return_value.delete_website.side_effect = RuntimeError("db exploded")
        response = client.delete("/scraping/websites/1")
    assert response.status_code == 500


def test_trigger_scrape_returns_500_on_unexpected_exception(client: TestClient) -> None:
    """POST /scraping/websites/{id}/scrape returns 500 when the repository raises unexpectedly."""
    with patch("app.backend.routes.scraping.ScrapingRepository") as mock_repo_cls:
        mock_repo_cls.return_value.get_website_by_id.side_effect = RuntimeError("db exploded")
        response = client.post("/scraping/websites/1/scrape")
    assert response.status_code == 500


def test_get_website_results_returns_500_on_unexpected_exception(client: TestClient) -> None:
    """GET /scraping/websites/{id}/results returns 500 when repository raises unexpectedly."""
    with patch("app.backend.routes.scraping.ScrapingRepository") as mock_repo_cls:
        mock_repo_cls.return_value.get_website_by_id.side_effect = RuntimeError("db exploded")
        response = client.get("/scraping/websites/1/results")
    assert response.status_code == 500


def test_get_result_detail_returns_500_on_unexpected_exception(client: TestClient) -> None:
    """GET /scraping/results/{id} returns 500 when the repository raises unexpectedly."""
    with patch("app.backend.routes.scraping.ScrapingRepository") as mock_repo_cls:
        mock_repo_cls.return_value.get_result_by_id.side_effect = RuntimeError("db exploded")
        response = client.get("/scraping/results/1")
    assert response.status_code == 500
