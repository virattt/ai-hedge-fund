"""FundSpec — a fund's mandate as data, and the Fund that lives it.

Specs are data (a Loop-2 ground rule): a mandate is a serializable YAML/JSON
config — universe, analysts, blend policy, risk limits, capital. Humans write
these files today; the strategy generator will emit the same specs later, so
nothing downstream ever needs to know who authored a fund.

A `Fund` is the living counterpart: the spec plus its analysts instantiated
once. Analysts are stateful (LLM prompt caches, PEAD earnings caches), so
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


class AnalystSpec(BaseModel):
    """One analyst on the fund's staff."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="key into ALPHA_MODEL_REGISTRY, e.g. 'buffett'")
    weight: float = Field(default=1.0, gt=0, description="blend weight")
    params: dict[str, Any] = Field(
        default_factory=dict, description="constructor kwargs for the model"
    )


class BlendPolicy(BaseModel):
    """How analyst views combine into one book."""

    model_config = ConfigDict(extra="forbid")

    method: Literal["conviction_weighted"] = "conviction_weighted"
    gross_target: float = Field(
        default=1.0, gt=0, description="desired sum of |weights| when views exist"
    )


class FundSpec(BaseModel):
    """A fund's complete mandate. `extra='forbid'` everywhere: YAML typos
    fail loud at load time, not silently at trade time."""

    model_config = ConfigDict(extra="forbid")

    name: str
    universe: list[str] = Field(min_length=1)
    analysts: list[AnalystSpec] = Field(min_length=1)
    blend: BlendPolicy = Field(default_factory=BlendPolicy)
    risk: RiskLimits
    capital: float = Field(default=100_000.0, gt=0)

    @field_validator("universe")
    @classmethod
    def _uppercase_unique(cls, tickers: list[str]) -> list[str]:
        upper = [t.upper() for t in tickers]
        duplicates = {t for t in upper if upper.count(t) > 1}
        if duplicates:
            raise ValueError(f"duplicate tickers in universe: {sorted(duplicates)}")
        return upper


def load_spec(path: str | Path) -> FundSpec:
    """Load a mandate from YAML. Validation errors carry the pydantic detail."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return FundSpec(**data)


class Fund:
    """A living fund: its spec plus instantiated analysts.

    Plain class, not pydantic — analysts hold state (LLM clients, prompt
    caches, per-ticker data caches) and are constructed exactly once here.
    The `analysts` override exists for tests to inject fakes; production
    callers let the registry build the staff.
    """

    def __init__(self, spec: FundSpec, analysts: list[AlphaModel] | None = None) -> None:
        self.spec = spec
        if analysts is not None:
            self.analysts = analysts
        else:
            self.analysts = []
            for a in spec.analysts:
                if a.name not in ALPHA_MODEL_REGISTRY:
                    raise ValueError(
                        f"unknown analyst {a.name!r}; available: "
                        f"{sorted(ALPHA_MODEL_REGISTRY)}"
                    )
                self.analysts.append(ALPHA_MODEL_REGISTRY[a.name](**a.params))

    @property
    def analyst_weights(self) -> dict[str, float]:
        """model_name -> blend weight, as portfolio construction consumes it."""
        return {a.name: a.weight for a in self.spec.analysts}
