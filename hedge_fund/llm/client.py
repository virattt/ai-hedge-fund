"""LLM provider protocol + the concrete clients.

Mirrors the DataClient pattern (hedge_fund/data/protocol.py): agents depend on the
`LLMClient` protocol, never a concrete provider. Any class with a
`complete(system, user) -> str` method plugs in — community providers welcome.

We deliberately do NOT use langchain's structured-output machinery: its
forced-tool mode breaks on Anthropic reasoning models (v1 carries the same
workaround). For chat providers, we ask for JSON in the prompt and parse it
ourselves; Jev adapts native typed answers into the same JSON contract.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from collections.abc import Callable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Protocol, runtime_checkable

import requests

from hedge_fund.llm import contract
from hedge_fund.llm.registry import (
    env_var_for,
    is_supported,
    KEYLESS_PROVIDERS,
    provider_for,
    SUPPORTED_PROVIDERS,
)

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_TIMEOUT = 60.0
TIMEOUT_ENV_VAR = "LLM_REQUEST_TIMEOUT"
# Modern OpenAI SDK name first; OPENAI_API_BASE is the older alias.
OPENAI_BASE_URL_VARS = ("OPENAI_BASE_URL", "OPENAI_API_BASE")
OLLAMA_BASE_URL_VAR = "OLLAMA_BASE_URL"
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
# ChatOpenAI requires a key string; Ollama ignores it.
OLLAMA_PLACEHOLDER_KEY = "ollama"
OLLAMA_MODEL_PREFIX = "ollama:"

# Called with each piece of text as it arrives. None means don't stream.
TokenListener = Callable[[str], None] | None


class LLMParseError(ValueError):
    """The model's response did not contain parseable JSON."""


class LLMCallError(RuntimeError):
    """Provider failure with optional, credential-free persistence context."""

    def __init__(self, message: str, diagnostic_record: dict | None = None) -> None:
        super().__init__(message)
        self.diagnostic_record = diagnostic_record


@runtime_checkable
class LLMClient(Protocol):
    """Protocol all LLM providers must satisfy.

    complete() returns text (native text or an adapter's compatibility JSON).
    Providers may optionally implement cache_key(agent, system, user) when
    their request contains additional semantics beyond the two prompts.
    Providers should raise on
    transport failure — the LLMAgent layer decides to abstain, not the
    provider.
    """

    model: str

    def complete(self, system: str, user: str) -> str: ...


class ChatLLM:
    """A langchain chat model behind the LLMClient protocol.

    Chat providers share this wrapper — only *constructing* the chat model
    differs, and that lives in make_llm(). Their response handling is written
    once; JevLLM handles TypeSafe's native typed responses separately.

    With an `on_token` listener the same call streams: the listener sees text
    as it arrives, and complete() still returns the whole response. Watching
    is a property of the client, not of the caller — so LLMAgent.predict(),
    the prompt cache, and the parse are untouched by it.
    """

    def __init__(
        self,
        model: str,
        chat,
        on_token: TokenListener = None,
        timeout: float | None = None,
        unreachable_hint: str | None = None,
    ) -> None:
        self.model = model
        self._chat = chat
        self._on_token = on_token
        self._timeout = timeout
        self._unreachable_hint = unreachable_hint

    def complete(self, system: str, user: str) -> str:
        messages = [("system", system), ("human", user)]
        try:
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
        except LLMCallError:
            raise
        except Exception as exc:
            raise _chat_call_error(
                self.model, exc, unreachable_hint=self._unreachable_hint
            ) from None


