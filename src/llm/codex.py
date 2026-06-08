"""LangChain chat model that routes OpenAI/GPT calls through the local
Codex CLI (`codex exec`) — uses your ChatGPT subscription, no API key needed.

This shells out to `codex exec -m <model> -c model_reasoning_effort=<effort> -s read-only`
and reads the last message back via `--output-last-message`. The pattern
mirrors `claude-agent-sdk` for Claude: subscription auth, subprocess transport,
no OpenAI API billing required.

Used when `OPENAI_API_KEY` is not set. Requires the Codex CLI (>= 0.130.0)
on PATH and a successful `codex login`. Raises a clear error if either is
missing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, List, Optional

from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult


_NOTICE_SHOWN = False
_AUTH_FILE = Path.home() / ".codex" / "auth.json"

# Codex CLI accepts these reasoning_effort values via config. Anything outside
# this set is clamped to "high" with a one-time warning.
_VALID_EFFORTS = {"minimal", "low", "medium", "high", "xhigh", "max"}


def _notice_once() -> None:
    global _NOTICE_SHOWN
    if not _NOTICE_SHOWN:
        print(
            "[ai-hedge-fund] No OPENAI_API_KEY set — using Codex CLI "
            "subscription via `codex exec`.",
            file=sys.stderr,
        )
        _NOTICE_SHOWN = True


def _codex_path() -> str:
    """Resolve the codex executable, raising if it's not installed."""
    p = shutil.which("codex")
    if not p:
        raise RuntimeError(
            "Codex CLI not found on PATH. Install it from "
            "https://github.com/openai/codex and run `codex login`."
        )
    return p


def _check_logged_in() -> None:
    if not _AUTH_FILE.exists():
        raise RuntimeError(
            f"No Codex auth at {_AUTH_FILE}. Run `codex login` first."
        )


def _flatten_messages(messages: List[BaseMessage]) -> str:
    """Concatenate LangChain messages into a single plain prompt.

    Codex CLI's `exec` mode treats the first paragraph as task framing and
    expects a concrete action to follow. If we lead with a SystemMessage
    ("You are an analyst…"), Codex reads it as priming and asks for the
    actual task. Tested fix: **put the user content FIRST** so the
    actionable question is in the lead, then append system content as
    inline instructions at the end ("Answer style: …").
    """
    system_parts: List[str] = []
    user_parts: List[str] = []
    for m in messages:
        content = m.content if isinstance(m.content, str) else str(m.content)
        if not content:
            continue
        if isinstance(m, SystemMessage):
            system_parts.append(content.strip())
        else:
            user_parts.append(content.strip())
    system = "\n\n".join(system_parts).strip()
    user = "\n\n".join(user_parts).strip()
    if user and system:
        return f"{user}\n\nAnswer style: {system}"
    return user or system


class ChatCodex(BaseChatModel):
    """Routes OpenAI/GPT calls through the Codex CLI subscription.

    Defaults to `gpt-5.5` at `xhigh` reasoning effort. Override either:

        ChatCodex(model_name="gpt-5", effort="medium")
    """

    model_name: str = "gpt-5.5"
    effort: Optional[str] = "xhigh"
    timeout_seconds: int = 600  # 10 min — extra-high reasoning can be slow

    @property
    def _llm_type(self) -> str:
        return "codex-cli-subscription"

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
        _notice_once()
        codex_bin = _codex_path()
        _check_logged_in()

        prompt = _flatten_messages(messages)

        effort = (self.effort or "high").lower()
        if effort not in _VALID_EFFORTS:
            print(
                f"[ai-hedge-fund] WARN: unknown effort '{self.effort}'. "
                f"Falling back to 'high'. Valid: {sorted(_VALID_EFFORTS)}",
                file=sys.stderr,
            )
            effort = "high"

        # Write the last assistant message to a temp file, then read it back.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as tmp:
            out_path = Path(tmp.name)

        try:
            cmd = [
                codex_bin,
                "exec",
                "-m",
                self.model_name,
                "-c",
                f'model_reasoning_effort="{effort}"',
                "-s",
                "read-only",  # safest sandbox: model can't write to disk
                "-o",
                str(out_path),
                prompt,
            ]
            # Run from a temp directory so Codex doesn't snap into its
            # "what to work on in this repo?" coding-agent persona — we
            # want general-purpose LLM behavior, not a project assistant.
            with tempfile.TemporaryDirectory(prefix="codex-run-") as run_cwd:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.timeout_seconds,
                    cwd=run_cwd,
                )
            if proc.returncode != 0:
                stderr_tail = (proc.stderr or "")[-800:]
                raise RuntimeError(
                    f"codex exec failed (exit {proc.returncode}). "
                    f"stderr tail: {stderr_tail}"
                )

            if out_path.exists() and out_path.stat().st_size > 0:
                text = out_path.read_text(encoding="utf-8", errors="replace").strip()
            else:
                # Fall back to parsing stdout if --output-last-message didn't write
                text = (proc.stdout or "").strip()
                # Strip the banner Codex prints before the actual response
                # (the actual response is on its own line at the end)
                lines = text.splitlines()
                if "codex" in [l.strip() for l in lines]:
                    # Take everything after the last "codex" marker line
                    idx = max(
                        i for i, l in enumerate(lines) if l.strip() == "codex"
                    )
                    text = "\n".join(lines[idx + 1 :]).strip()

            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(content=text))]
            )
        finally:
            try:
                out_path.unlink()
            except OSError:
                pass
