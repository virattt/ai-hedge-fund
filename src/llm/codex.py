"""LangChain chat model that routes OpenAI calls through the Codex CLI
OAuth token. Used when OPENAI_API_KEY is not set. Reads the access token
from ~/.codex/auth.json and passes it as a Bearer token to the OpenAI API."""

import json
import os
import sys
from typing import Any, List, Optional

from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

_NOTICE_SHOWN = False
_AUTH_FILE = os.path.join(os.path.expanduser("~"), ".codex", "auth.json")


def _notice_once() -> None:
    global _NOTICE_SHOWN
    if not _NOTICE_SHOWN:
        print(
            "[ai-hedge-fund] No OPENAI_API_KEY set — using Codex CLI "
            "subscription via codex exec.",
            file=sys.stderr,
        )
        _NOTICE_SHOWN = True


def _read_access_token() -> str:
    with open(_AUTH_FILE, "r", encoding="utf-8") as f:
        auth = json.load(f)
    token = auth.get("tokens", {}).get("access_token", "")
    if not token:
        raise ValueError(
            "No access_token found in ~/.codex/auth.json. "
            "Please log in via the Codex CLI: codex login"
        )
    return token


class ChatCodex(BaseChatModel):
    """Routes OpenAI API calls through the Codex CLI subscription OAuth token."""

    model_name: str = "gpt-5.5"
    effort: Optional[str] = "high"

    @property
    def _llm_type(self) -> str:
        return "codex-subscription"

    @property
    def _identifying_params(self) -> dict:
        return {"model_name": self.model_name, "effort": self.effort}

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        from langchain_openai import ChatOpenAI

        _notice_once()
        access_token = _read_access_token()

        model_kwargs: dict = {}
        if self.effort:
            model_kwargs["reasoning_effort"] = self.effort

        llm = ChatOpenAI(
            model=self.model_name,
            api_key=access_token,
            model_kwargs=model_kwargs if model_kwargs else None,
        )

        result = llm._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        return result