class JevLLM:
    """Native TypeSafe adapter returning compatibility JSON without streaming.

    Provider metadata travels with the result so cache replay needs no mutable
    last-response state. Native response bodies are preserved except for echoed
    credentials, which are redacted. Credentials are passed in explicitly.
    """

    ENDPOINT = "https://api.typesafe.ai/v1/systemone"
    _RETRY_STATUSES = frozenset({429, 500, 502, 503, 504, 529})

    def __init__(self, api_key: str, model: str = "jev-1.13.0", timeout: float = 60.0) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("A non-empty TypeSafe API key is required")
        self.model = model
        self._api_key = api_key
        self._timeout = _positive_timeout(timeout)

    def cache_key(self, agent: str, system: str, user: str) -> str:
        """Hash semantic inputs only; do not disturb legacy prompt keys."""
        identity = {
            "provider": "TypeSafe",
            "endpoint": self.ENDPOINT,
            "agent": agent,
            "request": contract.build_jev_request(system, user, self.model),
            "contract_version": contract.JEV_CONTRACT_VERSION,
        }
        canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:24]

    def complete(self, system: str, user: str) -> str:
        request = contract.build_jev_request(system, user, self.model)
        started = time.monotonic()
        diagnostics = {
            "provider": "TypeSafe",
            "contract_version": contract.JEV_CONTRACT_VERSION,
            "request": request,
            "attempt_count": 0,
            "status_code": None,
            "raw_response": None,
        }

        def fail(category: str, message: str) -> None:
            diagnostics.update(failure_category=category, elapsed_seconds=time.monotonic() - started)
            # Do not chain transport exceptions: their message/request can carry
            # credentials. Diagnostics intentionally omit all HTTP headers.
            raise LLMCallError(message, self._redact(diagnostics)) from None

        for attempt in range(1, 3):
            diagnostics["attempt_count"] = attempt
            try:
                with requests.post(
                    self.ENDPOINT,
                    json=request,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=self._timeout,
                    allow_redirects=False,
                ) as response:
                    status = response.status_code
                    raw = response.text
                    retry_after = response.headers.get("Retry-After")
            except requests.RequestException:
                fail("transport", "TypeSafe request failed during transport")

            diagnostics.update(status_code=status, raw_response=raw)
            if status in self._RETRY_STATUSES and attempt == 1:
                delay = _retry_delay(retry_after)
                if delay > self._timeout:
                    fail("http", f"TypeSafe HTTP {status}: retry delay exceeds timeout")
                time.sleep(delay)
                continue
            if not 200 <= status < 300:
                fail("http", f"TypeSafe returned HTTP {status}")
            try:
                native_response = json.loads(raw)
            except ValueError:
                fail("json_decode", "TypeSafe returned invalid JSON")
            try:
                payload, metadata = contract.normalize_jev_response(native_response)
            except contract.JevContractError as exc:
                fail("contract", f"TypeSafe response failed validation: {exc}")

            metadata.update(diagnostics, elapsed_seconds=time.monotonic() - started)
            payload["provider_metadata"] = {"jev": self._redact(metadata)}
            return json.dumps(payload)

        raise AssertionError("unreachable: every attempt returns, retries, or raises")

    def _redact(self, value):
        """Protect against a service echoing the API key in an error body."""
        if isinstance(value, str):
            return value.replace(self._api_key, "[REDACTED]")
        if isinstance(value, dict):
            return {self._redact(key): self._redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        return value


def _retry_delay(header: str | None) -> float:
    """One-second backoff, honoring valid delta-seconds and HTTP-date values."""
    if header is not None:
        try:
            seconds = float(header)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(header)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                seconds = (retry_at - datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                return 1.0
        if math.isfinite(seconds):
            return max(1.0, seconds)
    return 1.0


def resolve_timeout(timeout: float | None = None) -> float:
    """Explicit timeout wins; else LLM_REQUEST_TIMEOUT; else DEFAULT_TIMEOUT."""
    if timeout is not None:
        return _positive_timeout(timeout)
    raw = os.getenv(TIMEOUT_ENV_VAR)
    if raw is None or not str(raw).strip():
        return DEFAULT_TIMEOUT
    try:
        return _positive_timeout(float(raw))
    except (TypeError, ValueError):
        raise ValueError(f"{TIMEOUT_ENV_VAR} must be a positive finite number") from None


def _positive_timeout(timeout: object) -> float:
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be a positive finite number")
    return float(timeout)


def _first_env(*names: str) -> str | None:
    """First non-empty environment value among *names*, stripped."""
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return None


def _optional_base_url(*names: str) -> dict:
    """Pass base_url only when set — an explicit None hides OPENAI_BASE_URL."""
    return _optional_kwarg("base_url", *names)


def _optional_kwarg(key: str, *names: str) -> dict:
    value = _first_env(*names)
    return {key: value} if value else {}


def resolve_ollama_base_url(url: str | None = None) -> str:
    """Ollama's OpenAI-compatible root: ``OLLAMA_BASE_URL`` or the local daemon.

    A bare host (``http://127.0.0.1:11434``) becomes ``.../v1``. A URL that
    already ends in ``/v1`` is left alone so overrides are not doubled.
    """
    raw = (url.strip() if isinstance(url, str) and url.strip()
           else _first_env(OLLAMA_BASE_URL_VAR) or DEFAULT_OLLAMA_HOST)
    return _as_openai_compatible(raw)


def _as_openai_compatible(url: str) -> str:
    url = url.rstrip("/")
    return url if url.endswith("/v1") else f"{url}/v1"


def _ollama_tag(model: str) -> str:
    """Strip the ``ollama:`` prefix used to route unlisted local tags."""
    if model.startswith(OLLAMA_MODEL_PREFIX):
        return model[len(OLLAMA_MODEL_PREFIX):]
    return model


def _chat_call_error(
    model: str,
    exc: BaseException,
    unreachable_hint: str | None = None,
) -> LLMCallError:
    """Credential-free failure for chat-provider transport and HTTP errors."""
    hint = f" {unreachable_hint}" if unreachable_hint else ""
    if _is_timeout(exc):
        return LLMCallError(f"LLM request timed out for model {model}.{hint}".rstrip("."))
    status = _http_status(exc)
    if status in (401, 403):
        return LLMCallError(f"LLM endpoint rejected the API key for model {model} (HTTP {status})")
    if status == 404:
        return LLMCallError(
            f"LLM endpoint rejected model {model} (HTTP 404). "
            f"Check the model id and any custom base URL ({OPENAI_BASE_URL_VARS[0]})."
            f"{hint}"
        )
    if status is not None:
        return LLMCallError(f"LLM endpoint rejected the request for model {model} (HTTP {status})")
    if _is_connection_error(exc):
        return LLMCallError(
            f"LLM request failed for model {model}: connection error.{hint}".rstrip(".")
        )
    return LLMCallError(f"LLM request failed for model {model}")


def _walk_exceptions(exc: BaseException):
    seen: set[int] = set()
    stack = [exc]
    while stack:
        current = stack.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        stack.append(current.__cause__)
        stack.append(current.__context__)


def _is_timeout(exc: BaseException) -> bool:
    for current in _walk_exceptions(exc):
        if isinstance(current, (TimeoutError, requests.Timeout)):
            return True
        if "timeout" in type(current).__name__.replace("_", "").lower():
            return True
    return False


def _is_connection_error(exc: BaseException) -> bool:
    for current in _walk_exceptions(exc):
        if isinstance(current, (ConnectionError, requests.ConnectionError)):
            return True
        name = type(current).__name__.replace("_", "").lower()
        if "connection" in name or name in {"apiconnectionerror", "connecterror"}:
            return True
    return False


def _http_status(exc: BaseException) -> int | None:
    for current in _walk_exceptions(exc):
        for attr in ("status_code", "status"):
            value = getattr(current, attr, None)
            if isinstance(value, int) and 100 <= value <= 599:
                return value
        response = getattr(current, "response", None)
        if response is not None:
            value = getattr(response, "status_code", None)
            if isinstance(value, int) and 100 <= value <= 599:
                return value
        match = re.search(r"(?:error code|HTTP)\s*:?\s*(\d{3})", str(current), re.I)
        if match:
            return int(match.group(1))
    return None


def make_llm(
    model: str | None = None,
    timeout: float | None = None,
    max_tokens: int = 4096,
    on_token: TokenListener = None,
) -> LLMClient:
    """Build the client for a model id, routed by the registry's provider.

    The id comes from the caller, else HEDGE_FUND_LLM_MODEL, else DEFAULT_MODEL — the
    same seam the TUI's picker writes to. Raises with the name of the missing
    environment variable, because that is the only thing the user can act on.

    Request timeout is ``timeout`` if given, else ``LLM_REQUEST_TIMEOUT``, else
    60 seconds. OpenAI-compatible transports honor ``OPENAI_BASE_URL`` /
    ``OPENAI_API_BASE`` (and the provider-specific aliases already documented).
    Ollama talks to ``OLLAMA_BASE_URL`` (default ``http://127.0.0.1:11434``)
    and needs no API key. Unlisted local tags route with an ``ollama:`` prefix
    (``ollama:mistral`` → tag ``mistral``).
    """
    model = model or os.environ.get("HEDGE_FUND_LLM_MODEL") or DEFAULT_MODEL
    provider = provider_for(model)
    if provider is None and model.startswith(OLLAMA_MODEL_PREFIX):
        tag = _ollama_tag(model)
        if not tag:
            raise ValueError(
                "Ollama model id is empty. Use ollama:<tag> (see `ollama list`)."
            )
        provider = "Ollama"
        model = tag
    if provider is None:
        # Unlisted ids still work: a model newer than the registry should not
        # need a code change. A custom OpenAI-compatible base URL means the
        # caller is routing that id (Groq, local proxy, ...) off OpenAI's host;
        # otherwise Anthropic remains the default transport.
        provider = "OpenAI" if _first_env(*OPENAI_BASE_URL_VARS) else "Anthropic"
    if not is_supported(provider):
        raise ValueError(
            f"No v2 client for {provider} (model {model}). "
            f"Supported: {', '.join(sorted(SUPPORTED_PROVIDERS))}."
        )

    timeout = resolve_timeout(timeout)
    if provider == "Ollama":
        return _ollama_llm(model, timeout=timeout, on_token=on_token)

    api_key = _require_key(provider)

    if provider == "TypeSafe":
        # Typed judgments have no generated tokens or output-token budget.
        return JevLLM(api_key=api_key, model=model, timeout=timeout)

    if provider == "Anthropic":
        from langchain_anthropic import ChatAnthropic
        chat = ChatAnthropic(model=model, api_key=api_key, timeout=timeout,
                             max_retries=1, max_tokens=max_tokens)
    elif provider == "OpenAI":
        from langchain_openai import ChatOpenAI
        chat = ChatOpenAI(model=model, api_key=api_key, timeout=timeout,
                          max_retries=1, **_optional_base_url(*OPENAI_BASE_URL_VARS))
    elif provider == "DeepSeek":
        from langchain_deepseek import ChatDeepSeek
        chat = ChatDeepSeek(model=model, api_key=api_key, timeout=timeout,
                            max_retries=1, **_optional_kwarg("api_base", "DEEPSEEK_BASE_URL", "DEEPSEEK_API_BASE"))
    elif provider == "Google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        chat = ChatGoogleGenerativeAI(model=model, api_key=api_key,
                                      timeout=timeout, max_retries=1)
    elif provider == "xAI":
        from langchain_xai import ChatXAI
        chat = ChatXAI(model=model, api_key=api_key, timeout=timeout,
                       max_retries=1, **_optional_kwarg("xai_api_base", "XAI_BASE_URL", "XAI_API_BASE"))
    elif provider == "Kimi":
        # Moonshot speaks the OpenAI wire format. Default to the international
        # host; mainland users override with MOONSHOT_BASE_URL (v1 does the same).
        from langchain_openai import ChatOpenAI
        chat = ChatOpenAI(
            model=model, api_key=api_key, timeout=timeout, max_retries=1,
            base_url=(_first_env("MOONSHOT_BASE_URL") or "https://api.moonshot.ai/v1"))
    else:  # pragma: no cover - SUPPORTED_PROVIDERS is checked above
        raise ValueError(f"Unhandled provider {provider}")

    return ChatLLM(model, chat, on_token, timeout=timeout)


def _ollama_llm(
    model: str,
    timeout: float,
    on_token: TokenListener,
) -> ChatLLM:
    """Local Ollama via the OpenAI-compatible /v1 surface. No cloud key."""
    from langchain_openai import ChatOpenAI

    host = _first_env(OLLAMA_BASE_URL_VAR) or DEFAULT_OLLAMA_HOST
    base_url = resolve_ollama_base_url(host)
    chat = ChatOpenAI(
        model=model,
        api_key=OLLAMA_PLACEHOLDER_KEY,
        timeout=timeout,
        max_retries=1,
        base_url=base_url,
    )
    return ChatLLM(
        model,
        chat,
        on_token,
        timeout=timeout,
        unreachable_hint=f"Is the Ollama daemon running at {host}?",
    )


def AnthropicLLM(model: str | None = None, **kwargs) -> LLMClient:  # noqa: N802
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
    if provider in KEYLESS_PROVIDERS:
        raise AssertionError(f"{provider} does not use an API key")
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
