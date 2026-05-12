import json
import os
from datetime import datetime

from sqlalchemy import Column, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    id = Column(Integer, primary_key=True)
    run_id = Column(String, nullable=False)
    date = Column(String, nullable=False)
    cash = Column(Float, nullable=False)
    long_value = Column(Float, nullable=False)
    short_value = Column(Float, nullable=False)
    nlv = Column(Float, nullable=False)
    positions = Column(Text, nullable=False)
    created_at = Column(String, nullable=False)


class TradeLog(Base):
    __tablename__ = "trade_log"
    id = Column(Integer, primary_key=True)
    run_id = Column(String, nullable=False)
    date = Column(String, nullable=False)
    ticker = Column(String, nullable=False)
    action = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    cash_impact = Column(Float, nullable=False)
    created_at = Column(String, nullable=False)


class DecisionLog(Base):
    __tablename__ = "decision_log"
    id = Column(Integer, primary_key=True)
    run_id = Column(String, nullable=False)
    date = Column(String, nullable=False)
    ticker = Column(String, nullable=False)
    agent = Column(String, nullable=False)
    signal = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    reasoning = Column(Text, nullable=False)
    created_at = Column(String, nullable=False)


_engine = None


def _db_path() -> str:
    return os.environ.get(
        "HEDGE_FUND_DB_PATH",
        os.path.join(os.path.dirname(__file__), "..", "..", "data", "hedge_fund.db"),
    )


def get_engine():
    global _engine
    if _engine is None:
        path = os.path.abspath(_db_path())
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _engine = create_engine(f"sqlite:///{path}")
        Base.metadata.create_all(_engine)
    return _engine


def _now() -> str:
    return datetime.utcnow().isoformat()


def write_portfolio_snapshot(
    run_id: str, date: str, portfolio: dict, current_prices: dict
) -> None:
    cash = float(portfolio.get("cash", 0.0))
    positions = portfolio.get("positions", {})
    long_value = sum(
        pos.get("long", 0) * float(current_prices.get(t, 0))
        for t, pos in positions.items()
    )
    short_value = sum(
        pos.get("short", 0) * float(current_prices.get(t, 0))
        for t, pos in positions.items()
    )
    nlv = cash + long_value - short_value
    with Session(get_engine()) as session:
        session.add(
            PortfolioSnapshot(
                run_id=run_id,
                date=date,
                cash=cash,
                long_value=long_value,
                short_value=short_value,
                nlv=nlv,
                positions=json.dumps(positions),
                created_at=_now(),
            )
        )
        session.commit()


def write_trade(
    run_id: str,
    date: str,
    ticker: str,
    action: str,
    quantity: int,
    price: float,
    cash_impact: float,
) -> None:
    with Session(get_engine()) as session:
        session.add(
            TradeLog(
                run_id=run_id,
                date=date,
                ticker=ticker,
                action=action,
                quantity=int(quantity),
                price=float(price),
                cash_impact=float(cash_impact),
                created_at=_now(),
            )
        )
        session.commit()


def write_decision(
    run_id: str,
    date: str,
    ticker: str,
    agent: str,
    signal: str,
    confidence: float,
    reasoning: str,
) -> None:
    with Session(get_engine()) as session:
        session.add(
            DecisionLog(
                run_id=run_id,
                date=date,
                ticker=ticker,
                agent=agent,
                signal=signal,
                confidence=float(confidence),
                reasoning=reasoning,
                created_at=_now(),
            )
        )
        session.commit()
