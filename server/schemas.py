"""Pydantic request / response schemas for the FastAPI server.

Mirrors the shapes returned by ``src.main.run_hedge_fund`` (`src/main.py:96-99`)
and the per-agent signal contract documented in the plan at §B2 / B3.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Reference data (GET /analysts, GET /models)
# ---------------------------------------------------------------------------


class AnalystInfo(BaseModel):
    """An analyst (e.g. ``warren_buffett``)."""

    key: str
    display_name: str
    order: int


class ModelInfo(BaseModel):
    """An LLM model option."""

    model_config = ConfigDict(protected_namespaces=())

    display_name: str
    model_name: str
    provider: str


# ---------------------------------------------------------------------------
# Analyze run (POST /runs)
# ---------------------------------------------------------------------------


_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class PortfolioPosition(BaseModel):
    long: float = 0.0
    short: float = 0.0
    long_cost_basis: float = 0.0
    short_cost_basis: float = 0.0


class Portfolio(BaseModel):
    cash: float = 100_000.0
    margin_requirement: float = 0.0
    positions: dict[str, PortfolioPosition] = Field(default_factory=dict)
    realized_gains: dict[str, float] = Field(default_factory=dict)


class AnalyzeRequest(BaseModel):
    """Input contract for ``POST /api/runs``.

    Mirrors the kwargs of ``run_hedge_fund`` (`src/main.py:53-62`).
    """

    tickers: list[str] = Field(..., min_length=1, max_length=20)
    start_date: str | None = None
    end_date: str | None = None
    portfolio: Portfolio = Field(default_factory=Portfolio)
    show_reasoning: bool = False
    selected_analysts: list[str] = Field(default_factory=list)
    model_name: str = "gpt-4o"
    model_provider: str = "OpenAI"

    @field_validator("tickers")
    @classmethod
    def _validate_tickers(cls, tickers: list[str]) -> list[str]:
        # A3: regex-validate ticker format. Resolves the prompt-injection vector
        # noted at `src/main.py:172`.
        cleaned: list[str] = []
        for raw in tickers:
            t = raw.strip().upper()
            if not _TICKER_RE.fullmatch(t):
                raise ValueError(f"invalid ticker symbol: {raw!r}")
            cleaned.append(t)
        return cleaned

    @field_validator("start_date", "end_date")
    @classmethod
    def _validate_dates(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _DATE_RE.fullmatch(value):
            raise ValueError("date must be YYYY-MM-DD")
        # Validates calendar reality (e.g. no Feb 30).
        datetime.strptime(value, "%Y-%m-%d")
        return value

    @model_validator(mode="after")
    def _default_dates_and_check_order(self) -> AnalyzeRequest:
        end = self.end_date or datetime.now(UTC).strftime("%Y-%m-%d")
        start = self.start_date or (datetime.strptime(end, "%Y-%m-%d") - timedelta(days=90)).strftime("%Y-%m-%d")

        if start > end:
            raise ValueError("start_date must not be after end_date")

        # Persist canonicalized values back.
        object.__setattr__(self, "start_date", start)
        object.__setattr__(self, "end_date", end)
        return self


class Decision(BaseModel):
    """Final per-ticker decision from the portfolio manager."""

    action: Literal["buy", "sell", "short", "cover", "hold"]
    quantity: int
    confidence: float = Field(..., ge=0, le=100)
    reasoning: str | None = None


class AnalystSignal(BaseModel):
    """A single analyst's per-ticker output."""

    signal: Literal["bullish", "bearish", "neutral"] | None = None
    confidence: float | None = None
    reasoning: str | dict[str, Any] | None = None
    # For risk_management_agent.
    remaining_position_limit: float | None = None
    current_price: float | None = None


class RunSummary(BaseModel):
    """Output contract for ``POST /api/runs`` (sync) and ``GET /api/runs/{id}``."""

    id: str
    status: Literal["running", "done", "error"]
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    error_message: str | None = None
    cost_usd: float | None = None
    config: AnalyzeRequest
    decisions: dict[str, Decision] = Field(default_factory=dict)
    analyst_signals: dict[str, dict[str, AnalystSignal]] = Field(default_factory=dict)


class RunListItem(BaseModel):
    id: str
    status: Literal["running", "done", "error"]
    kind: Literal["analyze", "backtest"]
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    tickers: list[str]
    model_name: str
    model_provider: str


class RunListResponse(BaseModel):
    items: list[RunListItem]
    next_cursor: str | None = None


# ---------------------------------------------------------------------------
# Backtest (POST /api/backtests/stream)
# ---------------------------------------------------------------------------


class BacktestRequest(BaseModel):
    """Input contract for ``POST /api/backtests/stream``."""

    tickers: list[str] = Field(..., min_length=1, max_length=20)
    start_date: str
    end_date: str
    initial_cash: float = 100_000.0
    margin_requirement: float = 0.0
    selected_analysts: list[str] = Field(default_factory=list)
    model_name: str = "gpt-4o"
    model_provider: str = "OpenAI"

    @field_validator("tickers")
    @classmethod
    def _validate_bt_tickers(cls, tickers: list[str]) -> list[str]:
        cleaned: list[str] = []
        for raw in tickers:
            t = raw.strip().upper()
            if not _TICKER_RE.fullmatch(t):
                raise ValueError(f"invalid ticker symbol: {raw!r}")
            cleaned.append(t)
        return cleaned

    @field_validator("start_date", "end_date")
    @classmethod
    def _validate_bt_dates(cls, value: str) -> str:
        if not _DATE_RE.fullmatch(value):
            raise ValueError("date must be YYYY-MM-DD")
        datetime.strptime(value, "%Y-%m-%d")
        return value


# ---------------------------------------------------------------------------
# Ticker endpoints (F4a)
# ---------------------------------------------------------------------------


class FinancialMetricsResponse(BaseModel):
    """Response for ``GET /api/tickers/{symbol}/financial-metrics``."""

    financial_metrics: list[dict[str, Any]]


class InsiderTradesResponse(BaseModel):
    """Response for ``GET /api/tickers/{symbol}/insider-trades``."""

    insider_trades: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    providers_configured: dict[str, bool]
    db_ok: bool
