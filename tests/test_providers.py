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
from src.providers.anthropic_provider import AnthropicProvider

@patch('src.providers.openai_provider.ChatOpenAI')
def test_openai_provider_initialization(mock_chat_openai):
    """Test OpenAI provider initialization."""
    mock_client = Mock()
    mock_chat_openai.return_value = mock_client

    provider = OpenAIProvider(model_name="gpt-4")
    assert provider is not None
    assert provider.model_name == "gpt-4"
    assert isinstance(provider.settings, dict)
    assert provider.client == mock_client

@patch('src.providers.openai_provider.ChatOpenAI')
def test_openai_provider_response_generation(mock_chat_openai):
    """Test OpenAI provider response generation."""
    mock_client = Mock()
    mock_client.invoke.return_value.content = "Test response"
    mock_chat_openai.return_value = mock_client

    provider = OpenAIProvider(model_name="gpt-4")
    response = provider.generate_response(
        system_prompt="You are a test assistant.",
        user_prompt="Test prompt"
    )

    assert response == "Test response"
    mock_client.invoke.assert_called_once()

@patch('src.providers.openai_provider.ChatOpenAI')
def test_openai_provider_response_validation(mock_chat_openai):
    """Test OpenAI provider response validation."""
    mock_client = Mock()
    mock_chat_openai.return_value = mock_client

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

@patch('src.providers.openai_provider.ChatOpenAI')
def test_provider_error_handling(mock_chat_openai):
    """Test provider error handling."""
    mock_client = Mock()
    mock_chat_openai.return_value = mock_client

    provider = OpenAIProvider(model_name="gpt-4")

    # Test authentication error
    mock_client.invoke.side_effect = Exception("authentication failed")
    with pytest.raises(ProviderAuthenticationError):
        provider.generate_response(
            system_prompt="Test system prompt",
            user_prompt="Test user prompt"
        )

    # Test rate limit error
    mock_client.invoke.side_effect = Exception("rate limit exceeded")
    with pytest.raises(ProviderQuotaError):
        provider.generate_response(
            system_prompt="Test system prompt",
            user_prompt="Test user prompt"
        )

    # Test connection error
    mock_client.invoke.side_effect = Exception("connection failed")
    with pytest.raises(ProviderConnectionError):
        provider.generate_response(
            system_prompt="Test system prompt",
            user_prompt="Test user prompt"
        )

    # Test generic error
    mock_client.invoke.side_effect = Exception("unknown error")
    with pytest.raises(ModelProviderError):
        provider.generate_response(
            system_prompt="Test system prompt",
            user_prompt="Test user prompt"
        )

@patch('src.providers.anthropic_provider.ChatAnthropicMessages')
def test_anthropic_provider_initialization(mock_chat_anthropic):
    """Test Anthropic provider initialization."""
    mock_client = Mock()
    mock_chat_anthropic.return_value = mock_client

    # Test with claude-3-opus
    provider = AnthropicProvider(
        model_name="claude-3-opus-20240229",
        settings={
            'temperature': 0.7,
            'max_tokens': 4096
        }
    )
    assert provider is not None
    assert provider.model_name == "claude-3-opus-20240229"
    assert isinstance(provider.settings, dict)
    assert provider.client == mock_client

    # Test with claude-3-sonnet
    provider = AnthropicProvider(
        model_name="claude-3-sonnet-20240229",
        settings={
            'temperature': 0.7,
            'max_tokens': 4096
        }
    )
    assert provider is not None
    assert provider.model_name == "claude-3-sonnet-20240229"

@patch('src.providers.anthropic_provider.ChatAnthropicMessages')
def test_anthropic_provider_response_generation(mock_chat_anthropic):
    """Test Anthropic provider response generation."""
    mock_client = Mock()
    mock_client.invoke.return_value.content = "Test response"
    mock_chat_anthropic.return_value = mock_client

    provider = AnthropicProvider(
        model_name="claude-3-opus-20240229",
        settings={'temperature': 0.7}
    )
    response = provider.generate_response("System prompt", "Test prompt")

    assert response == "Test response"
    mock_client.invoke.assert_called_once()

@patch('src.providers.anthropic_provider.ChatAnthropicMessages')
def test_anthropic_provider_error_handling(mock_chat_anthropic):
    """Test Anthropic provider error handling."""
    mock_client = Mock()
    mock_chat_anthropic.return_value = mock_client

    provider = AnthropicProvider(
        model_name="claude-3-opus-20240229",
        settings={'temperature': 0.7}
    )

    # Test authentication error
    mock_client.invoke.side_effect = Exception("authentication failed")
    with pytest.raises(ProviderAuthenticationError):
        provider.generate_response("System prompt", "Test prompt")

    # Test rate limit error
    mock_client.invoke.side_effect = Exception("rate limit exceeded")
    with pytest.raises(ProviderQuotaError):
        provider.generate_response("System prompt", "Test prompt")

    # Test connection error
    mock_client.invoke.side_effect = Exception("connection failed")
    with pytest.raises(ProviderConnectionError):
        provider.generate_response("System prompt", "Test prompt")

    # Test generic error
    mock_client.invoke.side_effect = Exception("unknown error")
    with pytest.raises(ModelProviderError):
        provider.generate_response("System prompt", "Test prompt")
