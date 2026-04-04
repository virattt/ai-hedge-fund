"""Tests for LRU+TTL cache helpers in insider_service.py."""
import time
from unittest.mock import MagicMock, patch


class TestCacheGetPut:
    """_cache_get/_cache_put implement LRU eviction and TTL expiration."""

    def setup_method(self) -> None:
        from app.backend.services.insider_service import _insider_cache
        _insider_cache.clear()

    def test_cache_miss_returns_none(self) -> None:
        from app.backend.services.insider_service import _cache_get

        result = _cache_get("summary:AAPL:4")
        assert result is None

    def test_cache_hit_returns_stored_value(self) -> None:
        from app.backend.services.insider_service import _cache_get, _cache_put

        fake_response = MagicMock()
        _cache_put("summary:AAPL:4", fake_response)
        result = _cache_get("summary:AAPL:4")
        assert result is fake_response

    def test_expired_entry_returns_none(self) -> None:
        from app.backend.services import insider_service
        from app.backend.services.insider_service import _cache_get, _cache_put

        fake_response = MagicMock()
        with patch.object(insider_service, "_CACHE_TTL_SECONDS", 0):
            _cache_put("summary:TSLA:4", fake_response)
            time.sleep(0.01)
            result = _cache_get("summary:TSLA:4")
        assert result is None

    def test_expired_entry_is_evicted_from_cache(self) -> None:
        from app.backend.services import insider_service
        from app.backend.services.insider_service import _cache_get, _cache_put, _insider_cache

        fake_response = MagicMock()
        with patch.object(insider_service, "_CACHE_TTL_SECONDS", 0):
            _cache_put("summary:TSLA:4", fake_response)
            time.sleep(0.01)
            _cache_get("summary:TSLA:4")
        assert "summary:TSLA:4" not in _insider_cache

    def test_lru_eviction_removes_oldest_entry(self) -> None:
        from app.backend.services import insider_service
        from app.backend.services.insider_service import _cache_put, _insider_cache

        with patch.object(insider_service, "_CACHE_MAX_SIZE", 3):
            _cache_put("key:1", MagicMock())
            _cache_put("key:2", MagicMock())
            _cache_put("key:3", MagicMock())
            _cache_put("key:4", MagicMock())  # Evicts key:1
        assert "key:1" not in _insider_cache
        assert "key:4" in _insider_cache
