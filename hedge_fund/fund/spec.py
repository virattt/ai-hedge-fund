"""Validated fund configurations, strategy composition, and model construction."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, TypeAlias

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_serializer,
    model_validator,
    ValidationError,
)

from hedge_fund.brokers.costs import TradingCosts
from hedge_fund.risk.limits import RiskLimits
from hedge_fund.signals import ALPHA_MODEL_REGISTRY, LLMAgent, get_investment_approach
from hedge_fund.signals.base import AlphaModel

PortfolioMode: TypeAlias = Literal["long_only", "long_short", "dollar_neutral"]
Cadence: TypeAlias = Literal["minute", "daily", "weekly", "monthly"]

# The shortest interval a minute fund may run at: a session key is stamped
# to the second, so one second is the finest bar there is. A snapshot round
# trip is about a second per name, so at the fastest settings the runner
# will miss bars (logged as gaps) rather than fall behind its clock.
MIN_INTERVAL_SECONDS = 1

# US extended hours: the earliest and latest a trading window may reach.
EARLIEST_WINDOW = "04:00"
LATEST_WINDOW = "20:00"


def _clock_seconds(hhmm: str) -> int:
    """Seconds since midnight for an HH:MM string; ValueError otherwise."""
    try:
        hours, minutes = hhmm.split(":")
        h, m = int(hours), int(minutes)
    except (AttributeError, ValueError):
        raise ValueError(f"{hhmm!r} is not a time of day (HH:MM)") from None
    if not (0 <= h < 24 and 0 <= m < 60 and len(hours) == 2 and len(minutes) == 2):
        raise ValueError(f"{hhmm!r} is not a time of day (HH:MM)")
    return h * 3600 + m * 60


class TradingWindow(BaseModel):
    """When a minute fund trades, in New York time. Both ends are sessions:
    the window opens with a bar at `start` and always closes with one at `end`."""

    model_config = ConfigDict(extra="forbid")

    start: str = "09:30"
    end: str = "16:00"

    @field_validator("start", "end")
    @classmethod
    def _within_extended_hours(cls, value: str) -> str:
        seconds = _clock_seconds(value)
        if not _clock_seconds(EARLIEST_WINDOW) <= seconds <= _clock_seconds(LATEST_WINDOW):
            raise ValueError(f"{value} is outside US extended hours ({EARLIEST_WINDOW}–{LATEST_WINDOW} ET)")
        return value

    @model_validator(mode="after")
    def _opens_before_it_closes(self) -> TradingWindow:
        if self.start_seconds >= self.end_seconds:
            raise ValueError(f"window must open before it closes ({self.start}–{self.end} ET)")
        return self

    @property
    def start_seconds(self) -> int:
        return _clock_seconds(self.start)

    @property
    def end_seconds(self) -> int:
        return _clock_seconds(self.end)

    @property
    def label(self) -> str:
        return f"{self.start}–{self.end} ET"


class ModelSpec(BaseModel):
    """One signal model in a strategy — an LLM agent or a quant model."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="key into ALPHA_MODEL_REGISTRY, e.g. 'buffett'")
    weight: float = Field(default=1.0, gt=0, description="blend weight")
    params: dict[str, Any] = Field(default_factory=dict, description="constructor kwargs for the model")

    @field_validator("name")
    @classmethod
    def _declared_approach(cls, name: str) -> str:
        get_investment_approach(name)
        return name


class BlendPolicy(BaseModel):
    """How a strategy's model views combine into one sleeve."""

    model_config = ConfigDict(extra="forbid")

    method: Literal["conviction_weighted"] = "conviction_weighted"
    gross_target: float = Field(default=1.0, gt=0, description="desired sum of |weights| when views exist")
    mode: PortfolioMode


