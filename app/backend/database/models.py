from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float, JSON, ForeignKey, Index
from sqlalchemy.orm import backref, relationship
from sqlalchemy.sql import func
from .connection import Base


class HedgeFundFlow(Base):
    """Table to store React Flow configurations (nodes, edges, viewport)"""
    __tablename__ = "hedge_fund_flows"
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Flow metadata
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # React Flow state
    nodes = Column(JSON, nullable=False)  # Store React Flow nodes as JSON
    edges = Column(JSON, nullable=False)  # Store React Flow edges as JSON
    viewport = Column(JSON, nullable=True)  # Store viewport state (zoom, x, y)
    data = Column(JSON, nullable=True)  # Store node internal states (tickers, models, etc.)
    
    # Additional metadata
    is_template = Column(Boolean, default=False)  # Mark as template for reuse
    tags = Column(JSON, nullable=True)  # Store tags for categorization


class HedgeFundFlowRun(Base):
    """Table to track individual execution runs of a hedge fund flow"""
    __tablename__ = "hedge_fund_flow_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    flow_id = Column(Integer, ForeignKey("hedge_fund_flows.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Run execution tracking
    status = Column(String(50), nullable=False, default="IDLE")  # IDLE, IN_PROGRESS, COMPLETE, ERROR
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Run configuration
    trading_mode = Column(String(50), nullable=False, default="one-time")  # one-time, continuous, advisory
    schedule = Column(String(50), nullable=True)  # hourly, daily, weekly (for continuous mode)
    duration = Column(String(50), nullable=True)  # 1day, 1week, 1month (for continuous mode)
    
    # Run data
    request_data = Column(JSON, nullable=True)  # Store the request parameters (tickers, agents, models, etc.)
    initial_portfolio = Column(JSON, nullable=True)  # Store initial portfolio state
    final_portfolio = Column(JSON, nullable=True)  # Store final portfolio state
    results = Column(JSON, nullable=True)  # Store the output/results from the run
    error_message = Column(Text, nullable=True)  # Store error details if run failed
    
    # Metadata
    run_number = Column(Integer, nullable=False, default=1)  # Sequential run number for this flow


class HedgeFundFlowRunCycle(Base):
    """Individual analysis cycles within a trading session"""
    __tablename__ = "hedge_fund_flow_run_cycles"
    
    id = Column(Integer, primary_key=True, index=True)
    flow_run_id = Column(Integer, ForeignKey("hedge_fund_flow_runs.id"), nullable=False, index=True)
    cycle_number = Column(Integer, nullable=False)  # 1, 2, 3, etc. within the run
    
    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Analysis results
    analyst_signals = Column(JSON, nullable=True)  # All agent decisions/signals
    trading_decisions = Column(JSON, nullable=True)  # Portfolio manager decisions
    executed_trades = Column(JSON, nullable=True)  # Actual trades executed (paper trading)
    
    # Portfolio state after this cycle
    portfolio_snapshot = Column(JSON, nullable=True)  # Cash, positions, performance metrics
    
    # Performance metrics for this cycle
    performance_metrics = Column(JSON, nullable=True)  # Returns, sharpe ratio, etc.
    
    # Execution tracking
    status = Column(String(50), nullable=False, default="IN_PROGRESS")  # IN_PROGRESS, COMPLETED, ERROR
    error_message = Column(Text, nullable=True)  # Store error details if cycle failed
    
    # Cost tracking
    llm_calls_count = Column(Integer, nullable=True, default=0)  # Number of LLM calls made
    api_calls_count = Column(Integer, nullable=True, default=0)  # Number of financial API calls made
    estimated_cost = Column(String(20), nullable=True)  # Estimated cost in USD
    
    # Metadata
    trigger_reason = Column(String(100), nullable=True)  # scheduled, manual, market_event, etc.
    market_conditions = Column(JSON, nullable=True)  # Market data snapshot at cycle start


class ApiKey(Base):
    """Table to store API keys for various services"""
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # API key details
    provider = Column(String(100), nullable=False, unique=True, index=True)  # e.g., "ANTHROPIC_API_KEY"
    key_value = Column(Text, nullable=False)  # The actual API key (encrypted in production)
    is_active = Column(Boolean, default=True)  # Enable/disable without deletion
    
    # Optional metadata
    description = Column(Text, nullable=True)  # Human-readable description
    last_used = Column(DateTime(timezone=True), nullable=True)  # Track usage


class ScrapingWebsite(Base):
    """Table to store target websites for scraping with scheduling configuration."""
    __tablename__ = "scraping_websites"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Website configuration
    url = Column(String(2048), nullable=False)
    name = Column(String(200), nullable=False)

    # Scrape status: idle, in_progress, completed, error
    scrape_status = Column(String(50), nullable=False, default="idle")
    scrape_interval_minutes = Column(Integer, nullable=True)  # None means no scheduling
    is_active = Column(Boolean, default=True)

    # Depth crawling configuration
    max_depth = Column(Integer, nullable=False, default=1)
    max_pages = Column(Integer, nullable=False, default=10)
    include_external = Column(Boolean, nullable=False, default=False)

    # Last scrape tracking
    last_scraped_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)

    # Relationship to results with cascade delete
    results = relationship("ScrapeResult", back_populates="website", cascade="all, delete-orphan")


