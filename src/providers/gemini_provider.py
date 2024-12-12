"""
Google Gemini model provider implementation.
Supports Gemini models through LangChain integration.
"""

from typing import Dict, List, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from . import ModelProvider, ModelProviderError, ResponseValidationError

class GeminiProvider(ModelProvider):
    """Google Gemini model provider implementation."""


    def __init__(self, model: str = "gemini-pro", **kwargs):
        """
        Initialize Gemini provider with specified model.

        Args:
            model: Gemini model identifier (default: "gemini-pro")
            **kwargs: Additional configuration parameters for ChatGoogleGenerativeAI
        """
        try:
            self.model = ChatGoogleGenerativeAI(model=model, **kwargs)
        except Exception as e:
            raise ModelProviderError(f"Failed to initialize Gemini provider: {str(e)}")

    def generate_response(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """
        Generate response using Gemini model.

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
            raise ModelProviderError(f"Gemini response generation failed: {str(e)}")

    def validate_response(self, response: str) -> bool:
        """
        Validate Gemini response format.

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
