"""Tests for settings module."""

import pytest
from src.config.settings import (
    Settings,
    DataSourceSettings,
    CacheSettings,
    MonitoringSettings,
)


class TestDataSourceSettings:
    """Tests for DataSourceSettings."""

    def test_default_values(self):
        """Test default configuration values."""
        settings = DataSourceSettings()

        assert settings.price_deviation_threshold == 0.02
        assert settings.volume_deviation_threshold == 0.10
        assert settings.request_timeout == 30
        assert settings.max_retries == 3
        assert 'AKShareSource' in settings.source_weights
        assert settings.source_weights['AKShareSource'] == 1.0

    def test_custom_values(self):
        """Test custom configuration values."""
        settings = DataSourceSettings(
            price_deviation_threshold=0.05,
            volume_deviation_threshold=0.20,
            request_timeout=60,
            max_retries=5,
        )

        assert settings.price_deviation_threshold == 0.05
        assert settings.volume_deviation_threshold == 0.20
        assert settings.request_timeout == 60
        assert settings.max_retries == 5

    def test_invalid_weight_validation(self):
        """Test validation of source weights."""
        with pytest.raises(ValueError, match="must be between 0 and 1"):
            DataSourceSettings(
                source_weights={'InvalidSource': 2.0}
            )

    def test_zero_weight_validation(self):
        """Test validation rejects zero weight."""
        with pytest.raises(ValueError, match="must be between 0 and 1"):
            DataSourceSettings(
                source_weights={'InvalidSource': 0.0}
            )

    def test_valid_weights(self):
        """Test valid weight configurations."""
        settings = DataSourceSettings(
            source_weights={
                'Source1': 1.0,
                'Source2': 0.5,
                'Source3': 0.1,
            }
        )
        assert len(settings.source_weights) == 3
        assert settings.source_weights['Source2'] == 0.5


class TestCacheSettings:
    """Tests for CacheSettings."""

    def test_default_values(self):
        """Test default cache configuration."""
        settings = CacheSettings()

        assert settings.ttl == 300
        assert settings.cleanup_interval == 60
        assert settings.max_size == 10000

    def test_custom_values(self):
        """Test custom cache configuration."""
        settings = CacheSettings(
            ttl=600,
            cleanup_interval=120,
            max_size=5000,
        )

        assert settings.ttl == 600
        assert settings.cleanup_interval == 120
        assert settings.max_size == 5000


class TestMonitoringSettings:
    """Tests for MonitoringSettings."""

    def test_default_values(self):
        """Test default monitoring configuration."""
        settings = MonitoringSettings()

        assert settings.enabled is True
        assert settings.metrics_interval == 60
        assert settings.health_check_interval == 300

    def test_custom_values(self):
        """Test custom monitoring configuration."""
        settings = MonitoringSettings(
            enabled=False,
            metrics_interval=30,
            health_check_interval=600,
        )

        assert settings.enabled is False
        assert settings.metrics_interval == 30
        assert settings.health_check_interval == 600


class TestSettings:
    """Tests for global Settings."""

    def test_default_configuration(self):
        """Test default global configuration."""
        settings = Settings()

        assert isinstance(settings.data_source, DataSourceSettings)
        assert isinstance(settings.cache, CacheSettings)
        assert isinstance(settings.monitoring, MonitoringSettings)

    def test_nested_access(self):
        """Test accessing nested configuration values."""
        settings = Settings()

        assert settings.data_source.request_timeout == 30
        assert settings.cache.ttl == 300
        assert settings.monitoring.enabled is True

    def test_custom_nested_configuration(self):
        """Test custom nested configuration."""
        settings = Settings(
            data_source=DataSourceSettings(request_timeout=60),
            cache=CacheSettings(ttl=600),
            monitoring=MonitoringSettings(enabled=False),
        )

        assert settings.data_source.request_timeout == 60
        assert settings.cache.ttl == 600
        assert settings.monitoring.enabled is False


class TestEnvironmentVariables:
    """Tests for environment variable loading."""

    def test_data_source_env_prefix(self, monkeypatch):
        """Test loading data source settings from environment."""
        monkeypatch.setenv('DATA_SOURCE_REQUEST_TIMEOUT', '120')
        monkeypatch.setenv('DATA_SOURCE_MAX_RETRIES', '5')

        settings = DataSourceSettings()

        assert settings.request_timeout == 120
        assert settings.max_retries == 5

    def test_cache_env_prefix(self, monkeypatch):
        """Test loading cache settings from environment."""
        monkeypatch.setenv('CACHE_TTL', '600')
        monkeypatch.setenv('CACHE_MAX_SIZE', '20000')

        settings = CacheSettings()

        assert settings.ttl == 600
        assert settings.max_size == 20000

    def test_monitoring_env_prefix(self, monkeypatch):
        """Test loading monitoring settings from environment."""
        monkeypatch.setenv('MONITORING_ENABLED', 'false')
        monkeypatch.setenv('MONITORING_METRICS_INTERVAL', '120')

        settings = MonitoringSettings()

        assert settings.enabled is False
        assert settings.metrics_interval == 120
