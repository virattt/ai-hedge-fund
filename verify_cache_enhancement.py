#!/usr/bin/env python3
"""Verification script for cache enhancement implementation."""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.data.cache import Cache, CacheStats
from src.data.cache_decorators import cached, get_decorator_cache
from src.data.cache_cleaner import CacheCleaner


def verify_imports():
    """Verify all imports work."""
    print("✓ All imports successful")
    return True


def verify_cache_basic():
    """Verify basic cache functionality."""
    cache = Cache(ttl=10)
    test_data = [{"time": "2024-01-01", "price": 100.0}]

    # Test set/get
    cache.set_prices("TEST", test_data)
    result = cache.get_prices("TEST")

    assert result is not None
    assert len(result) == 1
    assert result[0]["price"] == 100.0

    print("✓ Basic cache operations work")
    return True


def verify_ttl():
    """Verify TTL functionality."""
    cache = Cache(ttl=1)
    test_data = [{"time": "2024-01-01", "price": 100.0}]

    cache.set_prices("TEST", test_data)
    time.sleep(1.1)
    result = cache.get_prices("TEST")

    assert result is None, "Cache should have expired"

    print("✓ TTL expiration works")
    return True


def verify_statistics():
    """Verify statistics tracking."""
    cache = Cache(ttl=10)
    test_data = [{"time": "2024-01-01", "price": 100.0}]

    cache.set_prices("TEST", test_data)
    cache.get_prices("TEST")  # Hit
    cache.get_prices("MISS")  # Miss

    stats = cache.get_stats()

    assert stats['hits'] == 1
    assert stats['misses'] == 1
    assert stats['total'] == 2
    assert "50.00%" in stats['hit_rate']

    print("✓ Statistics tracking works")
    return True


def verify_cleanup():
    """Verify manual cleanup."""
    cache = Cache(ttl=1)

    for i in range(5):
        cache.set_prices(f"TEST{i}", [{"time": "2024-01-01", "price": 100.0}])

    time.sleep(1.1)
    removed = cache.cleanup_expired()

    assert removed == 5, f"Expected 5 removed, got {removed}"

    print("✓ Manual cleanup works")
    return True


def verify_decorator():
    """Verify cache decorator."""
    call_count = [0]

    @cached(ttl=10)
    def test_func(x):
        call_count[0] += 1
        return x * 2

    # Clear decorator cache first
    get_decorator_cache().clear()

    result1 = test_func(5)
    result2 = test_func(5)

    assert result1 == 10
    assert result2 == 10
    assert call_count[0] == 1, f"Expected 1 call, got {call_count[0]}"

    print("✓ Cache decorator works")
    return True


def verify_cleaner():
    """Verify automatic cleaner."""
    cache = Cache(ttl=1)
    test_data = [{"time": "2024-01-01", "price": 100.0}]

    cache.set_prices("TEST", test_data)

    cleaner = CacheCleaner(cache, interval=1)
    cleaner.start()

    assert cleaner.is_running()

    time.sleep(2.5)  # Wait for expiration and cleanup

    cleaner.stop()

    assert not cleaner.is_running()
    assert len(cache._prices_cache) == 0

    print("✓ Automatic cleaner works")
    return True


def verify_thread_safety():
    """Verify thread safety."""
    import threading

    cache = Cache(ttl=10)
    test_data = [{"time": "2024-01-01", "price": 100.0}]
    errors = []

    def worker():
        try:
            for i in range(10):
                cache.set_prices(f"TEST{i}", test_data)
                cache.get_prices(f"TEST{i}")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(5)]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    assert len(errors) == 0, f"Thread safety errors: {errors}"

    print("✓ Thread safety verified")
    return True


def verify_all_data_types():
    """Verify all cache data types."""
    cache = Cache(ttl=10)

    # Test all data types
    cache.set_prices("TEST", [{"time": "2024-01-01", "price": 100.0}])
    cache.set_financial_metrics("TEST", [{"report_period": "2024-Q1", "revenue": 1000}])
    cache.set_line_items("TEST", [{"report_period": "2024-Q1", "item": "revenue"}])
    cache.set_insider_trades("TEST", [{"filing_date": "2024-01-01", "shares": 100}])
    cache.set_company_news("TEST", [{"date": "2024-01-01", "title": "News"}])

    assert cache.get_prices("TEST") is not None
    assert cache.get_financial_metrics("TEST") is not None
    assert cache.get_line_items("TEST") is not None
    assert cache.get_insider_trades("TEST") is not None
    assert cache.get_company_news("TEST") is not None

    print("✓ All data types work")
    return True


def main():
    """Run all verifications."""
    print("\n" + "=" * 60)
    print("Cache Enhancement Verification")
    print("=" * 60 + "\n")

    verifications = [
        ("Imports", verify_imports),
        ("Basic Cache", verify_cache_basic),
        ("TTL Expiration", verify_ttl),
        ("Statistics", verify_statistics),
        ("Manual Cleanup", verify_cleanup),
        ("Decorator", verify_decorator),
        ("Auto Cleaner", verify_cleaner),
        ("Thread Safety", verify_thread_safety),
        ("All Data Types", verify_all_data_types),
    ]

    passed = 0
    failed = 0

    for name, verify_func in verifications:
        try:
            verify_func()
            passed += 1
        except Exception as e:
            print(f"✗ {name} failed: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")

    if failed > 0:
        sys.exit(1)
    else:
        print("✅ All verifications passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
