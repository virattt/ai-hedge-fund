"""LangChain chat model that routes Anthropic calls through the user's
Claude Code subscription via the `claude-agent-sdk`. Used only when
ANTHROPIC_API_KEY is not set."""

import asyncio
import concurrent.futures
import sys
from typing import Any, List, Optional

from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

_NOTICE_SHOWN = False


def _notice_once() -> None:
    global _NOTICE_SHOWN
    if not _NOTICE_SHOWN:
        print(
            "[ai-hedge-fund] No ANTHROPIC_API_KEY set — using Claude Code "
            "subscription via claude-agent-sdk.",
            file=sys.stderr,
        )
        _NOTICE_SHOWN = True


class ChatClaudeCode(BaseChatModel):
    model_name: str

    @property
    def _llm_type(self) -> str:
        return "claude-code-subscription"

    @property
    def _identifying_params(self) -> dict:
        return {"model_name": self.model_name}

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            TextBlock,
            query,
        )

        system_parts: List[str] = []
        user_parts: List[str] = []
        for m in messages:
            content = m.content if isinstance(m.content, str) else str(m.content)
            if isinstance(m, SystemMessage):
                system_parts.append(content)
            else:
                user_parts.append(content)

        system_prompt = "\n\n".join(p for p in system_parts if p) or None
        prompt = "\n\n".join(p for p in user_parts if p)

        options = ClaudeAgentOptions(
            model=self.model_name,
            system_prompt=system_prompt,
        )

        async def _collect() -> str:
            out: List[str] = []
            async for msg in query(prompt=prompt, options=options):
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            out.append(block.text)
            return "".join(out)

        _notice_once()

        try:
            asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                text = ex.submit(asyncio.run, _collect()).result()
        except RuntimeError:
            text = asyncio.run(_collect())

        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=text))]
        )
