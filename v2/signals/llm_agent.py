"""LLMAgent — base class for LLM investor agents (the second AlphaModel flavor).

An LLMAgent reasons over a point-in-time FundamentalsSnapshot in a persona's
voice and emits the same Signal every quant model does. The base class owns
all the machinery; a persona is just a name + a system prompt:

    class BuffettAgent(LLMAgent):
        @property
        def name(self) -> str:
            return "buffett"

        def get_system_prompt(self) -> str:
            return "You are Warren Buffett..."

Failure contract (locked decisions):
- Data-layer errors PROPAGATE (fail loud — a broken snapshot must never
  silently become a neutral view).
- LLM call/parse failures ABSTAIN: Signal(value=0.0, metadata.abstained=True).
- Every LLM decision persists its exact prompt + response (via PromptCache),
  and an unchanged snapshot never pays for a second LLM call.
"""

from __future__ import annotations

import logging

from v2.data.protocol import DataClient
from v2.features.snapshot import FundamentalsSnapshot, InsufficientData, build_snapshot
from v2.llm import AnthropicLLM, LLMClient, PromptCache, extract_json, prompt_key
from v2.models import Signal
from v2.signals.base import AlphaModel

logger = logging.getLogger(__name__)

# What the model must return; folded into Signal.value below.
_SIGNAL_TO_SIGN = {"bullish": 1.0, "neutral": 0.0, "bearish": -1.0}


class LLMAgent(AlphaModel):
    """Base for persona agents. Subclasses define `name` and `get_system_prompt`."""

    def __init__(
        self,
        llm: LLMClient | None = None,
        cache: PromptCache | None = None,
    ) -> None:
        self._llm = llm if llm is not None else AnthropicLLM()
        self._cache = cache if cache is not None else PromptCache()

    # ------------------------------------------------------------------
    # AlphaModel interface
    # ------------------------------------------------------------------

    def predict(self, ticker: str, date: str, data_client: DataClient) -> Signal:
        try:
            snapshot = self.build_snapshot(ticker, date, data_client)
        except InsufficientData as exc:
            return self._abstain(ticker, date, f"insufficient data: {exc}")
        # Any other data-layer exception (e.g. FDClientError) propagates.

        system = self.get_system_prompt()
        user = self.build_user_prompt(snapshot)
        key = prompt_key(self.name, self._llm.model, system, user)

        cached = self._cache.get(key)
        if cached is not None and "parsed" in cached:
            return self._to_signal(ticker, date, cached["parsed"], key, snapshot, cached=True)

        try:
            response = self._llm.complete(system, user)
        except Exception as exc:
            logger.warning("%s LLM call failed for %s@%s: %s", self.name, ticker, date, exc)
            return self._abstain(ticker, date, f"LLM call failed: {exc}")

        record = {
            "agent": self.name,
            "model": self._llm.model,
            "ticker": ticker,
            "as_of": date,
            "snapshot_hash": snapshot.content_hash,
            "system": system,
            "user": user,
            "response": response,
        }

        try:
            parsed = self._parse(response)
        except Exception as exc:
            # Persist the raw response even when unparseable — the debug trail.
            self._cache.put(key, {**record, "parse_error": str(exc)})
            logger.warning("%s parse failed for %s@%s: %s", self.name, ticker, date, exc)
            return self._abstain(ticker, date, f"parse failed: {exc}")

        self._cache.put(key, {**record, "parsed": parsed})
        return self._to_signal(ticker, date, parsed, key, snapshot, cached=False)

    # ------------------------------------------------------------------
    # Subclass surface
    # ------------------------------------------------------------------

    def get_system_prompt(self) -> str:
        """The persona — every subclass must define its voice."""
        raise NotImplementedError(f"{type(self).__name__} must define get_system_prompt()")

    def build_snapshot(self, ticker: str, date: str, data_client: DataClient) -> FundamentalsSnapshot:
        """What this persona is allowed to know. Default: the shared
        point-in-time fundamentals snapshot — right for value/quality
        personas. Override for personas that reason over different data
        (macro, news); when a second snapshot TYPE exists, extract the
        implicit interface (ticker/as_of/content_hash/render) into a
        Protocol — not before."""
        return build_snapshot(ticker, date, data_client)

    def build_user_prompt(self, snapshot: FundamentalsSnapshot) -> str:
        """Default user prompt: the rendered snapshot. Override to enrich."""
        return snapshot.render()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse(self, response: str) -> dict:
        """Extract + validate {signal, confidence, reasoning}."""
        data = extract_json(response)
        signal = str(data.get("signal", "")).lower()
        if signal not in _SIGNAL_TO_SIGN:
            raise ValueError(f"invalid signal {data.get('signal')!r}")
        confidence = float(data.get("confidence", 0))
        if not 0 <= confidence <= 100:
            raise ValueError(f"confidence out of range: {confidence}")
        return {
            "signal": signal,
            "confidence": confidence,
            "reasoning": str(data.get("reasoning", "")),
        }

    def _to_signal(
        self,
        ticker: str,
        date: str,
        parsed: dict,
        key: str,
        snapshot: FundamentalsSnapshot,
        cached: bool,
    ) -> Signal:
        value = _SIGNAL_TO_SIGN[parsed["signal"]] * parsed["confidence"] / 100.0
        return Signal(
            model_name=self.name,
            ticker=ticker,
            date=date,
            value=value,
            reasoning=parsed["reasoning"],
            metadata={
                "signal": parsed["signal"],
                "confidence": parsed["confidence"],
                "model": self._llm.model,
                "prompt_key": key,
                "snapshot_hash": snapshot.content_hash,
                "cached": cached,
                "abstained": False,
            },
        )

    def _abstain(self, ticker: str, date: str, reason: str) -> Signal:
        return Signal(
            model_name=self.name,
            ticker=ticker,
            date=date,
            value=0.0,
            reasoning=f"abstained: {reason}",
            metadata={"abstained": True, "abstain_reason": reason, "cached": False},
        )
