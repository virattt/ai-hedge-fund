"""Cache validation and integrity utilities."""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

from src.data.cache_factory import get_cache

logger = logging.getLogger(__name__)


class CacheValidator:
    """Validate cache data integrity and consistency."""

    def __init__(self):
        self.cache = get_cache()

    def validate_data_integrity(self, table_name: str, cache_key: str, data: List[Dict[str, Any]]) -> bool:
        """Validate that cache data has proper structure and required fields."""
        if not data:
            return True

        required_fields = {
            "prices": ["time", "open", "close", "high", "low", "volume"],
            "financial_metrics": ["ticker", "report_period", "period"],
            "line_items": ["ticker", "report_period", "period"],
            "insider_trades": ["ticker", "filing_date"],
            "company_news": ["date"],
            "line_item_search": ["ticker"]
        }

        fields = required_fields.get(table_name, [])
        if not fields:
            return True

        try:
            for item in data:
                if not isinstance(item, dict):
                    logger.warning(f"Invalid data type in {table_name}:{cache_key}")
                    return False

                for field in fields:
                    if field not in item:
                        logger.warning(f"Missing required field '{field}' in {table_name}:{cache_key}")
                        return False

            return True
        except Exception as e:
            logger.error(f"Error validating data integrity for {table_name}:{cache_key}: {e}")
            return False

    def validate_json_serializable(self, data: Any) -> bool:
        """Validate that data can be JSON serialized."""
        try:
            json.dumps(data)
            return True
        except (TypeError, ValueError) as e:
            logger.warning(f"Data not JSON serializable: {e}")
            return False

    def check_cache_consistency(self) -> Dict[str, Any]:
        """Check cache consistency and report issues."""
        issues = []

        # Check if cache instance is available
        if not self.cache:
            issues.append("Cache instance not available")
            return {"status": "error", "issues": issues}

        # Check cache stats (if available)
        if hasattr(self.cache, 'get_cache_stats'):
            try:
                stats = self.cache.get_cache_stats()
                logger.info(f"Cache stats: {stats}")
            except Exception as e:
                issues.append(f"Error getting cache stats: {e}")

        # Run cleanup to remove any corrupted entries
        if hasattr(self.cache, 'cleanup_expired'):
            try:
                self.cache.cleanup_expired()
            except Exception as e:
                issues.append(f"Error during cache cleanup: {e}")

        status = "healthy" if not issues else "warning"
        return {
            "status": status,
            "issues": issues,
            "timestamp": datetime.now().isoformat()
        }

    def repair_cache(self) -> Dict[str, Any]:
        """Attempt to repair cache issues."""
        logger.info("Starting cache repair...")
        repaired = []
        errors = []

        try:
            # Clear any corrupted entries by running cleanup
            if hasattr(self.cache, 'cleanup_expired'):
                self.cache.cleanup_expired()
                repaired.append("Ran cache cleanup")

            # Reset cache instance if needed
            if hasattr(self.cache, 'clear_cache'):
                # Only clear if there are serious issues
                consistency_check = self.check_cache_consistency()
                if consistency_check["status"] == "error":
                    logger.warning("Clearing cache due to errors")
                    self.cache.clear_cache()
                    repaired.append("Cleared corrupted cache")

        except Exception as e:
            errors.append(f"Error during cache repair: {e}")

        return {
            "repaired": repaired,
            "errors": errors,
            "timestamp": datetime.now().isoformat()
        }


def validate_cache_entry(table_name: str, cache_key: str, data: List[Dict[str, Any]]) -> bool:
    """Validate a single cache entry."""
    validator = CacheValidator()
    return (validator.validate_data_integrity(table_name, cache_key, data) and
            validator.validate_json_serializable(data))
