"""Database models for storing trading data"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, JSON, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .connection import Base


class TradingSession(Base):
    """交易会话 - 每次运行CLI的记录"""
    __tablename__ = "trading_sessions"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # 运行参数
    tickers = Column(JSON, nullable=False)  # 股票代码列表
    start_date = Column(String(20), nullable=False)
    end_date = Column(String(20), nullable=False)
    model_name = Column(String(100), nullable=False)
    model_provider = Column(String(50), nullable=False)

    # 初始配置
    initial_cash = Column(Float, default=100000.0)
    margin_requirement = Column(Float, default=0.0)

    # 状态
    status = Column(String(20), default="RUNNING")  # RUNNING, COMPLETED, ERROR
    error_message = Column(Text, nullable=True)

    # 关系
    decisions = relationship("TradingDecision", back_populates="session", cascade="all, delete-orphan")
    analyst_analyses = relationship("AnalystAnalysis", back_populates="session", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_session_date', 'created_at'),
        # Note: JSON columns cannot be indexed directly in MySQL
    )


class TradingDecision(Base):
    """交易决策 - Portfolio Manager的最终决策"""
    __tablename__ = "trading_decisions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("trading_sessions.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 股票信息
    ticker = Column(String(20), nullable=False, index=True)

    # 决策内容
    action = Column(String(20), nullable=False)  # BUY, SELL, SHORT, COVER, HOLD
    quantity = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=False)
    reasoning = Column(Text, nullable=True)

    # 市场数据
    current_price = Column(Float, nullable=True)

    # 信号统计
    bullish_signals = Column(Integer, default=0)
    bearish_signals = Column(Integer, default=0)
    neutral_signals = Column(Integer, default=0)

    # 关系
    session = relationship("TradingSession", back_populates="decisions")

    # 索引
    __table_args__ = (
        Index('idx_decision_ticker', 'ticker'),
        Index('idx_decision_action', 'action'),
        Index('idx_decision_date', 'created_at'),
    )


class AnalystAnalysis(Base):
    """分析师分析 - 每个代理的详细分析"""
    __tablename__ = "analyst_analyses"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("trading_sessions.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 分析师信息
    analyst_name = Column(String(100), nullable=False, index=True)
    analyst_type = Column(String(50), nullable=False)  # fundamental, technical, sentiment, etc.

    # 股票信息
    ticker = Column(String(20), nullable=False, index=True)

    # 分析结果
    signal = Column(String(20), nullable=False)  # BULLISH, BEARISH, NEUTRAL
    confidence = Column(Float, nullable=False)
    reasoning = Column(Text, nullable=True)

    # 详细分析数据（JSON格式存储原始数据）
    analysis_data = Column(JSON, nullable=True)

    # 关系
    session = relationship("TradingSession", back_populates="analyst_analyses")

    # 索引
    __table_args__ = (
        Index('idx_analysis_analyst', 'analyst_name'),
        Index('idx_analysis_ticker', 'ticker'),
        Index('idx_analysis_signal', 'signal'),
        Index('idx_analysis_date', 'created_at'),
    )


class MarketData(Base):
    """市场数据 - 存储获取的市场数据快照"""
    __tablename__ = "market_data"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("trading_sessions.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 股票信息
    ticker = Column(String(20), nullable=False, index=True)
    data_date = Column(String(20), nullable=False)  # 数据日期

    # 价格数据
    open_price = Column(Float, nullable=True)
    high_price = Column(Float, nullable=True)
    low_price = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)

    # 财务指标
    financial_metrics = Column(JSON, nullable=True)

    # 新闻数据
    news_count = Column(Integer, default=0)
    news_sentiment = Column(String(20), nullable=True)  # positive, negative, neutral

    # 技术指标
    technical_indicators = Column(JSON, nullable=True)

    # 索引
    __table_args__ = (
        Index('idx_market_ticker_date', 'ticker', 'data_date'),
        Index('idx_market_date', 'data_date'),
    )


class PerformanceMetrics(Base):
    """性能指标 - 回测和实时交易的性能指标"""
    __tablename__ = "performance_metrics"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("trading_sessions.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 日期范围
    start_date = Column(String(20), nullable=False)
    end_date = Column(String(20), nullable=False)

    # 收益指标
    total_return = Column(Float, nullable=True)
    annualized_return = Column(Float, nullable=True)

    # 风险指标
    sharpe_ratio = Column(Float, nullable=True)
    sortino_ratio = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    volatility = Column(Float, nullable=True)

    # 持仓指标
    long_short_ratio = Column(Float, nullable=True)
    gross_exposure = Column(Float, nullable=True)
    net_exposure = Column(Float, nullable=True)

    # 交易统计
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, nullable=True)

    # 详细数据
    daily_returns = Column(JSON, nullable=True)
    portfolio_values = Column(JSON, nullable=True)

    # 索引
    __table_args__ = (
        Index('idx_perf_session', 'session_id'),
        Index('idx_perf_date', 'end_date'),
    )
