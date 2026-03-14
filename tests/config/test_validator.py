"""Tests for configuration validator."""

import pytest
from src.config.settings import Settings, DataSourceSettings, CacheSettings, MonitoringSettings
from src.config.validator import validate_settings, validate_and_raise


class TestValidateSettings:
    """Tests for validate_settings function."""

    def test_valid_configuration(self):
        """Test that valid configuration passes validation."""
        settings = Settings()
        errors = validate_settings(settings)
        assert len(errors) == 0

    def test_invalid_weight(self):
        """Test detection of invalid source weights."""
        # Pydantic will catch this during initialization
        # Test that our validator works by manually setting invalid values
        settings = Settings()
        # Bypass Pydantic by directly modifying the dict
        settings.data_source.source_weights['InvalidSource'] = 1.5
        errors = validate_settings(settings)
        # Our validator should catch this
        assert len(errors) > 0
        assert any('InvalidSource' in err for err in errors)

    def test_invalid_deviation_thresholds(self):
        """Test detection of invalid deviation thresholds."""
        # These should be caught by Pydantic's Field validators
        # Test with values that bypass Pydantic
        settings = Settings()
        # Manually set invalid values to test validator
        settings.data_source.price_deviation_threshold = 1.5
        errors = validate_settings(settings)
        assert len(errors) > 0
        assert any('price_deviation_threshold' in err for err in errors)

    def test_invalid_timeout(self):
        """Test detection of invalid timeout values."""
        settings = Settings()
        settings.data_source.request_timeout = -1
        errors = validate_settings(settings)
        assert len(errors) > 0
        assert any('request_timeout' in err for err in errors)

    def test_invalid_max_retries(self):
        """Test detection of invalid max_retries."""
        settings = Settings()
        settings.data_source.max_retries = -5
        errors = validate_settings(settings)
        assert len(errors) > 0
        assert any('max_retries' in err for err in errors)

    def test_invalid_cache_ttl(self):
        """Test detection of invalid cache TTL."""
        settings = Settings()
        settings.cache.ttl = -100
        errors = validate_settings(settings)
        assert len(errors) > 0
        assert any('ttl' in err for err in errors)

    def test_invalid_cache_max_size(self):
        """Test detection of invalid cache max_size."""
        settings = Settings()
        settings.cache.max_size = 50  # Less than minimum of 100
        errors = validate_settings(settings)
        assert len(errors) > 0
        assert any('max_size' in err for err in errors)

    def test_invalid_monitoring_intervals(self):
        """Test detection of invalid monitoring intervals."""
        settings = Settings()
        settings.monitoring.metrics_interval = -10
        errors = validate_settings(settings)
        assert len(errors) > 0
        assert any('metrics_interval' in err for err in errors)

    def test_multiple_errors(self):
        """Test that multiple errors are detected."""
        settings = Settings()
        settings.data_source.request_timeout = -1
        settings.cache.ttl = -100
        settings.monitoring.metrics_interval = -10

        errors = validate_settings(settings)
        assert len(errors) >= 3


class TestValidateAndRaise:
    """Tests for validate_and_raise function."""

    def test_valid_configuration_no_exception(self):
        """Test that valid configuration doesn't raise exception."""
        settings = Settings()
        # Should not raise
        validate_and_raise(settings)

    def test_invalid_configuration_raises(self):
        """Test that invalid configuration raises ValueError."""
        settings = Settings()
        settings.data_source.request_timeout = -1

        with pytest.raises(ValueError, match="Configuration validation failed"):
            validate_and_raise(settings)

    def test_error_message_format(self):
        """Test that error message contains details."""
        settings = Settings()
        settings.data_source.request_timeout = -1
        settings.cache.ttl = -100

        with pytest.raises(ValueError) as exc_info:
            validate_and_raise(settings)

        error_message = str(exc_info.value)
        assert 'request_timeout' in error_message
        assert 'ttl' in error_message


class TestValidationEdgeCases:
    """Tests for edge cases in validation."""

    def test_zero_timeout(self):
        """Test that zero timeout is invalid."""
        settings = Settings()
        settings.data_source.request_timeout = 0
        errors = validate_settings(settings)
        assert len(errors) > 0

    def test_minimum_valid_values(self):
        """Test minimum valid values."""
        settings = Settings(
            data_source=DataSourceSettings(
                price_deviation_threshold=0.01,
                volume_deviation_threshold=0.01,
                request_timeout=1,
                max_retries=0,
            ),
            cache=CacheSettings(
                ttl=1,
                cleanup_interval=1,
                max_size=100,
            ),
            monitoring=MonitoringSettings(
                metrics_interval=1,
                health_check_interval=1,
            )
        )
        errors = validate_settings(settings)
        assert len(errors) == 0

    def test_maximum_valid_values(self):
        """Test maximum valid values."""
        settings = Settings(
            data_source=DataSourceSettings(
                price_deviation_threshold=0.99,
                volume_deviation_threshold=0.99,
                request_timeout=3600,
                max_retries=100,
            ),
            cache=CacheSettings(
                ttl=86400,
                cleanup_interval=3600,
                max_size=1000000,
            ),
            monitoring=MonitoringSettings(
                metrics_interval=3600,
                health_check_interval=86400,
            )
        )
        errors = validate_settings(settings)
        assert len(errors) == 0