class ScrapeResult(Base):
    """Table to store individual scrape results for a website."""
    __tablename__ = "scrape_results"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Foreign key to the website
    website_id = Column(Integer, ForeignKey("scraping_websites.id"), nullable=False, index=True)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())

    # Scraped content (truncated to 1MB)
    content = Column(Text, nullable=True)
    content_length = Column(Integer, default=0)  # Original length before truncation

    # Result status: success, error
    status = Column(String(50), nullable=False)
    error_message = Column(Text, nullable=True)

    # Depth crawling fields
    page_url = Column(String(2048), nullable=True)  # Actual URL of this page
    depth = Column(Integer, nullable=False, default=0)  # 0 = root page
    parent_result_id = Column(Integer, ForeignKey("scrape_results.id"), nullable=True)
    scrape_run_id = Column(String(36), nullable=True, index=True)  # UUID grouping one execution

    # Relationships
    website = relationship("ScrapingWebsite", back_populates="results")
    children = relationship("ScrapeResult", backref=backref("parent", remote_side="ScrapeResult.id"))

    __table_args__ = (
        Index("ix_scrape_results_website_id_scraped_at", "website_id", "scraped_at"),
    )


class ThirteenFCompany(Base):
    """Cached 13F-HR company names + CIKs, synced from SEC EDGAR."""
    __tablename__ = "thirteenf_companies"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String(500), nullable=False, index=True)
    cik = Column(Integer, nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AppSetting(Base):
    """Key-value store for application settings (e.g. selected LLM model)."""
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ThirteenFSavedSelection(Base):
    """User-saved company selections for the 13F-HR dropdown filter."""
    __tablename__ = "thirteenf_saved_selections"

    id = Column(Integer, primary_key=True, index=True)
    cik = Column(Integer, nullable=False, unique=True, index=True)
    company = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SpinoffFiling(Base):
    """Cached SEC Form 10 / 10-12B filings (new public entities, often spin-offs)."""
    __tablename__ = "spinoff_filings"

    id = Column(Integer, primary_key=True, index=True)
    accession_no = Column(String(50), nullable=False, unique=True, index=True)
    cik = Column(Integer, nullable=False, index=True)
    company = Column(String(500), nullable=False, index=True)
    form = Column(String(20), nullable=False, index=True)
    filing_date = Column(String(10), nullable=False, index=True)
    primary_doc_url = Column(String(500), nullable=True)
    primary_doc_description = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Alert(Base):
    """Alert events generated by alert rules; persisted for in-app feed + de-dupe."""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    rule_type = Column(String(50), nullable=False, index=True)
    ticker = Column(String(20), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    payload = Column(JSON, nullable=True)
    severity = Column(String(20), nullable=False, default="info")
    sent_to_telegram = Column(Boolean, default=False)
    telegram_error = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index("ix_alerts_rule_ticker_created", "rule_type", "ticker", "created_at"),
    )


class WatchlistItem(Base):
    """User-saved tickers with cached latest sentiment snapshot."""
    __tablename__ = "watchlist_items"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), nullable=False, unique=True, index=True)
    notes = Column(Text, nullable=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    last_analyzed_at = Column(DateTime(timezone=True), nullable=True)
    last_overall_sentiment = Column(String(20), nullable=True)
    last_delta_direction = Column(String(20), nullable=True)
    last_management_tone = Column(String(200), nullable=True)
    last_payload = Column(JSON, nullable=True)
    last_error = Column(Text, nullable=True)


class DiscoverySnapshot(Base):
    """Per-ticker Discovery score snapshots, written on each fresh compute.

    Enables historical score tracking, "score moved from X to Y" alerts, and
    eventually backtest replay. Tickers with no public symbol (spin-off CIKs)
    use the CIK string as the ticker key with ``is_ticker=False``.
    """
    __tablename__ = "discovery_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), nullable=False, index=True)
    cik = Column(Integer, nullable=True, index=True)
    is_ticker = Column(Boolean, nullable=False, default=True)
    company = Column(String(500), nullable=True)
    score = Column(Float, nullable=False)
    distinct_sources = Column(Integer, nullable=False, default=0)
    signals = Column(JSON, nullable=True)
    snapshot_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    __table_args__ = (
        Index("ix_discovery_snapshots_ticker_at", "ticker", "snapshot_at"),
    )


class WhaleFund(Base):
    """A user-curated whale fund whose 13F entries we track for don't-chase signals.

    Seeded with ~10 well-known investors at first run, fully editable through
    the settings page. CIK is the unique key (SEC filer ID).
    """
    __tablename__ = "whale_funds"

    id = Column(Integer, primary_key=True, index=True)
    cik = Column(Integer, nullable=False, unique=True, index=True)
    name = Column(String(500), nullable=False)
    notes = Column(Text, nullable=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())


class WhaleEntryCache(Base):
    """Computed entry price per (whale, ticker) pair from 13F history.

    Walks back through a whale's 13F filings to find the earliest filing
    where a ticker first appears, then approximates entry price as the
    volume-weighted typical price over that filing's report period.

    Refreshed on demand; rows older than 7 days are treated as stale.
    """
    __tablename__ = "whale_entry_cache"

    id = Column(Integer, primary_key=True, index=True)
    whale_cik = Column(Integer, nullable=False, index=True)
    ticker = Column(String(20), nullable=False, index=True)
    entry_quarter_label = Column(String(20), nullable=True)
    entry_period_start = Column(String(20), nullable=True)
    entry_period_end = Column(String(20), nullable=True)
    entry_vwap = Column(Float, nullable=True)
    entry_low = Column(Float, nullable=True)
    entry_high = Column(Float, nullable=True)
    share_count_at_entry = Column(Float, nullable=True)
    is_pre_lookback = Column(Boolean, nullable=False, default=False)
    computed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_whale_entry_cache_whale_ticker", "whale_cik", "ticker", unique=True),
        Index("ix_whale_entry_cache_ticker", "ticker"),
    )