import ipaddress
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator
from src.llm.models import ModelProvider
from app.backend.services.graph import extract_base_agent_key


class FlowRunStatus(str, Enum):
    IDLE = "IDLE"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"


class AgentModelConfig(BaseModel):
    agent_id: str
    model_name: str | None = None
    model_provider: ModelProvider | None = None


@dataclass
class AgentModelSelection:
    """Resolved model name and provider for a specific agent."""
    model_name: str
    model_provider: ModelProvider


class PortfolioPosition(BaseModel):
    ticker: str
    quantity: float
    trade_price: float

    @field_validator('trade_price')
    @classmethod
    def price_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError('Trade price must be positive!')
        return v


class GraphNode(BaseModel):
    id: str
    type: str | None = None
    data: dict | None = None
    position: dict | None = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str | None = None
    data: dict | None = None


class HedgeFundResponse(BaseModel):
    decisions: dict
    analyst_signals: dict


class ErrorResponse(BaseModel):
    message: str
    error: str | None = None


# Base class for shared fields between HedgeFundRequest and BacktestRequest
class BaseHedgeFundRequest(BaseModel):
    tickers: list[str]
    graph_nodes: list[GraphNode]
    graph_edges: list[GraphEdge]
    agent_models: list[AgentModelConfig] | None = None
    model_name: str | None = "gpt-4.1"
    model_provider: ModelProvider | None = ModelProvider.OPENAI
    margin_requirement: float = 0.0
    portfolio_positions: list[PortfolioPosition] | None = None
    api_keys: dict[str, str] | None = None

    def get_agent_ids(self) -> list[str]:
        """Extract agent IDs from graph structure"""
        return [node.id for node in self.graph_nodes]

    def get_agent_model_config(self, agent_id: str) -> AgentModelSelection:
        """Get model configuration for a specific agent"""
        if self.agent_models:
            # Extract base agent key from unique node ID for matching
            base_agent_key = extract_base_agent_key(agent_id)

            for config in self.agent_models:
                # Check both unique node ID and base agent key for matches
                config_base_key = extract_base_agent_key(config.agent_id)
                if config.agent_id == agent_id or config_base_key == base_agent_key:
                    return AgentModelSelection(
                        model_name=config.model_name or self.model_name,
                        model_provider=config.model_provider or self.model_provider,
                    )
        # Fallback to global model settings
        return AgentModelSelection(
            model_name=self.model_name,
            model_provider=self.model_provider,
        )


class BacktestRequest(BaseHedgeFundRequest):
    start_date: str
    end_date: str
    initial_capital: float = 100000.0


class BacktestDayResult(BaseModel):
    date: str
    portfolio_value: float
    cash: float
    decisions: dict
    executed_trades: dict[str, int]
    analyst_signals: dict
    current_prices: dict[str, float]
    long_exposure: float
    short_exposure: float
    gross_exposure: float
    net_exposure: float
    long_short_ratio: float | None = None


class BacktestPerformanceMetrics(BaseModel):
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    max_drawdown: float | None = None
    max_drawdown_date: str | None = None
    long_short_ratio: float | None = None
    gross_exposure: float | None = None
    net_exposure: float | None = None


class BacktestResponse(BaseModel):
    results: list[BacktestDayResult]
    performance_metrics: BacktestPerformanceMetrics
    final_portfolio: dict


class HedgeFundRequest(BaseHedgeFundRequest):
    end_date: str | None = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    start_date: str | None = None
    initial_cash: float = 100000.0

    def get_start_date(self) -> str:
        """Calculate start date if not provided"""
        if self.start_date:
            return self.start_date
        return (datetime.strptime(self.end_date, "%Y-%m-%d") - timedelta(days=90)).strftime("%Y-%m-%d")


# Flow-related schemas
class FlowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    nodes: list[dict]
    edges: list[dict]
    viewport: dict | None = None
    data: dict | None = None
    is_template: bool = False
    tags: list[str] | None = None


class FlowUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    nodes: list[dict] | None = None
    edges: list[dict] | None = None
    viewport: dict | None = None
    data: dict | None = None
    is_template: bool | None = None
    tags: list[str] | None = None


class FlowResponse(BaseModel):
    id: int
    name: str
    description: str | None
    nodes: list[dict]
    edges: list[dict]
    viewport: dict | None
    data: dict | None
    is_template: bool
    tags: list[str] | None
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class FlowSummaryResponse(BaseModel):
    """Lightweight flow response without nodes/edges for listing"""
    id: int
    name: str
    description: str | None
    is_template: bool
    tags: list[str] | None
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


# Flow Run schemas
class FlowRunCreateRequest(BaseModel):
    """Request to create a new flow run"""
    request_data: dict | None = None


class FlowRunUpdateRequest(BaseModel):
    """Request to update an existing flow run"""
    status: FlowRunStatus | None = None
    results: dict | None = None
    error_message: str | None = None


