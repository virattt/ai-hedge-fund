"""LLMAgent — base class for LLM investor agents (the second AlphaModel flavor).

An LLMAgent reasons over a point-in-time snapshot (fundamentals by default) in a persona's
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
from typing import Protocol

from hedge_fund.data.protocol import DataClient
from hedge_fund.features.snapshot import InsufficientData, build_snapshot
from hedge_fund.llm import LLMCallError, LLMClient, PromptCache, extract_json, make_llm, prompt_key
from hedge_fund.models import Signal
from hedge_fund.signals.base import AlphaModel

logger = logging.getLogger(__name__)

# What the model must return; folded into Signal.value below.
_SIGNAL_TO_SIGN = {"bullish": 1.0, "neutral": 0.0, "bearish": -1.0}


class Snapshot(Protocol):
    """What an LLMAgent needs from any snapshot type (fundamentals, news, ...)."""

    ticker: str
    as_of: str

    @property
    def content_hash(self) -> str: ...

    def render(self) -> str: ...


class LLMAgent(AlphaModel):
    """Base for persona agents. Subclasses define `name` and `get_system_prompt`."""

    def __init__(
        self,
        llm: LLMClient | None = None,
        cache: PromptCache | None = None,
        blind: bool = False,
    ) -> None:
        self._llm = llm if llm is not None else make_llm()
        self._cache = cache if cache is not None else PromptCache()
        # Blind prompts withhold the ticker, industry and calendar dates so a
        # backtest can't lean on what the LLM remembers about the company
        # (FundamentalsSnapshot.render). Backtests set this; live runs don't.
        self._blind = blind

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
        cache_key = getattr(self._llm, "cache_key", None)
        key = (cache_key(self.name, system, user) if callable(cache_key)
               else prompt_key(self.name, self._llm.model, system, user))

        cached = self._cache.get(key)
        if cached is not None and "parsed" in cached:
            return self._to_signal(ticker, date, cached["parsed"], key, snapshot, cached=True)

        record = {
            "agent": self.name,
            "model": self._llm.model,
            "ticker": ticker,
            "as_of": date,
            "snapshot_hash": snapshot.content_hash,
            "system": system,
            "user": user,
        }

        try:
            response = self._llm.complete(system, user)
        except Exception as exc:
            if isinstance(exc, LLMCallError) and exc.diagnostic_record is not None:
                self._cache.put(key, {**record, "call_error": str(exc),
                                      "diagnostics": exc.diagnostic_record})
                signal = self._abstain(ticker, date, f"LLM call failed: {exc}")
                signal.metadata["prompt_key"] = key
            else:
                signal = self._abstain(ticker, date, f"LLM call failed: {exc}")
            logger.warning("%s LLM call failed for %s@%s: %s", self.name, ticker, date, exc)
            return signal

        record["response"] = response
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

    def build_snapshot(self, ticker: str, date: str, data_client: DataClient) -> Snapshot:
        """What this persona is allowed to know. Default: the shared
        point-in-time fundamentals snapshot — right for value/quality
        personas. Override for personas that reason over different data
        (see NewsAnalystAgent); any object satisfying `Snapshot` works."""
        return build_snapshot(ticker, date, data_client)

    def build_user_prompt(self, snapshot: Snapshot) -> str:
        """Default user prompt: the rendered snapshot. Override to enrich."""
        return snapshot.render(blind=self._blind)

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
        parsed = {
            "signal": signal,
            "confidence": confidence,
            "reasoning": str(data.get("reasoning", "")),
        }
        if "provider_metadata" in data:
            if not isinstance(data["provider_metadata"], dict):
                raise ValueError("provider_metadata must be an object")
            parsed["provider_metadata"] = data["provider_metadata"]
        return parsed

    def _to_signal(
        self,
        ticker: str,
        date: str,
        parsed: dict,
        key: str,
        snapshot: Snapshot,
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
                **({"provider_metadata": parsed["provider_metadata"]}
                   if "provider_metadata" in parsed else {}),
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
