"""Configuration validation utilities."""

from typing import List
from .settings import Settings


def validate_settings(settings: Settings) -> List[str]:
    """Validate application settings.

    Args:
        settings: Settings instance to validate

    Returns:
        List of error messages (empty if valid)

    Example:
        >>> from src.config import settings, validate_settings
        >>> errors = validate_settings(settings)
        >>> if errors:
        ...     print("Configuration errors:", errors)
    """
    errors = []

    # Validate data source weights
    for source, weight in settings.data_source.source_weights.items():
        if not 0 < weight <= 1:
            errors.append(f"Invalid weight for {source}: {weight} (must be between 0 and 1)")

    # Validate price deviation threshold
    if not 0 < settings.data_source.price_deviation_threshold < 1:
        errors.append(
            f"Invalid price_deviation_threshold: {settings.data_source.price_deviation_threshold} "
            "(must be between 0 and 1)"
        )

    # Validate volume deviation threshold
    if not 0 < settings.data_source.volume_deviation_threshold < 1:
        errors.append(
            f"Invalid volume_deviation_threshold: {settings.data_source.volume_deviation_threshold} "
            "(must be between 0 and 1)"
        )

    # Validate timeout values
    if settings.data_source.request_timeout <= 0:
        errors.append(
            f"Invalid request_timeout: {settings.data_source.request_timeout} "
            "(must be positive)"
        )

    if settings.data_source.max_retries < 0:
        errors.append(
            f"Invalid max_retries: {settings.data_source.max_retries} "
            "(must be non-negative)"
        )

    # Validate cache settings
    if settings.cache.ttl <= 0:
        errors.append(f"Invalid cache ttl: {settings.cache.ttl} (must be positive)")

    if settings.cache.cleanup_interval <= 0:
        errors.append(
            f"Invalid cache cleanup_interval: {settings.cache.cleanup_interval} "
            "(must be positive)"
        )

    if settings.cache.max_size < 100:
        errors.append(
            f"Invalid cache max_size: {settings.cache.max_size} "
            "(must be at least 100)"
        )

    # Validate monitoring settings
    if settings.monitoring.metrics_interval <= 0:
        errors.append(
            f"Invalid monitoring metrics_interval: {settings.monitoring.metrics_interval} "
            "(must be positive)"
        )

    if settings.monitoring.health_check_interval <= 0:
        errors.append(
            f"Invalid monitoring health_check_interval: {settings.monitoring.health_check_interval} "
            "(must be positive)"
        )

    return errors


def validate_and_raise(settings: Settings) -> None:
    """Validate settings and raise exception if invalid.

    Args:
        settings: Settings instance to validate

    Raises:
        ValueError: If any validation errors are found

    Example:
        >>> from src.config import settings, validate_and_raise
        >>> validate_and_raise(settings)  # Raises if invalid
    """
    errors = validate_settings(settings)
    if errors:
        error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {err}" for err in errors)
        raise ValueError(error_msg)
