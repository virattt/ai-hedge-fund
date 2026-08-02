"""LLM provider protocol + the concrete clients.

Mirrors the DataClient pattern (hedge_fund/data/protocol.py): agents depend on the
`LLMClient` protocol, never a concrete provider. Any class with a
`complete(system, user) -> str` method plugs in — community providers welcome.

We deliberately do NOT use langchain's structured-output machinery: its
forced-tool mode breaks on Anthropic reasoning models (v1 carries the same
workaround). We ask for JSON in the prompt and parse it ourselves.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from hedge_fund.llm.registry import (
    SUPPORTED_PROVIDERS,
    env_var_for,
    is_supported,
    provider_for,
)

DEFAULT_MODEL = "claude-sonnet-5"

# Called with each piece of text as it arrives. None means don't stream.
TokenListener = Callable[[str], None] | None


class LLMParseError(ValueError):
    """The model's response did not contain parseable JSON."""


@runtime_checkable
class LLMClient(Protocol):
    """Protocol all LLM providers must satisfy.

    complete() returns the model's raw text. Providers should raise on
    transport failure — the LLMAgent layer decides to abstain, not the
    provider.
    """

    model: str

    def complete(self, system: str, user: str) -> str: ...


class ChatLLM:
    """A langchain chat model behind the LLMClient protocol.

    Every provider we support ends up here — only *constructing* the chat
    model differs, and that lives in make_llm(). The response handling is
    identical across providers, so it is written once.

    With an `on_token` listener the same call streams: the listener sees text
    as it arrives, and complete() still returns the whole response. Watching
    is a property of the client, not of the caller — so LLMAgent.predict(),
    the prompt cache, and the parse are untouched by it.
    """

    def __init__(self, model: str, chat, on_token: TokenListener = None) -> None:
        self.model = model
        self._chat = chat
        self._on_token = on_token

    def complete(self, system: str, user: str) -> str:
        messages = [("system", system), ("human", user)]
        if self._on_token is None:
            return _flatten(self._chat.invoke(messages).content)

        # Streaming chunks concatenate into the response, so they flatten
        # without a separator — the "\n" that joins whole-message blocks would
        # land mid-word here.
        parts: list[str] = []
        for chunk in self._chat.stream(messages):
            text = _flatten(chunk.content, sep="")
            if text:
                parts.append(text)
                self._on_token(text)
        return "".join(parts)


def make_llm(
    model: str | None = None,
    timeout: float = 60.0,
    max_tokens: int = 4096,
    on_token: TokenListener = None,
) -> ChatLLM:
    """Build the client for a model id, routed by the registry's provider.

    The id comes from the caller, else HEDGE_FUND_LLM_MODEL, else DEFAULT_MODEL — the
    same seam the TUI's picker writes to. Raises with the name of the missing
    environment variable, because that is the only thing the user can act on.
    """
    model = model or os.environ.get("HEDGE_FUND_LLM_MODEL") or DEFAULT_MODEL
    provider = provider_for(model)
    if provider is None:
        # Unlisted ids still work: a model newer than the registry should not
        # need a code change. Anthropic is the default transport.
        provider = "Anthropic"
    if not is_supported(provider):
        raise ValueError(
            f"No v2 client for {provider} (model {model}). "
            f"Supported: {', '.join(sorted(SUPPORTED_PROVIDERS))}."
        )

    api_key = _require_key(provider)

    if provider == "Anthropic":
        from langchain_anthropic import ChatAnthropic
        chat = ChatAnthropic(model=model, api_key=api_key, timeout=timeout,
                             max_retries=1, max_tokens=max_tokens)
    elif provider == "OpenAI":
        from langchain_openai import ChatOpenAI
        chat = ChatOpenAI(model=model, api_key=api_key, timeout=timeout,
                          max_retries=1, base_url=os.getenv("OPENAI_API_BASE"))
    elif provider == "DeepSeek":
        from langchain_deepseek import ChatDeepSeek
        chat = ChatDeepSeek(model=model, api_key=api_key, timeout=timeout,
                            max_retries=1)
    elif provider == "Google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        chat = ChatGoogleGenerativeAI(model=model, api_key=api_key,
                                      timeout=timeout, max_retries=1)
    elif provider == "xAI":
        from langchain_xai import ChatXAI
        chat = ChatXAI(model=model, api_key=api_key, timeout=timeout,
                       max_retries=1)
    elif provider == "Kimi":
        # Moonshot speaks the OpenAI wire format. Default to the international
        # host; mainland users override with MOONSHOT_BASE_URL (v1 does the same).
        from langchain_openai import ChatOpenAI
        chat = ChatOpenAI(
            model=model, api_key=api_key, timeout=timeout, max_retries=1,
            base_url=(os.getenv("MOONSHOT_BASE_URL")
                      or "https://api.moonshot.ai/v1"))
    else:  # pragma: no cover - SUPPORTED_PROVIDERS is checked above
        raise ValueError(f"Unhandled provider {provider}")

    return ChatLLM(model, chat, on_token)


def AnthropicLLM(model: str | None = None, **kwargs) -> ChatLLM:  # noqa: N802
    """Back-compat shim: v2 was Anthropic-only, and this name is exported.
    Prefer make_llm(), which honours whichever model is selected."""
    return make_llm(model or DEFAULT_MODEL, **kwargs)


def _flatten(content, sep: str = "\n") -> str:
    """One provider's response as plain text.

    Reasoning models (Anthropic extended thinking, and Gemini/DeepSeek in
    their thinking modes) return a LIST of blocks rather than a string. Only
    the text blocks are the answer — a thinking block stringified into the
    payload is prose in front of the JSON, which is exactly what breaks the
    parse. Mirrors v1's extract_json_from_response (src/utils/llm.py:109).

    *sep* joins the blocks: "\\n" for a whole message, "" for a stream chunk
    whose blocks are fragments of one continuing string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return sep.join(parts)
    return "" if content is None else str(content)


def _require_key(provider: str) -> str:
    """The provider's API key, or a failure that names the variable to set."""
    env_var = env_var_for(provider)
    # Kimi accepts either name; v1 reads MOONSHOT_API_KEY first.
    key = (os.getenv("MOONSHOT_API_KEY") if provider == "Kimi" else None)
    key = key or (os.getenv(env_var) if env_var else None)
    if not key:
        raise ValueError(
            f"{env_var} not found. Set it in your .env to use {provider} models."
        )
    return key


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of an LLM response.

    Tries: ```json fence -> whole string -> first balanced {...} block.
    Raises LLMParseError if nothing parses.
    """
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break

    raise LLMParseError(f"no JSON object found in response: {text[:200]!r}")
