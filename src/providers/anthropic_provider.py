from typing import Any, Dict, Optional
from langchain_anthropic import ChatAnthropicMessages
from .base import (
    BaseProvider,
    ModelProviderError,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderQuotaError
)

class AnthropicProvider(BaseProvider):
    """Provider implementation for Anthropic's Claude models."""

    def __init__(self, model_name: str, settings: Dict[str, Any] = None):
        """Initialize Anthropic provider with model and settings.

        Args:
            model_name: Name of the Claude model to use
            settings: Additional settings (temperature, max_tokens, etc.)
        """
        super().__init__(model_name=model_name, settings=settings or {})

    def _initialize_provider(self) -> None:
        """Initialize the Anthropic client with model settings."""
        try:
            self.client = ChatAnthropicMessages(
                model=self.model_name,
                temperature=self.settings.get('temperature', 0.7),
                max_tokens=self.settings.get('max_tokens', 4096),
                top_p=self.settings.get('top_p', 1.0)
            )
        except Exception as e:
            if "authentication" in str(e).lower():
                raise ProviderAuthenticationError(str(e), provider="Anthropic")
            elif "rate limit" in str(e).lower():
                raise ProviderQuotaError(str(e), provider="Anthropic")
            elif "connection" in str(e).lower():
                raise ProviderConnectionError(str(e), provider="Anthropic")
            else:
                raise ModelProviderError(str(e), provider="Anthropic")

    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a response using the Claude model.

        Args:
            system_prompt: System context for the model
            user_prompt: User input to generate response from

        Returns:
            Generated text response

        Raises:
            ModelProviderError: If API call fails or other errors occur
        """
        try:
            response = self.client.invoke(f"{system_prompt}\n\n{user_prompt}")
            return response.content
        except Exception as e:
            if "authentication" in str(e).lower():
                raise ProviderAuthenticationError(str(e), provider="Anthropic")
            elif "rate limit" in str(e).lower():
                raise ProviderQuotaError(str(e), provider="Anthropic")
            elif "connection" in str(e).lower():
                raise ProviderConnectionError(str(e), provider="Anthropic")
            else:
                raise ModelProviderError(str(e), provider="Anthropic")
