"""Centralized configuration management using Pydantic Settings."""

from typing import Dict, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DataSourceSettings(BaseSettings):
    """Data source configuration settings.

    Attributes:
        source_weights: Weight for each data source (0-1)
        price_deviation_threshold: Maximum allowed price deviation (0-1)
        volume_deviation_threshold: Maximum allowed volume deviation (0-1)
        request_timeout: Request timeout in seconds
        max_retries: Maximum number of retries for failed requests
    """

    source_weights: Dict[str, float] = Field(
        default={
            'AKShareSource': 1.0,
            'YFinanceSource': 0.8,
            'SinaSource': 0.7,
        },
        description="Weight for each data source"
    )

    price_deviation_threshold: float = Field(
        default=0.02,
        ge=0.0,
        le=1.0,
        description="Maximum allowed price deviation (2%)"
    )

    volume_deviation_threshold: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="Maximum allowed volume deviation (10%)"
    )

    request_timeout: int = Field(
        default=30,
        ge=1,
        description="Request timeout in seconds"
    )

    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum number of retries"
    )

    model_config = SettingsConfigDict(
        env_prefix="DATA_SOURCE_",
        case_sensitive=False
    )

    @field_validator('source_weights')
    @classmethod
    def validate_weights(cls, v: Dict[str, float]) -> Dict[str, float]:
        """Validate that all weights are between 0 and 1."""
        for source, weight in v.items():
            if not 0 < weight <= 1:
                raise ValueError(f"Weight for {source} must be between 0 and 1, got {weight}")
        return v


class CacheSettings(BaseSettings):
    """Cache configuration settings.

    Attributes:
        ttl: Time to live in seconds
        cleanup_interval: Cleanup interval in seconds
        max_size: Maximum number of cache entries
    """

    ttl: int = Field(
        default=300,
        ge=1,
        description="Cache time to live in seconds (5 minutes)"
    )

    cleanup_interval: int = Field(
        default=60,
        ge=1,
        description="Cache cleanup interval in seconds"
    )

    max_size: int = Field(
        default=10000,
        ge=100,
        description="Maximum cache entries"
    )

    model_config = SettingsConfigDict(
        env_prefix="CACHE_",
        case_sensitive=False
    )


class MonitoringSettings(BaseSettings):
    """Monitoring configuration settings.

    Attributes:
        enabled: Whether monitoring is enabled
        metrics_interval: Metrics collection interval in seconds
        health_check_interval: Health check interval in seconds
    """

    enabled: bool = Field(
        default=True,
        description="Enable monitoring"
    )

    metrics_interval: int = Field(
        default=60,
        ge=1,
        description="Metrics collection interval in seconds"
    )

    health_check_interval: int = Field(
        default=300,
        ge=1,
        description="Health check interval in seconds"
    )

    model_config = SettingsConfigDict(
        env_prefix="MONITORING_",
        case_sensitive=False
    )


class Settings(BaseSettings):
    """Global application settings.

    This class combines all configuration sections and can be initialized
    from environment variables or a .env file.

    Attributes:
        data_source: Data source configuration
        cache: Cache configuration
        monitoring: Monitoring configuration
    """

    data_source: DataSourceSettings = Field(
        default_factory=DataSourceSettings,
        description="Data source settings"
    )

    cache: CacheSettings = Field(
        default_factory=CacheSettings,
        description="Cache settings"
    )

    monitoring: MonitoringSettings = Field(
        default_factory=MonitoringSettings,
        description="Monitoring settings"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Global settings instance
settings = Settings()
