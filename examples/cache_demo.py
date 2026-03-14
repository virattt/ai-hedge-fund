#!/usr/bin/env python3
"""Demonstration of enhanced cache features."""

import time
import logging
from src.data.cache import Cache
from src.data.cache_decorators import cached
from src.data.cache_cleaner import CacheCleaner

# Setup logging to see cache activity
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def demo_basic_cache():
    """Demo basic cache with TTL."""
    print("\n" + "=" * 60)
    print("DEMO 1: Basic Cache with TTL")
    print("=" * 60)

    # Create cache with 3-second TTL for demo
    cache = Cache(ttl=3)

    # Store some data
    test_data = [{"time": "2024-01-01", "price": 100.0}]
    cache.set_prices("AAPL", test_data)
    print("✓ Stored AAPL price data")

    # First retrieval - should hit
    result = cache.get_prices("AAPL")
    print(f"✓ Retrieved data: {result}")

    # Check stats
    stats = cache.get_stats()
    print(f"✓ Cache stats: Hits={stats['hits']}, Misses={stats['misses']}, Hit Rate={stats['hit_rate']}")

    # Wait for expiration
    print("\nWaiting 3.5 seconds for cache to expire...")
    time.sleep(3.5)

    # Try to retrieve again - should miss
    result = cache.get_prices("AAPL")
    print(f"✗ Retrieved data after expiration: {result}")

    stats = cache.get_stats()
    print(f"✓ Updated stats: Hits={stats['hits']}, Misses={stats['misses']}, Hit Rate={stats['hit_rate']}")


def demo_decorator():
    """Demo cache decorator."""
    print("\n" + "=" * 60)
    print("DEMO 2: Cache Decorator")
    print("=" * 60)

    call_count = [0]

    @cached(ttl=5, key_prefix="demo:")
    def expensive_calculation(x: int) -> int:
        """Simulate expensive calculation."""
        call_count[0] += 1
        logger.info(f"Performing expensive calculation for {x}")
        time.sleep(0.5)  # Simulate work
        return x * x

    # First call - cache miss
    print(f"✓ First call: expensive_calculation(5) = {expensive_calculation(5)}")
    print(f"  Function called {call_count[0]} time(s)")

    # Second call - cache hit
    print(f"✓ Second call: expensive_calculation(5) = {expensive_calculation(5)}")
    print(f"  Function called {call_count[0]} time(s) (cached!)")

    # Different argument - cache miss
    print(f"✓ Third call: expensive_calculation(10) = {expensive_calculation(10)}")
    print(f"  Function called {call_count[0]} time(s)")


def demo_cleanup():
    """Demo automatic cache cleanup."""
    print("\n" + "=" * 60)
    print("DEMO 3: Automatic Cache Cleanup")
    print("=" * 60)

    # Create cache with 2-second TTL
    cache = Cache(ttl=2)

    # Add multiple entries
    for i, ticker in enumerate(["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA"]):
        cache.set_prices(ticker, [{"time": "2024-01-01", "price": 100.0 + i}])

    stats = cache.get_stats()
    print(f"✓ Added 5 entries, cache size: {stats['prices_size']}")

    # Start cleaner with 1-second interval
    print("✓ Starting cache cleaner (1-second interval)...")
    cleaner = CacheCleaner(cache, interval=1)
    cleaner.start()

    # Wait for entries to expire and cleanup to run
    print("  Waiting 3 seconds for expiration and cleanup...")
    time.sleep(3.5)

    stats = cache.get_stats()
    print(f"✓ After cleanup, cache size: {stats['prices_size']}")

    cleaner.stop()
    print("✓ Cleaner stopped")


def demo_statistics():
    """Demo cache statistics tracking."""
    print("\n" + "=" * 60)
    print("DEMO 4: Cache Statistics")
    print("=" * 60)

    cache = Cache(ttl=10)
    test_data = [{"time": "2024-01-01", "price": 100.0}]

    # Perform various operations
    cache.set_prices("AAPL", test_data)
    cache.get_prices("AAPL")  # Hit
    cache.get_prices("AAPL")  # Hit
    cache.get_prices("GOOGL")  # Miss
    cache.get_prices("MSFT")  # Miss

    # Get detailed stats
    stats = cache.get_stats()
    print(f"✓ Cache Statistics:")
    print(f"  - Total operations: {stats['total']}")
    print(f"  - Hits: {stats['hits']}")
    print(f"  - Misses: {stats['misses']}")
    print(f"  - Hit rate: {stats['hit_rate']}")
    print(f"  - Cache size: {stats['prices_size']} entries")
    print(f"  - TTL: {stats['ttl']} seconds")


def demo_concurrent_access():
    """Demo thread-safe concurrent access."""
    print("\n" + "=" * 60)
    print("DEMO 5: Thread-Safe Concurrent Access")
    print("=" * 60)

    import threading

    cache = Cache(ttl=10)
    errors = []

    def writer():
        try:
            for i in range(10):
                cache.set_prices(f"TICKER{i}", [{"time": "2024-01-01", "price": 100.0}])
        except Exception as e:
            errors.append(e)

    def reader():
        try:
            for i in range(10):
                cache.get_prices(f"TICKER{i}")
        except Exception as e:
            errors.append(e)

    # Start multiple threads
    threads = []
    for _ in range(3):
        threads.append(threading.Thread(target=writer))
        threads.append(threading.Thread(target=reader))

    print("✓ Starting 6 concurrent threads...")
    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    if errors:
        print(f"✗ Errors occurred: {errors}")
    else:
        print("✓ All concurrent operations completed successfully")

    stats = cache.get_stats()
    print(f"✓ Final cache state: {stats['prices_size']} entries, {stats['total']} operations")


def main():
    """Run all demos."""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "Enhanced Cache System Demo" + " " * 22 + "║")
    print("╚" + "═" * 58 + "╝")

    try:
        demo_basic_cache()
        demo_decorator()
        demo_cleanup()
        demo_statistics()
        demo_concurrent_access()

        print("\n" + "=" * 60)
        print("All demos completed successfully!")
        print("=" * 60 + "\n")

    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)


if __name__ == "__main__":
    main()
