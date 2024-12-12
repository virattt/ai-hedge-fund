"""
Base agent class for AI-powered trading agents.
Provides common functionality and provider integration for all agents.
"""

from typing import Dict, Any, Optional, List
from ..providers import ModelProvider
from ..config import ModelConfig

class BaseAgent:
    """Base class for all trading agents."""

    def __init__(
        self,
        provider: Optional[ModelProvider] = None,
        config_path: str = "config/models.yaml",
        provider_name: str = "openai",
        model: Optional[str] = None,
    ):
        """
        Initialize base agent with AI provider.

        Args:
            provider: ModelProvider instance (optional)
            config_path: Path to model configuration file
            provider_name: Name of provider to use if no provider given
            model: Model identifier to use with provider

        Raises:
            ValueError: If provider initialization fails
        """
        if provider is None:
            config = ModelConfig(config_path)
            self.provider = config.get_model_provider(provider_name, model)
        else:
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
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return self.provider.generate_response(messages, **kwargs)

    def validate_response(self, response: str) -> bool:
        """
        Validate model response.

        Args:
            response: Response string from model

        Returns:
            bool: True if response is valid
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