class FlowRunResponse(BaseModel):
    """Complete flow run response"""
    id: int
    flow_id: int
    status: FlowRunStatus
    run_number: int
    created_at: datetime
    updated_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    request_data: dict | None
    results: dict | None
    error_message: str | None

    class Config:
        from_attributes = True


class FlowRunSummaryResponse(BaseModel):
    """Lightweight flow run response for listing"""
    id: int
    flow_id: int
    status: FlowRunStatus
    run_number: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None

    class Config:
        from_attributes = True


# API Key schemas
class ApiKeyCreateRequest(BaseModel):
    """Request to create or update an API key"""
    provider: str = Field(..., min_length=1, max_length=100)
    key_value: str = Field(..., min_length=1)
    description: str | None = None
    is_active: bool = True


class ApiKeyUpdateRequest(BaseModel):
    """Request to update an existing API key"""
    key_value: str | None = Field(None, min_length=1)
    description: str | None = None
    is_active: bool | None = None


class ApiKeyResponse(BaseModel):
    """Complete API key response"""
    id: int
    provider: str
    key_value: str
    is_active: bool
    description: str | None
    created_at: datetime
    updated_at: datetime | None
    last_used: datetime | None

    class Config:
        from_attributes = True


class ApiKeySummaryResponse(BaseModel):
    """API key response without the actual key value"""
    id: int
    provider: str
    is_active: bool
    description: str | None
    created_at: datetime
    updated_at: datetime | None
    last_used: datetime | None
    has_key: bool = True  # Indicates if a key is set

    class Config:
        from_attributes = True


class ApiKeyBulkUpdateRequest(BaseModel):
    """Request to update multiple API keys at once"""
    api_keys: list[ApiKeyCreateRequest]


# ---------------------------------------------------------------------------
# Scraping enums
# ---------------------------------------------------------------------------


class ScrapeStatus(str, Enum):
    """Status values for a scraping website."""
    IDLE = "idle"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"


class ScrapeResultStatus(str, Enum):
    """Status values for an individual scrape result."""
    SUCCESS = "success"
    ERROR = "error"


# ---------------------------------------------------------------------------
# SSRF validation helper
# ---------------------------------------------------------------------------


def _validate_url_no_ssrf(url: str) -> str:
    """Validate that a URL does not target private/reserved IP ranges (SSRF protection).

    Args:
        url: The URL string to validate.

    Returns:
        The original URL if valid.

    Raises:
        ValueError: If the URL scheme is not http/https, targets localhost, or
            resolves to a private, loopback, or link-local IP address.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http and https schemes are allowed")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must have a valid hostname")
    if hostname in ("localhost", "0.0.0.0", "::1"):
        raise ValueError("localhost URLs are not allowed")
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in addr_infos:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise ValueError(f"URL resolves to a private/reserved IP address: {ip}")
    except socket.gaierror:
        # Hostname could not be resolved; allow it (scrape will fail at runtime)
        pass
    return url


# ---------------------------------------------------------------------------
# Scraping request/response schemas
# ---------------------------------------------------------------------------


class WebsiteCreateRequest(BaseModel):
    """Request body for POST /scraping/websites."""
    url: str = Field(..., description="Target URL (http/https only, no private IPs)")
    name: str = Field(..., min_length=1, max_length=200)
    scrape_interval_minutes: int | None = Field(None, gt=0)
    max_depth: int = Field(1, ge=1, le=5)
    max_pages: int = Field(10, ge=1, le=100)
    include_external: bool = Field(False)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Apply SSRF protection to the provided URL."""
        return _validate_url_no_ssrf(v)


class WebsiteUpdateRequest(BaseModel):
    """Request body for PUT /scraping/websites/{id}."""
    name: str | None = Field(None, min_length=1, max_length=200)
    scrape_interval_minutes: int | None = Field(None, gt=0)
    is_active: bool | None = None
    max_depth: int | None = Field(None, ge=1, le=5)
    max_pages: int | None = Field(None, ge=1, le=100)
    include_external: bool | None = None


class WebsiteResponse(BaseModel):
    """Response model for a scraping website."""
    id: int
    url: str
    name: str
    scrape_status: str
    scrape_interval_minutes: int | None
    is_active: bool
    max_depth: int
    max_pages: int
    include_external: bool
    last_scraped_at: datetime | None
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class ScrapeResultResponse(BaseModel):
    """Response model for a scrape result (without full content)."""
    id: int
    website_id: int
    scraped_at: datetime
    content_length: int
    content_preview: str
    status: str
    error_message: str | None
    page_url: str | None = None
    depth: int = 0
    scrape_run_id: str | None = None
    parent_result_id: int | None = None

    class Config:
        from_attributes = True


class ScrapeResultDetailResponse(ScrapeResultResponse):
    """Response model for a scrape result including the full content."""
    content: str


class ScrapeRunResponse(BaseModel):
    """Summary of a single scrape run for a website."""
    scrape_run_id: str
    website_id: int
    scraped_at: datetime
    total_pages: int
    success_count: int
    error_count: int
