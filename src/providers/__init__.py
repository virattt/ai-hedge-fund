"""
Provider abstraction layer for AI model integration.
Defines the base interface that all model providers must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import json

class ModelProviderError(Exception):
    """Base exception class for model provider errors."""
    pass

class ResponseValidationError(ModelProviderError):
    """Raised when model response validation fails."""
    pass

class ModelProvider(ABC):
    """
    Abstract base class for AI model providers.
    All model providers must implement these methods to ensure consistent behavior
    across different AI services.
    """

    @abstractmethod
    def generate_response(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """
        Generate a response from the AI model based on input messages.

        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            **kwargs: Additional provider-specific parameters

        Returns:
            str: The model's response

        Raises:
            ModelProviderError: If the model fails to generate a response
        """
        pass

    @abstractmethod
    def validate_response(self, response: str) -> bool:
        """
        Validate that the model's response meets the expected format.

        Args:
            response: The raw response string from the model

        Returns:
            bool: True if response is valid, False otherwise

        Raises:
            ResponseValidationError: If response validation fails
        """
        pass

    def _validate_json_response(self, response: str) -> bool:
        """
        Helper method to validate JSON responses.

        Args:
            response: String that should contain valid JSON

        Returns:
            bool: True if response is valid JSON, False otherwise
        """
        try:
            json.loads(response)
            return True
        except json.JSONDecodeError:
            return False
