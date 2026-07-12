from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, JSON, ForeignKey
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


class Account(Base):
    """Family ISA accounts (e.g. Chandra ISA, Wife ISA, Kids JISA)"""
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    owner_name = Column(String(200), nullable=False, index=True)
    account_type = Column(String(100), nullable=False, default="ISA")  # ISA, JISA, SIPP, GIA
    provider = Column(String(200), nullable=False, default="AJ Bell")
    label = Column(String(300), nullable=True)  # e.g. "Chandra Stocks & Shares ISA"


class Holding(Base):
    """Table to store user portfolio holdings"""
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True, index=True)
    portfolio_name = Column(String(200), nullable=False, default="Default", index=True)
    ticker = Column(String(20), nullable=False, index=True)
    investment_name = Column(String(300), nullable=False)
    quantity = Column(String(50), nullable=False)  # stored as string to handle fractional shares
    buy_price = Column(String(50), nullable=False)  # price per unit at purchase
    cost_basis = Column(String(50), nullable=True)  # total cost (quantity * buy_price)
    currency = Column(String(10), nullable=False, default="GBP")
    sector = Column(String(200), nullable=True)  # e.g. Technology, Healthcare, Bonds


class Watchlist(Base):
    """Watchlist stocks for analysis without holding position"""
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    ticker = Column(String(20), nullable=False, index=True)
    investment_name = Column(String(300), nullable=True)
    notes = Column(Text, nullable=True)


class PortfolioAnalysisResult(Base):
    """Stores results from the AI agent analysis pipeline"""
    __tablename__ = "portfolio_analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    holding_id = Column(Integer, ForeignKey("holdings.id"), nullable=True, index=True)
    watchlist_id = Column(Integer, ForeignKey("watchlist.id"), nullable=True, index=True)
    ticker = Column(String(20), nullable=False, index=True)
    analysis_ticker = Column(String(20), nullable=False)

    final_action = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False, default=0.0)

    technical_summary = Column(Text, nullable=True)
    fundamental_summary = Column(Text, nullable=True)
    sentiment_summary = Column(Text, nullable=True)
    valuation_summary = Column(Text, nullable=True)
    risk_summary = Column(Text, nullable=True)
    portfolio_manager_summary = Column(Text, nullable=True)

    positive_factors = Column(Text, nullable=True)  # JSON array
    risk_factors = Column(Text, nullable=True)  # JSON array
    uncertainties = Column(Text, nullable=True)  # JSON array
    price_estimate = Column(Text, nullable=True)  # JSON object: experimental next-price estimate


class AnalysisJob(Base):
    """Tracks async analysis job execution"""
    __tablename__ = "analysis_jobs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed
    job_type = Column(String(50), nullable=False)  # portfolio, watchlist
    total_tickers = Column(Integer, nullable=True)
    completed_tickers = Column(Integer, nullable=True, default=0)
    error_message = Column(Text, nullable=True)
    result_ids = Column(Text, nullable=True)  # JSON array of PortfolioAnalysisResult IDs

    # Token optimization fields
    analysis_mode = Column(String(20), nullable=True, default="quick_scan")
    model_name = Column(String(50), nullable=True)
    agent_count = Column(Integer, nullable=True, default=0)
    estimated_tokens = Column(Integer, nullable=True, default=0)
    elapsed_seconds = Column(Float, nullable=True)


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


 