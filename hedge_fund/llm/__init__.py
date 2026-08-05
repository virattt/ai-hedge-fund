"""v2 LLM layer — provider protocol, provider clients, prompt cache."""

from hedge_fund.llm.cache import PromptCache, prompt_key
from hedge_fund.llm.client import (
    DEFAULT_MODEL,
    AnthropicLLM,
    ChatLLM,
    LLMClient,
    LLMParseError,
    extract_json,
    make_llm,
)
from hedge_fund.llm.registry import (
    PROVIDER_ENV_VARS,
    SUPPORTED_PROVIDERS,
    env_var_for,
    is_supported,
    load_api_models,
    provider_for,
)
from hedge_fund.llm.watch import ThesisStream

__all__ = [
    "AnthropicLLM",
    "ChatLLM",
    "DEFAULT_MODEL",
    "LLMClient",
    "LLMParseError",
    "PROVIDER_ENV_VARS",
    "PromptCache",
    "SUPPORTED_PROVIDERS",
    "ThesisStream",
    "env_var_for",
    "extract_json",
    "is_supported",
    "load_api_models",
    "make_llm",
    "prompt_key",
    "provider_for",
]
