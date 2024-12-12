"""
OpenAI model provider implementation.
Supports GPT-4 and other OpenAI models through LangChain integration.
"""

from typing import Dict, List, Any
from langchain_openai import ChatOpenAI
from . import ModelProvider, ModelProviderError, ResponseValidationError

class OpenAIProvider(ModelProvider):
    """OpenAI model provider implementation."""

    def __init__(self, model: str = "gpt-4", **kwargs):
        """
        Initialize OpenAI provider with specified model.

        Args:
            model: OpenAI model identifier (default: "gpt-4")
            **kwargs: Additional configuration parameters for ChatOpenAI
        """
        try:
            self.model = ChatOpenAI(model=model, **kwargs)
        except Exception as e:
            raise ModelProviderError(f"Failed to initialize OpenAI provider: {str(e)}")

    def generate_response(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """
        Generate response using OpenAI model.

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
            raise ModelProviderError(f"OpenAI response generation failed: {str(e)}")

    def validate_response(self, response: str) -> bool:
        """
        Validate OpenAI response format.

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
