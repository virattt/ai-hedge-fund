"""
Base agent class for AI-powered trading agents.
Provides common functionality and provider integration for all agents.
"""

from typing import Dict, Any, Optional, List
from ..providers import BaseProvider

class BaseAgent:
    """Base class for all trading agents."""

    def __init__(self, provider: BaseProvider):
        """
        Initialize base agent with AI provider.

        Args:
            provider: BaseProvider instance for model interactions

        Raises:
            ValueError: If provider is None
        """
        if provider is None:
            raise ValueError("Provider cannot be None")
        self.provider = provider

    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any
    ) -> str:
        """
        Generate response from AI provider.

        Args:
            system_prompt: System context for the model
            user_prompt: User input for the model
            **kwargs: Additional parameters for provider

        Returns:
            str: Model response

        Raises:
            Exception: If response generation fails
        """
        return self.provider.generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            **kwargs
        )

    def validate_response(self, response: str) -> Dict[str, Any]:
        """
        Validate and parse model response.

        Args:
            response: Response string from model

        Returns:
            Dict: Parsed response data

        Raises:
            ResponseValidationError: If response is invalid
        """
        return self.provider.validate_response(response)

    def format_message(self, content: str, name: str) -> Dict[str, Any]:
        """
        Format agent message for state graph.

        Args:
            content: Message content
            name: Agent name

        Returns:
            Dict containing formatted message
        """
        return {
            "content": content,
            "name": name
        }
