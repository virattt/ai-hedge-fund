"""FundSpec — a fund's mandate as data, and the Fund that lives it.

The hierarchy mirrors a real shop (see VISION.md):

    FUND      = capital slices over STRATEGIES  (master risk on the netted book)
    STRATEGY  = a blend policy over MODELS      (a "pod")
    MODEL     = an alpha model -> Signal

Models come in two kinds, and the strategy's character follows from its
staff: a strategy of LLM investor AGENTS (Buffett, Munger, ...) is a
discretionary pod — its identity is who's on the desk; a strategy powered
by quant models (PEAD, ...) is a systematic pod — its identity is the edge
it harvests. Same spec shape, same engine slot; the kind is derived, never
declared.

Specs are data (a Loop-2 ground rule): a mandate is a serializable YAML/JSON
config. The wizard, a chat LLM, and the strategy generator all emit this same
format — nothing downstream ever needs to know who authored a fund.

A `Fund` is the living counterpart: the spec plus its models instantiated
once. Models are stateful (LLM prompt caches, PEAD earnings caches), so
they must be constructed per fund — never per cycle — for caches to survive
across cycles.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from v2.risk.limits import RiskLimits
from v2.signals import ALPHA_MODEL_REGISTRY
from v2.signals.base import AlphaModel


class ModelSpec(BaseModel):
    """One signal model in a strategy — an LLM agent or a quant model."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="key into ALPHA_MODEL_REGISTRY, e.g. 'buffett'")
    weight: float = Field(default=1.0, gt=0, description="blend weight")
    params: dict[str, Any] = Field(
        default_factory=dict, description="constructor kwargs for the model"
    )


class BlendPolicy(BaseModel):
    """How a strategy's model views combine into one sleeve."""

    model_config = ConfigDict(extra="forbid")

    method: Literal["conviction_weighted"] = "conviction_weighted"
    gross_target: float = Field(
        default=1.0, gt=0, description="desired sum of |weights| when views exist"
    )
    market_neutral: bool = Field(
        default=False,
        description="demean convictions cross-sectionally before scaling: long "
        "the best-liked names relative to the rest, short the least-liked — a "
        "dollar-neutral sleeve",
    )


class StrategySpec(BaseModel):
    """A strategy ("pod"): signal models plus the policy that blends them.

    `weight` is the fund's capital slice for this strategy, relative to its
    siblings (normalized at netting time — 2/2 means the same as 1/1). In a
    library file (v2/strategies/) it stays at the default; slices are a
    fund-assembly decision, not a property of the strategy itself.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    display_name: str | None = Field(
        default=None, description="human-facing name, e.g. 'Deep Value'"
    )
    weight: float = Field(default=1.0, gt=0)
    models: list[ModelSpec] = Field(min_length=1)
    blend: BlendPolicy = Field(default_factory=BlendPolicy)

    @property
    def title(self) -> str:
        """Display name, falling back to a title-cased slug."""
        return self.display_name or self.name.replace("-", " ").title()

    @property
    def model_weights(self) -> dict[str, float]:
        """model_name -> blend weight, as portfolio construction consumes it."""
        return {m.name: m.weight for m in self.models}


class FundSpec(BaseModel):
    """A fund's complete mandate. `extra='forbid'` everywhere: YAML typos
    fail loud at load time, not silently at trade time. `risk` is MASTER
    risk — applied to the netted book after all strategies are combined."""

    model_config = ConfigDict(extra="forbid")

    name: str
    universe: list[str] = Field(min_length=1)
    strategies: list[StrategySpec] = Field(min_length=1)
    risk: RiskLimits
    capital: float = Field(default=100_000.0, gt=0)
    rebalance: Literal["daily", "weekly", "monthly"] = Field(
        default="weekly",
        description="how often the fund re-runs its cycle — a mandate choice, "
        "not an engine constant: a fundamentals fund trades weekly, a "
        "news-driven fund daily. The backtester (and the future daemon) obey "
        "it; run_cycle itself never sees it.",
    )
    benchmark: str = Field(
        default="SPY",
        description="what the fund measures itself against; also the source "
        "of the backtest's trading-day grid",
    )

    @field_validator("benchmark")
    @classmethod
    def _uppercase_benchmark(cls, ticker: str) -> str:
        return ticker.upper()

    @field_validator("universe")
    @classmethod
    def _uppercase_unique(cls, tickers: list[str]) -> list[str]:
        upper = [t.upper() for t in tickers]
        duplicates = {t for t in upper if upper.count(t) > 1}
        if duplicates:
            raise ValueError(f"duplicate tickers in universe: {sorted(duplicates)}")
        return upper

    @field_validator("strategies")
    @classmethod
    def _unique_strategy_names(cls, strategies: list[StrategySpec]) -> list[StrategySpec]:
        names = [s.name for s in strategies]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            raise ValueError(f"duplicate strategy names: {sorted(duplicates)}")
        return strategies


def load_spec(path: str | Path) -> FundSpec:
    """Load a mandate from YAML. Validation errors carry the pydantic detail."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return FundSpec(**data)


def load_strategy(path: str | Path) -> StrategySpec:
    """Load one strategy (a library file under v2/strategies/) from YAML."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return StrategySpec(**data)


class Fund:
    """A living fund: its spec plus instantiated models, per strategy.

    Plain class, not pydantic — models hold state (LLM clients, prompt
    caches, per-ticker data caches) and are constructed exactly once here.
    A persona appearing in two strategies gets two instances; that's fine —
    the prompt cache is disk-keyed by prompt content and shared, so the
    second instance's calls are cache hits, not spend.

    The `models` override (strategy name -> instances) exists for tests to
    inject fakes; production callers let the registry build the staff.
    """

    def __init__(
        self,
        spec: FundSpec,
        models: dict[str, list[AlphaModel]] | None = None,
    ) -> None:
        self.spec = spec
        self.strategies: list[tuple[StrategySpec, list[AlphaModel]]] = []
        for strategy in spec.strategies:
            if models is not None:
                self.strategies.append((strategy, models[strategy.name]))
                continue
            staff = []
            for m in strategy.models:
                if m.name not in ALPHA_MODEL_REGISTRY:
                    raise ValueError(
                        f"unknown model {m.name!r} in strategy "
                        f"{strategy.name!r}; available: {sorted(ALPHA_MODEL_REGISTRY)}"
                    )
                staff.append(ALPHA_MODEL_REGISTRY[m.name](**m.params))
            self.strategies.append((strategy, staff))