class StrategySpec(BaseModel):
    """A strategy ("pod"): signal models plus the policy that blends them.

    `weight` is the fund's capital slice for this strategy, relative to its
    siblings (normalized at netting time — 2/2 means the same as 1/1). In a
    library file (hedge_fund/strategies/) it stays at the default; slices are a
    fund-assembly decision, not a property of the strategy itself.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    display_name: str | None = Field(default=None, description="human-facing name, e.g. 'Deep Value'")
    weight: float = Field(default=1.0, gt=0)
    models: list[ModelSpec] = Field(min_length=1)
    blend: BlendPolicy

    @property
    def title(self) -> str:
        """Display name, falling back to a title-cased slug."""
        return self.display_name or self.name.replace("-", " ").title()

    @property
    def model_weights(self) -> dict[str, float]:
        """model_name -> blend weight, as portfolio construction consumes it."""
        return {m.name: m.weight for m in self.models}


class FundSpec(BaseModel):
    """A mandate with fund-level risk limits and no fixed ticker universe.

    Unknown fields are rejected. Risk limits apply to the combined portfolio;
    the ticker universe is supplied separately for each run.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2]
    name: str
    strategies: list[StrategySpec] = Field(min_length=1)
    risk: RiskLimits
    costs: TradingCosts = Field(
        default_factory=TradingCosts,
        description="what every fill costs: half-spread per side and commission per share",
    )
    capital: float = Field(default=100_000.0, gt=0)
    rebalance: Cadence = Field(
        default="weekly",
        description="how often the fund decides: every bar (minute), or the first session of each day/week/month",
    )
    interval: float = Field(
        default=1.0, gt=0,
        description="minutes between sessions; read only when rebalance is minute",
    )
    window: TradingWindow = Field(
        default_factory=TradingWindow,
        description="trading hours in New York time; read only when rebalance is minute",
    )
    benchmark: str = Field(
        default="SPY",
        description="what the fund measures itself against; also the source " "of the backtest's trading-day grid",
    )

    @field_validator("benchmark")
    @classmethod
    def _uppercase_benchmark(cls, ticker: str) -> str:
        return ticker.upper()

    @field_validator("strategies")
    @classmethod
    def _unique_strategy_names(cls, strategies: list[StrategySpec]) -> list[StrategySpec]:
        names = [s.name for s in strategies]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            raise ValueError(f"duplicate strategy names: {sorted(duplicates)}")
        return strategies

    @model_validator(mode="after")
    def _interval_and_window_belong_to_minute_funds(self) -> FundSpec:
        if self.rebalance != "minute":
            stray = sorted({"interval", "window"} & self.model_fields_set)
            if stray:
                raise ValueError(f"{', '.join(stray)}: only a minute fund has these; this one is {self.rebalance}")
            return self
        if self.interval_seconds < MIN_INTERVAL_SECONDS:
            raise ValueError(
                f"interval: floor is {MIN_INTERVAL_SECONDS} second — sessions are stamped to the second"
            )
        if self.interval_seconds > self.window.end_seconds - self.window.start_seconds:
            raise ValueError(
                f"interval: {format_interval(self.interval_seconds)} is longer than the {self.window.label} window"
            )
        return self

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        """Daily/weekly/monthly mandates serialize exactly as they did before
        minute funds existed: `interval` and `window` mean nothing to them,
        and every ledger record carries a serialized spec in its hash. For
        the same reason a mandate at the default costs serializes without a
        `costs` block, as every mandate did before costs existed."""
        data = handler(self)
        if self.rebalance != "minute":
            data.pop("interval", None)
            data.pop("window", None)
        if self.costs == TradingCosts():
            data.pop("costs", None)
        return data

    @property
    def is_intraday(self) -> bool:
        return self.rebalance == "minute"

    @property
    def interval_seconds(self) -> int:
        """The bar length, to the second. Only meaningful for a minute fund."""
        return int(round(self.interval * 60))

    @property
    def cadence_label(self) -> str:
        """How the cadence reads: `daily`, or `every 30s` / `every 5m` / `every 1h30m`."""
        if not self.is_intraday:
            return self.rebalance
        return f"every {format_interval(self.interval_seconds)}"


def format_interval(seconds: int) -> str:
    """`30s`, `5m`, `1h`, `1h30m`, `2m30s` — the shortest honest spelling."""
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if seconds < 60:
        return f"{secs}s"
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs:
        parts.append(f"{secs}s")
    return "".join(parts)


def normalize_universe(tickers: list[str]) -> list[str]:
    """Strip, uppercase, and deduplicate tickers while preserving their order.

    Raise ValueError if no nonempty tickers remain.
    """
    universe: list[str] = []
    for ticker in tickers:
        upper = ticker.strip().upper()
        if upper and upper not in universe:
            universe.append(upper)
    if not universe:
        raise ValueError("universe is empty — a run needs at least one ticker")
    return universe


def load_spec(path: str | Path) -> FundSpec:
    """Load a YAML mandate, raising ValueError with its path and error details."""
    data = _read_yaml(path)
    if "schema_version" not in data:
        raise ValueError(f"{path}: schema_version: This fund uses an older format. " "Recreate it or update its configuration.")
    try:
        return FundSpec.model_validate(data)
    except ValidationError as exc:
        raise ValueError(_validation_message(path, exc)) from exc


def load_strategy(path: str | Path) -> StrategySpec:
    """Load one strategy (a library file under hedge_fund/strategies/) from YAML."""
    try:
        return StrategySpec.model_validate(_read_yaml(path))
    except ValidationError as exc:
        raise ValueError(_validation_message(path, exc)) from exc


def _validation_message(path: str | Path, exc: ValidationError) -> str:
    errors = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
    return f"{path}: {errors}"


def _read_yaml(path: str | Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(Path(path).read_text())
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f"{path}: cannot read configuration: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: configuration must be a YAML mapping")
    return data


def custom_strategy(names: list[str]) -> StrategySpec:
    """Build a strategy with its mode derived from registered analyst profiles.

    Duplicate names are removed in selection order. Any analyst that permits
    shorting enables long/short mode; dollar neutrality is never inferred.
    Invalid or empty selections raise ValueError.
    """
    models = [ModelSpec(name=n) for n in dict.fromkeys(names)]
    mode: PortfolioMode = "long_short" if any(get_investment_approach(m.name) == "long_short" for m in models) else "long_only"
    return StrategySpec(name="custom", models=models, blend=BlendPolicy(mode=mode))


class Fund:
    """A validated mandate with persistent model instances for each strategy.

    Models are constructed once so their caches survive successive cycles.
    Callers may supply instances keyed by strategy name, including test doubles.

    `blind=True` is for backtests: the LLM agents render prompts without
    the ticker, industry or calendar dates, so the result can't lean on
    what the model remembers about the company. Quant models are unaffected.
    """

    def __init__(
        self,
        spec: FundSpec,
        models: dict[str, list[AlphaModel]] | None = None,
        blind: bool = False,
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
                    raise ValueError(f"unknown model {m.name!r} in strategy " f"{strategy.name!r}; available: {sorted(ALPHA_MODEL_REGISTRY)}")
                cls = ALPHA_MODEL_REGISTRY[m.name]
                params = {**m.params, "blind": True} if blind and issubclass(cls, LLMAgent) else m.params
                staff.append(cls(**params))
            self.strategies.append((strategy, staff))
