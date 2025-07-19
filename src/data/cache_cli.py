"""Cache management CLI utilities."""

import argparse
import json
import sys
from typing import Dict, Any

from src.data.cache_factory import get_cache, CacheFactory
from src.data.cache_monitor import get_cache_monitor
from src.data.cache_validator import CacheValidator


def show_cache_stats():
    """Display cache statistics."""
    try:
        monitor = get_cache_monitor()
        stats = monitor.get_stats()

        print("=== Cache Statistics ===")
        print(f"Cache hits: {stats.get('hits', 0)}")
        print(f"Cache misses: {stats.get('misses', 0)}")
        print(f"Hit rate: {stats.get('hit_rate', 0):.2f}%")
        print(f"Last cleanup: {stats.get('last_cleanup', 'Never')}")

        # Show table-specific stats
        table_stats = {k: v for k, v in stats.items()
                      if k in ['prices', 'financial_metrics', 'line_items',
                              'insider_trades', 'company_news', 'line_item_search']}

        if table_stats:
            print("\n=== Cache Entries by Type ===")
            for table, count in table_stats.items():
                print(f"{table}: {count} entries")

        total_entries = sum(table_stats.values())
        print(f"\nTotal entries: {total_entries}")

    except Exception as e:
        print(f"Error getting cache stats: {e}")
        return 1

    return 0


def check_cache_health():
    """Check and display cache health."""
    try:
        monitor = get_cache_monitor()
        health = monitor.check_cache_health()

        print("=== Cache Health Check ===")
        print(f"Status: {health['status'].upper()}")

        if health.get('issues'):
            print("\nIssues found:")
            for issue in health['issues']:
                print(f"  - {issue}")

        if health.get('recommendations'):
            print("\nRecommendations:")
            for rec in health['recommendations']:
                print(f"  - {rec}")

        if health['status'] == 'healthy':
            print("✓ Cache is healthy")
        else:
            print("⚠ Cache has issues that need attention")

    except Exception as e:
        print(f"Error checking cache health: {e}")
        return 1

    return 0


def cleanup_cache():
    """Clean up expired cache entries."""
    try:
        cache = get_cache()
        monitor = get_cache_monitor()

        print("Starting cache cleanup...")

        # Get stats before cleanup
        if hasattr(cache, 'get_cache_stats'):
            before_stats = cache.get_cache_stats()
            before_total = sum(before_stats.values())
            print(f"Entries before cleanup: {before_total}")

        # Run cleanup
        monitor.cleanup_if_needed(force=True)

        # Get stats after cleanup
        if hasattr(cache, 'get_cache_stats'):
            after_stats = cache.get_cache_stats()
            after_total = sum(after_stats.values())
            removed = before_total - after_total
            print(f"Entries after cleanup: {after_total}")
            print(f"Removed {removed} expired entries")

        print("✓ Cache cleanup completed")

    except Exception as e:
        print(f"Error during cache cleanup: {e}")
        return 1

    return 0


def clear_cache():
    """Clear all cache entries."""
    try:
        cache = get_cache()

        if not hasattr(cache, 'clear_cache'):
            print("Cache clearing not supported for this cache type")
            return 1

        # Get confirmation
        response = input("Are you sure you want to clear ALL cache entries? (yes/no): ")
        if response.lower() != 'yes':
            print("Cache clear cancelled")
            return 0

        print("Clearing cache...")
        cache.clear_cache()
        print("✓ Cache cleared successfully")

    except Exception as e:
        print(f"Error clearing cache: {e}")
        return 1

    return 0


def validate_cache():
    """Validate cache integrity."""
    try:
        validator = CacheValidator()

        print("Running cache validation...")
        result = validator.check_cache_consistency()

        print(f"Validation status: {result['status'].upper()}")

        if result.get('issues'):
            print("\nIssues found:")
            for issue in result['issues']:
                print(f"  - {issue}")
        else:
            print("✓ No issues found")

        print(f"Validation completed at: {result['timestamp']}")

    except Exception as e:
        print(f"Error during cache validation: {e}")
        return 1

    return 0


def repair_cache():
    """Repair cache issues."""
    try:
        validator = CacheValidator()

        print("Starting cache repair...")
        result = validator.repair_cache()

        if result.get('repaired'):
            print("Repair actions taken:")
            for action in result['repaired']:
                print(f"  ✓ {action}")

        if result.get('errors'):
            print("Repair errors:")
            for error in result['errors']:
                print(f"  ✗ {error}")

        if not result.get('errors'):
            print("✓ Cache repair completed successfully")
        else:
            print("⚠ Cache repair completed with errors")

    except Exception as e:
        print(f"Error during cache repair: {e}")
        return 1

    return 0


def reset_cache_instance():
    """Reset the cache singleton instance."""
    try:
        print("Resetting cache instance...")
        CacheFactory.reset_instance()
        print("✓ Cache instance reset")

    except Exception as e:
        print(f"Error resetting cache instance: {e}")
        return 1

    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Cache management utilities")
    parser.add_argument('command', choices=[
        'stats', 'health', 'cleanup', 'clear', 'validate', 'repair', 'reset'
    ], help='Command to execute')

    args = parser.parse_args()

    commands = {
        'stats': show_cache_stats,
        'health': check_cache_health,
        'cleanup': cleanup_cache,
        'clear': clear_cache,
        'validate': validate_cache,
        'repair': repair_cache,
        'reset': reset_cache_instance
    }

    try:
        return commands[args.command]()
    except KeyError:
        print(f"Unknown command: {args.command}")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
