"""LLM provider protocol + the Anthropic implementation.

Mirrors the DataClient pattern (v2/data/protocol.py): agents depend on the
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
from typing import Protocol, runtime_checkable

DEFAULT_MODEL = "claude-sonnet-5"


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


class AnthropicLLM:
    """Anthropic provider via the existing langchain-anthropic dependency
    (transport only — no structured-output magic)."""

    def __init__(
        self,
        model: str | None = None,
        timeout: float = 60.0,
        max_tokens: int = 4096,
    ) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not found. Set it in your .env to use LLM agents."
            )
        from langchain_anthropic import ChatAnthropic

        self.model = model or os.getenv("V2_LLM_MODEL", DEFAULT_MODEL)
        self._chat = ChatAnthropic(
            model=self.model,
            api_key=api_key,
            timeout=timeout,
            max_retries=1,
            max_tokens=max_tokens,
        )

    def complete(self, system: str, user: str) -> str:
        result = self._chat.invoke([("system", system), ("human", user)])
        content = result.content
        # Anthropic reasoning models return a list of content blocks.
        if isinstance(content, list):
            content = "".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        return content


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
