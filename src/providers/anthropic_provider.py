from typing import Any, Dict, Optional
from langchain_anthropic import ChatAnthropicMessages
from .base import BaseProvider

class AnthropicProvider(BaseProvider):
    """Provider implementation for Anthropic's Claude models."""

    def __init__(self, model: str, **kwargs):
        """Initialize Anthropic provider with model and settings.

        Args:
            model: Name of the Claude model to use
            **kwargs: Additional settings (temperature, max_tokens, etc.)
        """
        super().__init__(model, **kwargs)
        self.client = ChatAnthropicMessages(
            model=model,
            temperature=kwargs.get('temperature', 0.7),
            max_tokens=kwargs.get('max_tokens', 4096),
            top_p=kwargs.get('top_p', 1.0)
        )

    def generate(self, prompt: str) -> str:
        """Generate a response using the Claude model.

        Args:
            prompt: Input text to generate response from

        Returns:
            Generated text response

        Raises:
            Exception: If API call fails or other errors occur
        """
        try:
            response = self.client.invoke(prompt)
            return response.content
        except Exception as e:
            self._handle_error(e)
            raise  # Re-raise after logging
