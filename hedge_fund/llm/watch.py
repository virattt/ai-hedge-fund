"""Reading an agent's answer while it is still being written.

Agents answer in JSON — `{"signal", "confidence", "reasoning"}`, in that
order — because that is what parses reliably. Streamed raw, that is a brace
and a half-typed key: unreadable. `ThesisStream` decodes the fields that have
fully arrived and the thesis as far as it has been written, so a live view can
show the call the moment it lands and let the prose type itself out after.

Read-only and best-effort by construction. It never replaces the real parse
(`LLMAgent._parse`), which runs on the complete response and is the only thing
a Signal is built from. If a model answers in some other shape, every field
here simply stays empty and the run is unaffected.
"""

from __future__ import annotations

import re

# Both patterns require the value's terminator, so a half-written number never
# shows as a smaller one ("confidence": 7 becoming 78 a chunk later).
_SIGNAL_RE = re.compile(r'"signal"\s*:\s*"([A-Za-z]+)"')
_CONFIDENCE_RE = re.compile(r'"confidence"\s*:\s*(-?\d+(?:\.\d+)?)\s*[,}]')
_REASONING_RE = re.compile(r'"reasoning"\s*:\s*"')

_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "b": "\b",
            "f": "\f", "n": "\n", "r": "\r", "t": "\t"}


class ThesisStream:
    """An agent's answer, decoded as far as it has arrived.

    Feed it the text an LLM client streams; read `signal`, `confidence`, and
    `thesis` at any point. Chunk boundaries are irrelevant — the decode runs
    over everything received so far, so a field split across two chunks
    resolves as soon as its last character lands.
    """

    def __init__(self) -> None:
        self._buf = ""
        self.signal: str | None = None
        self.confidence: float | None = None
        self.thesis: str = ""

    def feed(self, text: str) -> None:
        self._buf += text
        signal = _SIGNAL_RE.search(self._buf)
        if signal:
            self.signal = signal.group(1).lower()
        confidence = _CONFIDENCE_RE.search(self._buf)
        if confidence:
            self.confidence = float(confidence.group(1))
        reasoning = _REASONING_RE.search(self._buf)
        if reasoning:
            self.thesis = _partial_string(self._buf, reasoning.end())

    def verdict(self) -> str | None:
        """The call so far — "BULLISH 78%" — or None until it is decodable.
        The confidence appears only once it is final, so this never counts up.
        """
        if self.signal is None:
            return None
        if self.confidence is None:
            return self.signal.upper()
        return f"{self.signal.upper()} {self.confidence:.0f}%"


def _partial_string(buf: str, start: int) -> str:
    """The JSON string body at *start*, decoded as far as it is written.

    Stops at the closing quote, at the end of the buffer, or just before an
    escape sequence that has not fully arrived — a lone trailing backslash is
    not yet a character, and guessing at one would print the wrong glyph for a
    frame.
    """
    out: list[str] = []
    i, n = start, len(buf)
    while i < n:
        char = buf[i]
        if char == '"':
            break
        if char != "\\":
            out.append(char)
            i += 1
            continue
        if i + 1 >= n:
            break
        escape = buf[i + 1]
        if escape == "u":
            if i + 6 > n:
                break
            try:
                out.append(chr(int(buf[i + 2:i + 6], 16)))
            except ValueError:
                break  # malformed — the real parse will report it
            i += 6
            continue
        out.append(_ESCAPES.get(escape, escape))
        i += 2
    return "".join(out)
