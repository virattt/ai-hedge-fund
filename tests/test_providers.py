"""
Tests for AI model providers.
"""

import pytest
from unittest.mock import Mock, patch

from src.providers.openai_provider import OpenAIProvider
from src.providers.anthropic_provider import AnthropicProvider
from src.providers.gemini_provider import GeminiProvider
from src.providers.mistral_provider import MistralProvider
from src.config import get_model_provider

def test_openai_provider_initialization():
    """Test OpenAI provider initialization."""
    provider = OpenAIProvider()
    assert provider is not None
    assert provider.model_name == "gpt-4"

def test_openai_provider_response_generation():
    """Test OpenAI provider response generation."""
    provider = OpenAIProvider()

    with patch('openai.ChatCompletion.create') as mock_create:
        mock_create.return_value = {
            'choices': [{'message': {'content': 'Test response'}}]
        }

        response = provider.generate_response(
            system_prompt="You are a test assistant.",
            user_prompt="Test prompt"
        )

        assert response == "Test response"
        mock_create.assert_called_once()

def test_openai_provider_response_validation():
    """Test OpenAI provider response validation."""
    provider = OpenAIProvider()

    # Test valid JSON response
    valid_response = '{"key": "value"}'
    assert provider.validate_response(valid_response) == {"key": "value"}

    # Test invalid JSON response
    invalid_response = 'Invalid JSON'
    with pytest.raises(ValueError):
        provider.validate_response(invalid_response)

def test_anthropic_provider_initialization():
    """Test Anthropic provider initialization."""
    provider = AnthropicProvider()
    assert provider is not None
    assert provider.model_name == "claude-3-opus-20240229"

def test_anthropic_provider_response_generation():
    """Test Anthropic provider response generation."""
    provider = AnthropicProvider()

    with patch('anthropic.Anthropic.messages.create') as mock_create:
        mock_create.return_value = Mock(content=[Mock(text="Test response")])

        response = provider.generate_response(
            system_prompt="You are a test assistant.",
            user_prompt="Test prompt"
        )

        assert response == "Test response"
        mock_create.assert_called_once()

def test_anthropic_provider_response_validation():
    """Test Anthropic provider response validation."""
    provider = AnthropicProvider()

    # Test valid JSON response
    valid_response = '{"key": "value"}'
    assert provider.validate_response(valid_response) == {"key": "value"}

    # Test invalid JSON response
    invalid_response = 'Invalid JSON'
    with pytest.raises(ValueError):
        provider.validate_response(invalid_response)

def test_gemini_provider_initialization():
    """Test Gemini provider initialization."""
    provider = GeminiProvider()
    assert provider is not None
    assert provider.model_name == "gemini-pro"

def test_gemini_provider_response_generation():
    """Test Gemini provider response generation."""
    provider = GeminiProvider()

    with patch('google.generativeai.GenerativeModel.generate_content') as mock_generate:
        mock_generate.return_value = Mock(text="Test response")

        response = provider.generate_response(
            system_prompt="You are a test assistant.",
            user_prompt="Test prompt"
        )

        assert response == "Test response"
        mock_generate.assert_called_once()

def test_gemini_provider_response_validation():
    """Test Gemini provider response validation."""
    provider = GeminiProvider()

    # Test valid JSON response
    valid_response = '{"key": "value"}'
    assert provider.validate_response(valid_response) == {"key": "value"}

    # Test invalid JSON response
    invalid_response = 'Invalid JSON'
    with pytest.raises(ValueError):
        provider.validate_response(invalid_response)

def test_mistral_provider_initialization():
    """Test Mistral provider initialization."""
    provider = MistralProvider()
    assert provider is not None
    assert provider.model_name == "mistral-large"

def test_mistral_provider_response_generation():
    """Test Mistral provider response generation."""
    provider = MistralProvider()

    with patch('mistralai.client.MistralClient.chat') as mock_chat:
        mock_chat.return_value = Mock(choices=[Mock(message=Mock(content="Test response"))])

        response = provider.generate_response(
            system_prompt="You are a test assistant.",
            user_prompt="Test prompt"
        )

        assert response == "Test response"
        mock_chat.assert_called_once()

def test_mistral_provider_response_validation():
    """Test Mistral provider response validation."""
    provider = MistralProvider()

    # Test valid JSON response
    valid_response = '{"key": "value"}'
    assert provider.validate_response(valid_response) == {"key": "value"}

    # Test invalid JSON response
    invalid_response = 'Invalid JSON'
    with pytest.raises(ValueError):
        provider.validate_response(invalid_response)

def test_model_provider_factory():
    """Test model provider factory function."""
    # Test OpenAI provider
    openai_provider = get_model_provider("openai")
    assert isinstance(openai_provider, OpenAIProvider)

    # Test Anthropic provider
    anthropic_provider = get_model_provider("anthropic")
    assert isinstance(anthropic_provider, AnthropicProvider)

    # Test invalid provider
    with pytest.raises(ValueError):
        get_model_provider("invalid_provider")

def test_provider_error_handling():
    """Test provider error handling."""
    provider = OpenAIProvider()

    with patch('openai.ChatCompletion.create') as mock_create:
        mock_create.side_effect = Exception("API Error")

        with pytest.raises(Exception):
            provider.generate_response(
                system_prompt="You are a test assistant.",
                user_prompt="Test prompt"
            )
