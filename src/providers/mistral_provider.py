"""
Mistral model provider implementation.
Supports Mistral models through LangChain integration.
"""

from typing import Dict, List, Any
from langchain_mistralai.chat_models import ChatMistralAI
from . import ModelProvider, ModelProviderError, ResponseValidationError

class MistralProvider(ModelProvider):
    """Mistral model provider implementation."""

    def __init__(self, model: str = "mistral-large-latest", **kwargs):
        """
        Initialize Mistral provider with specified model.

        Args:
            model: Mistral model identifier (default: "mistral-large-latest")
            **kwargs: Additional configuration parameters for ChatMistralAI
        """
        try:
            self.model = ChatMistralAI(model=model, **kwargs)
        except Exception as e:
            raise ModelProviderError(f"Failed to initialize Mistral provider: {str(e)}")

    def generate_response(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """
        Generate response using Mistral model.

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
            raise ModelProviderError(f"Mistral response generation failed: {str(e)}")

    def validate_response(self, response: str) -> bool:
        """
        Validate Mistral response format.

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
