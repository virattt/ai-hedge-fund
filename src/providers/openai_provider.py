"""
OpenAI model provider implementation.
Supports GPT-4 and other OpenAI models through LangChain integration.
"""

from typing import Dict, Any
from langchain_openai import ChatOpenAI

from .base import (
    BaseProvider,
    ModelProviderError,
    ResponseValidationError,
    ProviderConnectionError,
    ProviderAuthenticationError,
    ProviderQuotaError
)

class OpenAIProvider(BaseProvider):
    """OpenAI model provider implementation."""

    def _initialize_provider(self) -> None:
        """Initialize the OpenAI client."""
        try:
            self.client = ChatOpenAI(
                model_name=self.model_name,
                **self.settings
            )
        except Exception as e:
            raise ModelProviderError(
                f"Failed to initialize OpenAI provider: {str(e)}",
                provider="OpenAI"
            )

    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        """Generate response using OpenAI model."""
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            response = self.client.invoke(messages)
            return response.content
        except Exception as e:
            if "authentication" in str(e).lower():
                raise ProviderAuthenticationError(
                    "OpenAI authentication failed",
                    provider="OpenAI"
                )
            elif "rate" in str(e).lower():
                raise ProviderQuotaError(
                    "OpenAI rate limit exceeded",
                    provider="OpenAI"
                )
            elif "connection" in str(e).lower():
                raise ProviderConnectionError(
                    "OpenAI connection failed",
                    provider="OpenAI"
                )
            else:
                raise ModelProviderError(
                    f"OpenAI response generation failed: {str(e)}",
                    provider="OpenAI"
                )

    def validate_response(self, response: str) -> Dict[str, Any]:
        """Validate OpenAI response format."""
        if not isinstance(response, str):
            raise ResponseValidationError(
                "Response must be a string",
                provider="OpenAI",
                response=response
            )
        if not response.strip():
            raise ResponseValidationError(
                "Response cannot be empty",
                provider="OpenAI",
                response=response
            )
        return super().validate_response(response)
