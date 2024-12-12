"""
Tests for AI model providers.
"""

import pytest
from unittest.mock import Mock, patch

from src.providers.base import (
    BaseProvider,
    ModelProviderError,
    ResponseValidationError,
    ProviderConnectionError,
    ProviderAuthenticationError,
    ProviderQuotaError
)
from src.providers.openai_provider import OpenAIProvider

def test_openai_provider_initialization():
    """Test OpenAI provider initialization."""
    provider = OpenAIProvider(model_name="gpt-4")
    assert provider is not None
    assert provider.model_name == "gpt-4"
    assert isinstance(provider.settings, dict)

def test_openai_provider_response_generation():
    """Test OpenAI provider response generation."""
    provider = OpenAIProvider(model_name="gpt-4")
    provider.client = Mock()
    provider.client.invoke.return_value.content = "Test response"

    response = provider.generate_response(
        system_prompt="You are a test assistant.",
        user_prompt="Test prompt"
    )

    assert response == "Test response"
    provider.client.invoke.assert_called_once()

def test_openai_provider_response_validation():
    """Test OpenAI provider response validation."""
    provider = OpenAIProvider(model_name="gpt-4")

    # Test valid JSON response
    valid_response = '{"key": "value"}'
    result = provider.validate_response(valid_response)
    assert isinstance(result, dict)
    assert result["key"] == "value"

    # Test invalid responses
    with pytest.raises(ResponseValidationError):
        provider.validate_response("")

    with pytest.raises(ResponseValidationError):
        provider.validate_response("Invalid JSON")

def test_provider_error_handling():
    """Test provider error handling."""
    provider = OpenAIProvider(model_name="gpt-4")
    provider.client = Mock()

    # Test authentication error
    provider.client.invoke.side_effect = Exception("authentication failed")
    with pytest.raises(ProviderAuthenticationError):
        provider.generate_response(
            system_prompt="Test system prompt",
            user_prompt="Test user prompt"
        )

    # Test rate limit error
    provider.client.invoke.side_effect = Exception("rate limit exceeded")
    with pytest.raises(ProviderQuotaError):
        provider.generate_response(
            system_prompt="Test system prompt",
            user_prompt="Test user prompt"
        )

    # Test connection error
    provider.client.invoke.side_effect = Exception("connection failed")
    with pytest.raises(ProviderConnectionError):
        provider.generate_response(
            system_prompt="Test system prompt",
            user_prompt="Test user prompt"
        )

    # Test generic error
    provider.client.invoke.side_effect = Exception("unknown error")
    with pytest.raises(ModelProviderError):
        provider.generate_response(
            system_prompt="Test system prompt",
            user_prompt="Test user prompt"
        )
