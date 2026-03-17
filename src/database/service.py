"""Database service for storing trading data"""
from datetime import datetime
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
import json

from .models import (
    TradingSession,
    TradingDecision,
    AnalystAnalysis,
    MarketData,
    PerformanceMetrics,
)
from .connection import SessionLocal


class DatabaseService:
    """数据库服务类"""

    def __init__(self):
        self.db: Optional[Session] = None
        self.current_session_id: Optional[int] = None

    def connect(self):
        """连接数据库"""
        if not self.db:
            self.db = SessionLocal()

    def close(self):
        """关闭数据库连接"""
        if self.db:
            self.db.close()
            self.db = None

    def create_trading_session(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        model_name: str,
        model_provider: str,
        initial_cash: float = 100000.0,
        margin_requirement: float = 0.0,
    ) -> int:
        """
        创建交易会话

        Returns:
            session_id: 创建的会话ID
        """
        self.connect()

        session = TradingSession(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            model_name=model_name,
            model_provider=model_provider,
            initial_cash=initial_cash,
            margin_requirement=margin_requirement,
            status="RUNNING",
        )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        self.current_session_id = session.id
        print(f"✅ 创建交易会话 ID: {session.id}")
        return session.id

    def save_trading_decisions(
        self,
        session_id: int,
        decisions: Dict,
        analyst_signals: Dict,
        current_prices: Dict = None,
    ):
        """
        保存交易决策和分析师信号

        Args:
            session_id: 会话ID
            decisions: Portfolio Manager的决策
            analyst_signals: 所有分析师的信号
            current_prices: 当前价格（可选）
        """
        self.connect()

        # 统计每个ticker的信号
        signal_counts = {}
        for ticker in decisions.keys():
            bullish = 0
            bearish = 0
            neutral = 0

            for agent, signals in analyst_signals.items():
                if agent.startswith("risk_management"):
                    continue
                if ticker in signals:
                    signal = signals[ticker].get("signal", "").upper()
                    if signal == "BULLISH":
                        bullish += 1
                    elif signal == "BEARISH":
                        bearish += 1
                    elif signal == "NEUTRAL":
                        neutral += 1

            signal_counts[ticker] = {
                "bullish": bullish,
                "bearish": bearish,
                "neutral": neutral,
            }

        # 保存交易决策
        for ticker, decision in decisions.items():
            trading_decision = TradingDecision(
                session_id=session_id,
                ticker=ticker,
                action=decision.get("action", "HOLD").upper(),
                quantity=decision.get("quantity", 0),
                confidence=decision.get("confidence", 0.0),
                reasoning=decision.get("reasoning", ""),
                current_price=current_prices.get(ticker) if current_prices else None,
                bullish_signals=signal_counts[ticker]["bullish"],
                bearish_signals=signal_counts[ticker]["bearish"],
                neutral_signals=signal_counts[ticker]["neutral"],
            )
            self.db.add(trading_decision)

        # 保存分析师分析
        for agent_name, signals in analyst_signals.items():
            # 跳过风险管理代理
            if agent_name.startswith("risk_management"):
                continue

            # 确定分析师类型
            analyst_type = self._get_analyst_type(agent_name)

            for ticker, signal_data in signals.items():
                analyst_analysis = AnalystAnalysis(
                    session_id=session_id,
                    analyst_name=agent_name,
                    analyst_type=analyst_type,
                    ticker=ticker,
                    signal=signal_data.get("signal", "NEUTRAL").upper(),
                    confidence=signal_data.get("confidence", 0.0),
                    reasoning=self._extract_reasoning(signal_data.get("reasoning")),
                    analysis_data=signal_data,  # 保存完整的signal_data（含signal/confidence/reasoning）
                )
                self.db.add(analyst_analysis)

        self.db.commit()
        print(f"✅ 保存交易决策和分析师信号到数据库")

    def _get_analyst_type(self, agent_name: str) -> str:
        """根据代理名称确定分析师类型"""
        if "fundamental" in agent_name.lower():
            return "fundamental"
        elif "technical" in agent_name.lower():
            return "technical"
        elif "sentiment" in agent_name.lower():
            return "sentiment"
        elif "valuation" in agent_name.lower():
            return "valuation"
        elif "growth" in agent_name.lower():
            return "growth"
        elif "news" in agent_name.lower():
            return "news"
        else:
            return "investor"  # 投资者风格的代理

    def _extract_reasoning(self, reasoning) -> str:
        """提取推理文本"""
        if isinstance(reasoning, str):
            return reasoning[:5000]  # 限制长度
        elif isinstance(reasoning, dict):
            return json.dumps(reasoning, ensure_ascii=False)[:5000]
        else:
            return str(reasoning)[:5000]

    def save_market_data(
        self,
        session_id: int,
        ticker: str,
        data_date: str,
        price_data: Dict = None,
        financial_metrics: Dict = None,
        news_data: Dict = None,
        technical_indicators: Dict = None,
    ):
        """
        保存市场数据

        Args:
            session_id: 会话ID
            ticker: 股票代码
            data_date: 数据日期
            price_data: 价格数据
            financial_metrics: 财务指标
            news_data: 新闻数据
            technical_indicators: 技术指标
        """
        self.connect()

        market_data = MarketData(
            session_id=session_id,
            ticker=ticker,
            data_date=data_date,
            open_price=price_data.get("open") if price_data else None,
            high_price=price_data.get("high") if price_data else None,
            low_price=price_data.get("low") if price_data else None,
            close_price=price_data.get("close") if price_data else None,
            volume=price_data.get("volume") if price_data else None,
            financial_metrics=financial_metrics,
            news_count=news_data.get("count", 0) if news_data else 0,
            news_sentiment=news_data.get("sentiment") if news_data else None,
            technical_indicators=technical_indicators,
        )

        self.db.add(market_data)
        self.db.commit()

    def complete_session(
        self,
        session_id: int,
        status: str = "COMPLETED",
        error_message: str = None,
    ):
        """
        完成交易会话

        Args:
            session_id: 会话ID
            status: 状态 (COMPLETED, ERROR)
            error_message: 错误信息（如果有）
        """
        self.connect()

        session = self.db.query(TradingSession).filter(TradingSession.id == session_id).first()
        if session:
            session.status = status
            session.completed_at = datetime.now()
            if error_message:
                session.error_message = error_message
            self.db.commit()
            print(f"✅ 会话 {session_id} 已完成，状态: {status}")

    def save_performance_metrics(
        self,
        session_id: int,
        start_date: str,
        end_date: str,
        metrics: Dict,
    ):
        """
        保存性能指标

        Args:
            session_id: 会话ID
            start_date: 开始日期
            end_date: 结束日期
            metrics: 性能指标字典
        """
        self.connect()

        performance = PerformanceMetrics(
            session_id=session_id,
            start_date=start_date,
            end_date=end_date,
            total_return=metrics.get("total_return"),
            annualized_return=metrics.get("annualized_return"),
            sharpe_ratio=metrics.get("sharpe_ratio"),
            sortino_ratio=metrics.get("sortino_ratio"),
            max_drawdown=metrics.get("max_drawdown"),
            volatility=metrics.get("volatility"),
            long_short_ratio=metrics.get("long_short_ratio"),
            gross_exposure=metrics.get("gross_exposure"),
            net_exposure=metrics.get("net_exposure"),
            total_trades=metrics.get("total_trades", 0),
            winning_trades=metrics.get("winning_trades", 0),
            losing_trades=metrics.get("losing_trades", 0),
            win_rate=metrics.get("win_rate"),
            daily_returns=metrics.get("daily_returns"),
            portfolio_values=metrics.get("portfolio_values"),
        )

        self.db.add(performance)
        self.db.commit()
        print(f"✅ 保存性能指标到数据库")

    def get_recent_sessions(self, limit: int = 10) -> List[TradingSession]:
        """获取最近的交易会话"""
        self.connect()
        return (
            self.db.query(TradingSession)
            .order_by(TradingSession.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_session_details(self, session_id: int) -> Dict:
        """获取会话详情"""
        self.connect()

        session = self.db.query(TradingSession).filter(TradingSession.id == session_id).first()
        if not session:
            return None

        decisions = (
            self.db.query(TradingDecision)
            .filter(TradingDecision.session_id == session_id)
            .all()
        )

        analyses = (
            self.db.query(AnalystAnalysis)
            .filter(AnalystAnalysis.session_id == session_id)
            .all()
        )

        return {
            "session": session,
            "decisions": decisions,
            "analyses": analyses,
        }


# 全局数据库服务实例
_db_service = None


def get_db_service() -> DatabaseService:
    """获取数据库服务实例"""
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service
