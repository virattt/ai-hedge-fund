"""
Model configuration management for AI providers.
Handles loading and validation of model configurations from YAML files.
"""

from typing import Dict, Any, Optional
import os
import yaml
from ..providers import (
    BaseProvider,
    OpenAIProvider
)

class ConfigurationError(Exception):
    """Raised when configuration loading or validation fails."""
    pass

class ModelConfig:
    """Manages model configurations for different AI providers."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize model configuration from YAML file.

        Args:
            config_path: Path to YAML configuration file (optional)

        Raises:
            ConfigurationError: If configuration loading or validation fails
        """
        self.config_path = config_path or os.path.join("config", "models.yaml")
        self.config = self._load_config()
        self._validate_config()

    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file.

        Returns:
            Dict containing provider configurations

        Raises:
            ConfigurationError: If file loading fails
        """
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise ConfigurationError(f"Failed to load config from {self.config_path}: {str(e)}")

    def _validate_config(self) -> None:
        """
        Validate configuration structure.

        Raises:
            ConfigurationError: If configuration is invalid
        """
        if not isinstance(self.config, dict):
            raise ConfigurationError("Configuration must be a dictionary")

        if 'providers' not in self.config:
            raise ConfigurationError("Configuration must have 'providers' section")

        for provider, settings in self.config['providers'].items():
            if 'default_model' not in settings:
                raise ConfigurationError(f"Provider {provider} missing 'default_model'")
            if 'models' not in settings:
                raise ConfigurationError(f"Provider {provider} missing 'models' list")
            if not isinstance(settings['models'], list):
                raise ConfigurationError(f"Provider {provider} 'models' must be a list")

    def get_provider_config(self, provider_name: str) -> Dict[str, Any]:
        """
        Get configuration for specific provider.

        Args:
            provider_name: Name of the provider

        Returns:
            Provider configuration dictionary

        Raises:
            ConfigurationError: If provider not found
        """
        if provider_name not in self.config['providers']:
            raise ConfigurationError(f"Provider {provider_name} not found in configuration")
        return self.config['providers'][provider_name]

    def get_default_model(self, provider_name: str) -> str:
        """
        Get default model for provider.

        Args:
            provider_name: Name of the provider

        Returns:
            Default model identifier

        Raises:
            ConfigurationError: If provider not found
        """
        return self.get_provider_config(provider_name)['default_model']

def get_model_provider(
    provider_name: str = "openai",
    model: Optional[str] = None,
    config_path: Optional[str] = None
) -> BaseProvider:
    """
    Factory function to create model provider instance.

    Args:
        provider_name: Name of the provider (default: "openai")
        model: Model identifier (optional)
        config_path: Path to configuration file (optional)

    Returns:
        BaseProvider instance

    Raises:
        ConfigurationError: If provider creation fails
    """
    try:
        config = ModelConfig(config_path)
        provider_config = config.get_provider_config(provider_name)
        model_name = model or provider_config['default_model']

        if provider_name == "openai":
            return OpenAIProvider(
                model_name=model_name,
                settings=provider_config.get('settings', {})
            )
        else:
            raise ConfigurationError(f"Unsupported provider: {provider_name}")
    except Exception as e:
        raise ConfigurationError(f"Failed to create provider {provider_name}: {str(e)}")
