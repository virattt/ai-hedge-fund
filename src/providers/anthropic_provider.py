"""
Anthropic model provider implementation.
Supports Claude-3 and other Anthropic models through LangChain integration.
"""

from typing import Dict, List, Any
from langchain_anthropic import ChatAnthropic
from . import ModelProvider, ModelProviderError, ResponseValidationError

class AnthropicProvider(ModelProvider):
    """Anthropic model provider implementation."""

    def __init__(self, model: str = "claude-3-opus-20240229", **kwargs):
        """
        Initialize Anthropic provider with specified model.

        Args:
            model: Anthropic model identifier (default: "claude-3-opus-20240229")
            **kwargs: Additional configuration parameters for ChatAnthropic
        """
        try:
            self.model = ChatAnthropic(model=model, **kwargs)
        except Exception as e:
            raise ModelProviderError(f"Failed to initialize Anthropic provider: {str(e)}")

    def generate_response(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """
        Generate response using Anthropic model.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            **kwargs: Additional parameters for model invocation

        Returns:
            str: Model response

        Raises:
            ModelProviderError: If response generation fails
        """
        try:
            response = self.model.invoke(messages)
            return response.content
        except Exception as e:
            raise ModelProviderError(f"Anthropic response generation failed: {str(e)}")

    def validate_response(self, response: str) -> bool:
        """
        Validate Anthropic response format.

        Args:
            response: Response string from the model

        Returns:
            bool: True if response is valid

        Raises:
            ResponseValidationError: If validation fails
        """
        try:
            # For responses that should be JSON
            if self._validate_json_response(response):
                return True

            # For non-JSON responses, ensure it's a non-empty string
            if isinstance(response, str) and response.strip():
                return True

            raise ResponseValidationError("Invalid response format")
        except Exception as e:
            raise ResponseValidationError(f"Response validation failed: {str(e)}")
