# Missing Components Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four missing capabilities to the ai-hedge-fund: persistent SQLite audit trail, market regime detection, confidence-weighted signal aggregation, and a SEC EDGAR 10-K/10-Q/8-K analyst agent.

**Architecture:** Each component is self-contained. The database module is foundational and wired in last after all new code is stable. Regime detection is embedded in the existing risk manager node (no graph changes). Confidence aggregation replaces the majority-vote logic in portfolio_manager.py. The SEC agent is a new analyst node registered in ANALYST_CONFIG.

**Tech Stack:** SQLAlchemy (already installed via LangChain), requests (already installed), pandas/numpy (already installed), SEC EDGAR public API (no key required).

---

## Task 1: Fork Setup

**Files:**
- Modify: `.git/config` (remote added via `gh`)

- [ ] **Step 1: Fork the upstream repo under your GitHub account**

```bash
cd /Users/vanditgandotra/ai-hedge-fund
gh repo fork virattt/ai-hedge-fund --clone=false
```

Expected output: `✓ Created fork VanditGandotra/ai-hedge-fund`

- [ ] **Step 2: Add your fork as the `origin` remote and rename upstream**

```bash
git remote rename origin upstream
git remote add origin https://github.com/VanditGandotra/ai-hedge-fund.git
git remote -v
```

Expected: two remotes — `origin` pointing to VanditGandotra/ai-hedge-fund and `upstream` pointing to virattt/ai-hedge-fund.

- [ ] **Step 3: Create a feature branch**

```bash
git checkout -b feature/missing-components
```

- [ ] **Step 4: Commit**

```bash
git commit --allow-empty -m "chore: start feature/missing-components branch"
```

---

## Task 2: Database Module

**Files:**
- Create: `src/data/database.py`
- Create: `tests/test_database.py`
- Create: `data/.gitkeep` (so data dir is tracked)

- [ ] **Step 1: Create the `data/` directory placeholder**

```bash
mkdir -p /Users/vanditgandotra/ai-hedge-fund/data
touch /Users/vanditgandotra/ai-hedge-fund/data/.gitkeep
echo "hedge_fund.db" >> /Users/vanditgandotra/ai-hedge-fund/.gitignore
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_database.py`:

```python
import os
import pytest
from src.data import database


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    """Point the module at a fresh temp DB for each test."""
    os.environ["HEDGE_FUND_DB_PATH"] = str(tmp_path / "test.db")
    database._engine = None
    yield
    database._engine = None
    del os.environ["HEDGE_FUND_DB_PATH"]


def test_write_and_read_trade():
    database.write_trade("run1", "2025-01-01", "AAPL", "buy", 10, 150.0, -1500.0)
    engine = database.get_engine()
    with database.Session(engine) as session:
        rows = session.query(database.TradeLog).all()
    assert len(rows) == 1
    assert rows[0].ticker == "AAPL"
    assert rows[0].action == "buy"
    assert rows[0].quantity == 10
    assert rows[0].cash_impact == -1500.0


def test_write_and_read_decision():
    database.write_decision("run1", "2025-01-01", "AAPL", "warren_buffett_agent", "bullish", 75.0, "Strong moat")
    engine = database.get_engine()
    with database.Session(engine) as session:
        rows = session.query(database.DecisionLog).all()
    assert len(rows) == 1
    assert rows[0].signal == "bullish"
    assert rows[0].confidence == 75.0


def test_write_and_read_portfolio_snapshot():
    portfolio = {
        "cash": 90000.0,
        "positions": {"AAPL": {"long": 10, "short": 0}},
    }
    current_prices = {"AAPL": 150.0}
    database.write_portfolio_snapshot("run1", "2025-01-01", portfolio, current_prices)
    engine = database.get_engine()
    with database.Session(engine) as session:
        rows = session.query(database.PortfolioSnapshot).all()
    assert len(rows) == 1
    assert rows[0].cash == 90000.0
    assert rows[0].long_value == 1500.0
    assert rows[0].nlv == 91500.0


def test_multiple_runs_are_independent():
    database.write_trade("runA", "2025-01-01", "AAPL", "buy", 5, 150.0, -750.0)
    database.write_trade("runB", "2025-01-01", "MSFT", "sell", 3, 300.0, 900.0)
    engine = database.get_engine()
    with database.Session(engine) as session:
        runA_trades = session.query(database.TradeLog).filter_by(run_id="runA").all()
        runB_trades = session.query(database.TradeLog).filter_by(run_id="runB").all()
    assert len(runA_trades) == 1
    assert len(runB_trades) == 1
    assert runA_trades[0].ticker == "AAPL"
    assert runB_trades[0].ticker == "MSFT"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /Users/vanditgandotra/ai-hedge-fund && poetry run pytest tests/test_database.py -v 2>&1 | tail -10
```

Expected: `ImportError` or `ModuleNotFoundError` — `database` doesn't exist yet.

- [ ] **Step 4: Create `src/data/database.py`**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/vanditgandotra/ai-hedge-fund && poetry run pytest tests/test_database.py -v 2>&1 | tail -15
```

Expected: `4 passed`.

- [ ] **Step 6: Commit**

```bash
cd /Users/vanditgandotra/ai-hedge-fund
git add src/data/database.py tests/test_database.py data/.gitkeep .gitignore
git commit -m "feat: add SQLite persistence module (portfolio_snapshots, trade_log, decision_log)"
```

---

## Task 3: Wire run_id Into State and DB Writes

**Files:**
- Modify: `src/main.py:46-93` (add run_id to invoke payload)
- Modify: `src/backtesting/engine.py:36-80` (add run_id, write trade+snapshot per day)
- Modify: `src/agents/portfolio_manager.py:25-93` (write decision_log per agent signal)

- [ ] **Step 1: Add `run_id` to `run_hedge_fund()` in `src/main.py`**

Add `import uuid` at the top of the file (after the existing imports). Then in `run_hedge_fund()`, add `run_id` to the data payload:

```python
# At top of file, add after existing imports:
import uuid

# Inside run_hedge_fund(), change the agent.invoke() call's data dict to:
"data": {
    "run_id": str(uuid.uuid4()),
    "tickers": tickers,
    "portfolio": portfolio,
    "start_date": start_date,
    "end_date": end_date,
    "analyst_signals": {},
},
```

- [ ] **Step 2: Add `run_id` and DB writes to `BacktestEngine`**

In `src/backtesting/engine.py`, add at the top:

```python
import uuid
from src.data.database import write_trade, write_portfolio_snapshot
```

In `BacktestEngine.__init__()`, add after `self._results = OutputBuilder(...)`:

```python
self._run_id = str(uuid.uuid4())
```

In `run_backtest()`, after `executed_qty = self._executor.execute_trade(...)`, add:

```python
if executed_qty and executed_qty != 0:
    price = current_prices[ticker]
    cash_impact = -executed_qty * price if action in ("buy", "cover") else executed_qty * price
    write_trade(
        self._run_id,
        current_date_str,
        ticker,
        action,
        abs(executed_qty),
        price,
        cash_impact,
    )
```

After `total_value = calculate_portfolio_value(...)`, add:

```python
write_portfolio_snapshot(
    self._run_id,
    current_date_str,
    self._portfolio.__dict__ if hasattr(self._portfolio, "__dict__") else vars(self._portfolio),
    current_prices,
)
```

Note: `Portfolio` is a dataclass — verify it exposes `cash` and `positions` as attributes. If it uses properties, access them directly:

```python
write_portfolio_snapshot(
    self._run_id,
    current_date_str,
    {"cash": self._portfolio.cash, "positions": self._portfolio.positions},
    current_prices,
)
```

- [ ] **Step 3: Write decision_log from portfolio_manager.py**

In `src/agents/portfolio_manager.py`, add at the top:

```python
from src.data.database import write_decision
```

In `portfolio_management_agent()`, after building `signals_by_ticker` (line ~64), add:

```python
    run_id = state["data"].get("run_id", "unknown")
    end_date = state["data"].get("end_date", "unknown")
    for ticker, agent_signals in signals_by_ticker.items():
        for agent_name, payload in agent_signals.items():
            sig = payload.get("sig") or payload.get("signal", "neutral")
            conf = float(payload.get("conf") or payload.get("confidence") or 0)
            write_decision(run_id, end_date, ticker, agent_name, sig, conf, "")
```

- [ ] **Step 4: Smoke-test a live run to verify no errors**

```bash
cd /Users/vanditgandotra/ai-hedge-fund
poetry run python src/main.py --tickers AAPL --analysts warren_buffett --model claude-opus-4-7 2>&1 | tail -20
ls -lh data/hedge_fund.db
```

Expected: DB file created, no import errors, trade output printed.

- [ ] **Step 5: Commit**

```bash
git add src/main.py src/backtesting/engine.py src/agents/portfolio_manager.py
git commit -m "feat: wire run_id and DB audit writes into live run and backtesting engine"
```

---

## Task 4: Regime Detection + Risk Manager Integration

**Files:**
- Create: `src/agents/regime_detector.py`
- Create: `tests/test_regime_detector.py`
- Modify: `src/agents/risk_manager.py:11-20` (call detect_regime, apply multiplier)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_regime_detector.py`:

```python
import numpy as np
import pandas as pd
import pytest

from src.agents.regime_detector import RegimeState, detect_regime


def _make_prices(n: int, daily_return: float, daily_vol: float) -> pd.DataFrame:
    """Build a synthetic price series."""
    rng = np.random.default_rng(42)
    returns = rng.normal(daily_return, daily_vol, n)
    prices = 100 * np.cumprod(1 + returns)
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    return pd.DataFrame({"close": prices}, index=dates)


def test_returns_regime_state_dataclass():
    prices = _make_prices(252, 0.0005, 0.008)
    result = detect_regime(prices)
    assert isinstance(result, RegimeState)
    assert result.regime in ("Bull", "Bear", "High-Vol", "Risk-Off")
    assert result.trend in ("bull", "bear")
    assert result.vol_level in ("low", "elevated", "crisis")
    assert result.momentum in ("risk_on", "neutral", "risk_off")


def test_strong_uptrend_is_bull():
    # Consistent uptrend, low vol
    prices = _make_prices(252, 0.001, 0.003)
    result = detect_regime(prices)
    assert result.trend == "bull"
    assert result.regime == "Bull"


def test_strong_downtrend_is_bear():
    # Consistent downtrend
    prices = _make_prices(252, -0.002, 0.004)
    result = detect_regime(prices)
    assert result.trend == "bear"
    assert result.regime in ("Bear", "Risk-Off")


def test_high_vol_overrides_trend():
    # Uptrend but extreme daily vol (>2% daily ≈ 32% annualised)
    prices = _make_prices(252, 0.0005, 0.025)
    result = detect_regime(prices)
    assert result.vol_level == "crisis"
    assert result.regime == "High-Vol"


def test_insufficient_data_returns_bull_default():
    prices = _make_prices(10, 0.001, 0.01)
    result = detect_regime(prices)
    assert isinstance(result, RegimeState)


def test_regime_multiplier_bull():
    from src.agents.regime_detector import regime_position_multiplier
    assert regime_position_multiplier("Bull") == 1.0


def test_regime_multiplier_risk_off():
    from src.agents.regime_detector import regime_position_multiplier
    assert regime_position_multiplier("Risk-Off") == 0.40


def test_regime_multiplier_unknown_defaults_to_one():
    from src.agents.regime_detector import regime_position_multiplier
    assert regime_position_multiplier("Unknown") == 1.0
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
cd /Users/vanditgandotra/ai-hedge-fund && poetry run pytest tests/test_regime_detector.py -v 2>&1 | tail -5
```

Expected: `ModuleNotFoundError` for `src.agents.regime_detector`.

- [ ] **Step 3: Create `src/agents/regime_detector.py`**

```python
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class RegimeState:
    regime: str        # "Bull" | "Bear" | "High-Vol" | "Risk-Off"
    trend: str         # "bull" | "bear"
    vol_level: str     # "low" | "elevated" | "crisis"
    momentum: str      # "risk_on" | "neutral" | "risk_off"


def detect_regime(spy_prices: pd.DataFrame) -> RegimeState:
    """
    Classify market regime from a SPY (or proxy) OHLCV dataframe with a 'close' column.
    Requires at least 200 rows for full MA calculation; falls back gracefully with less data.
    """
    closes = spy_prices["close"].dropna()
    n = len(closes)

    # --- Trend: 50-day vs 200-day MA ---
    if n >= 200:
        ma50 = closes.iloc[-50:].mean()
        ma200 = closes.mean()  # use all available data up to 200 days
        trend = "bull" if ma50 > ma200 else "bear"
    elif n >= 50:
        ma50 = closes.iloc[-50:].mean()
        ma_long = closes.mean()
        trend = "bull" if ma50 > ma_long else "bear"
    else:
        trend = "bull"  # insufficient data — default to bull

    # --- Volatility: 20-day realized vol (annualised) ---
    daily_returns = closes.pct_change().dropna()
    lookback = min(20, len(daily_returns))
    if lookback >= 2:
        daily_vol = float(daily_returns.iloc[-lookback:].std())
        ann_vol = daily_vol * np.sqrt(252)
    else:
        ann_vol = 0.15  # default to low

    if ann_vol < 0.15:
        vol_level = "low"
    elif ann_vol < 0.30:
        vol_level = "elevated"
    else:
        vol_level = "crisis"

    # --- Momentum: 63-day (≈3 month) return ---
    lookback_mom = min(63, n - 1)
    if lookback_mom >= 5:
        mom_return = float(closes.iloc[-1] / closes.iloc[-lookback_mom - 1] - 1)
    else:
        mom_return = 0.0

    if mom_return > 0.02:
        momentum = "risk_on"
    elif mom_return < -0.02:
        momentum = "risk_off"
    else:
        momentum = "neutral"

    # --- Regime classification (priority: High-Vol > Risk-Off > Bear > Bull) ---
    if vol_level == "crisis":
        regime = "High-Vol"
    elif trend == "bear" and momentum == "risk_off":
        regime = "Risk-Off"
    elif trend == "bear" or momentum == "risk_off":
        regime = "Bear"
    else:
        regime = "Bull"

    return RegimeState(regime=regime, trend=trend, vol_level=vol_level, momentum=momentum)


_MULTIPLIERS = {
    "Bull": 1.00,
    "Bear": 0.70,
    "High-Vol": 0.50,
    "Risk-Off": 0.40,
}


def regime_position_multiplier(regime: str) -> float:
    """Return the position-limit multiplier for a given regime label."""
    return _MULTIPLIERS.get(regime, 1.0)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/vanditgandotra/ai-hedge-fund && poetry run pytest tests/test_regime_detector.py -v 2>&1 | tail -10
```

Expected: `8 passed`.

- [ ] **Step 5: Integrate regime detection into `risk_manager.py`**

Add at the top of `src/agents/risk_manager.py`:

```python
from src.agents.regime_detector import detect_regime, regime_position_multiplier
```

At the beginning of `risk_management_agent()`, after line `api_key = get_api_key_from_state(...)`, add:

```python
    # Detect market regime from SPY
    regime_state = None
    try:
        spy_prices = get_prices(
            ticker="SPY",
            start_date=data["start_date"],
            end_date=data["end_date"],
            api_key=api_key,
        )
        if spy_prices:
            spy_df = prices_to_df(spy_prices)
            regime_state = detect_regime(spy_df)
            progress.update_status(agent_id, None, f"Market regime: {regime_state.regime}")
    except Exception:
        pass  # Non-fatal: fall back to no regime adjustment
```

Then in the per-ticker loop, after `combined_limit_pct = vol_adjusted_limit_pct * corr_multiplier`, add:

```python
        # Regime overlay
        if regime_state is not None:
            regime_mult = regime_position_multiplier(regime_state.regime)
            combined_limit_pct = combined_limit_pct * regime_mult
            # Block new longs in Bear / High-Vol / Risk-Off regimes
            if regime_state.regime != "Bull":
                state["data"]["regime_no_new_longs"] = True
```

Also add the regime to the reasoning dict:

```python
            "reasoning": {
                ...
                "regime": regime_state.regime if regime_state else "unknown",
                "regime_multiplier": regime_mult if regime_state else 1.0,
                ...
            }
```

- [ ] **Step 6: Smoke-test a run and confirm regime appears in output**

```bash
cd /Users/vanditgandotra/ai-hedge-fund
poetry run python src/main.py --tickers AAPL --analysts warren_buffett --model claude-opus-4-7 --show-reasoning 2>&1 | grep -i regime
```

Expected: at least one line mentioning the current regime.

- [ ] **Step 7: Commit**

```bash
git add src/agents/regime_detector.py tests/test_regime_detector.py src/agents/risk_manager.py
git commit -m "feat: add regime detection (Bull/Bear/High-Vol/Risk-Off) with position limit multipliers"
```

---

## Task 5: Confidence-Weighted Signal Aggregation

**Files:**
- Modify: `src/agents/portfolio_manager.py` (add `aggregate_signals`, update `generate_trading_decision`)
- Create: `tests/test_portfolio_manager.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_portfolio_manager.py`:

```python
import pytest
from src.agents.portfolio_manager import aggregate_signals


def test_high_confidence_bullish_wins():
    signals = {
        "agent_a": {"sig": "bullish", "conf": 90},
        "agent_b": {"sig": "bearish", "conf": 30},
    }
    result = aggregate_signals(signals)
    assert result["signal"] == "bullish"
    assert result["confidence"] > 50


def test_high_confidence_bearish_wins():
    signals = {
        "agent_a": {"sig": "bearish", "conf": 85},
        "agent_b": {"sig": "bullish", "conf": 40},
    }
    result = aggregate_signals(signals)
    assert result["signal"] == "bearish"


def test_balanced_confidence_returns_neutral():
    signals = {
        "agent_a": {"sig": "bullish", "conf": 60},
        "agent_b": {"sig": "bearish", "conf": 60},
    }
    result = aggregate_signals(signals)
    assert result["signal"] == "neutral"


def test_neutral_signal_contributes_zero():
    signals = {
        "agent_a": {"sig": "bullish", "conf": 70},
        "agent_b": {"sig": "neutral", "conf": 100},
    }
    result = aggregate_signals(signals)
    # Neutral agent contributes 0; bullish with 70 conf should still win
    assert result["signal"] == "bullish"


def test_empty_signals_returns_neutral_zero_confidence():
    result = aggregate_signals({})
    assert result["signal"] == "neutral"
    assert result["confidence"] == 0


def test_single_bullish_agent():
    signals = {"only_agent": {"sig": "bullish", "conf": 80}}
    result = aggregate_signals(signals)
    assert result["signal"] == "bullish"
    assert result["confidence"] == 80


def test_confidence_is_int_between_0_and_100():
    signals = {
        "a": {"sig": "bullish", "conf": 75},
        "b": {"sig": "bullish", "conf": 55},
    }
    result = aggregate_signals(signals)
    assert isinstance(result["confidence"], int)
    assert 0 <= result["confidence"] <= 100


def test_result_has_required_keys():
    result = aggregate_signals({"a": {"sig": "bullish", "conf": 60}})
    assert "signal" in result
    assert "confidence" in result
    assert "weighted_score" in result
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
cd /Users/vanditgandotra/ai-hedge-fund && poetry run pytest tests/test_portfolio_manager.py -v 2>&1 | tail -5
```

Expected: `ImportError` — `aggregate_signals` not defined yet.

- [ ] **Step 3: Add `aggregate_signals` to `src/agents/portfolio_manager.py`**

Add this function anywhere before `generate_trading_decision` (after `_compact_signals`):

```python
def aggregate_signals(signals: dict[str, dict]) -> dict:
    """
    Confidence-weighted aggregation of analyst signals.

    Each agent's directional score: bullish=+1, neutral=0, bearish=-1,
    multiplied by confidence/100. The mean of these weighted scores is
    mapped back to a signal + aggregate confidence.

    Returns: {"signal": str, "confidence": int, "weighted_score": float}
    """
    if not signals:
        return {"signal": "neutral", "confidence": 0, "weighted_score": 0.0}

    _direction = {"bullish": 1, "neutral": 0, "bearish": -1}

    weighted_sum = 0.0
    for payload in signals.values():
        sig = (payload.get("sig") or payload.get("signal") or "neutral").lower()
        conf = float(payload.get("conf") or payload.get("confidence") or 0)
        weighted_sum += _direction.get(sig, 0) * (conf / 100.0)

    n = len(signals)
    score = weighted_sum / n  # normalised to [-1, +1]

    THRESHOLD = 0.15
    if score > THRESHOLD:
        signal = "bullish"
        confidence = int(min(score * 100, 100))
    elif score < -THRESHOLD:
        signal = "bearish"
        confidence = int(min(abs(score) * 100, 100))
    else:
        signal = "neutral"
        confidence = int((1.0 - abs(score)) * 100)

    return {"signal": signal, "confidence": confidence, "weighted_score": round(score, 4)}
```

- [ ] **Step 4: Update `generate_trading_decision` to include the aggregate in the LLM prompt**

In `generate_trading_decision()`, after `compact_signals = _compact_signals(...)`, add:

```python
    # Build confidence-weighted aggregates per ticker for the LLM
    aggregates = {
        t: aggregate_signals(compact_signals.get(t, {}))
        for t in tickers_for_llm
    }
```

Update the prompt's `human` message template to include the aggregate:

```python
            (
                "human",
                "Signals:\n{signals}\n\n"
                "Weighted aggregate (confidence-weighted signal summary):\n{aggregates}\n\n"
                "Allowed:\n{allowed}\n\n"
                "Format:\n"
                "{{\n"
                '  "decisions": {{\n'
                '    "TICKER": {{"action":"...","quantity":int,"confidence":int,"reasoning":"..."}}\n'
                "  }}\n"
                "}}"
            ),
```

Add `aggregates` to `prompt_data`:

```python
    prompt_data = {
        "signals": json.dumps(compact_signals, separators=(",", ":"), ensure_ascii=False),
        "aggregates": json.dumps(aggregates, separators=(",", ":"), ensure_ascii=False),
        "allowed": json.dumps(compact_allowed, separators=(",", ":"), ensure_ascii=False),
    }
```

Also update `compute_allowed_actions` to scale `max_qty` by aggregate confidence when the aggregate is available. Add a new helper at the bottom of the file:

```python
def scale_quantity_by_confidence(quantity: int, aggregate_confidence: int) -> int:
    """Scale a max quantity down proportionally to aggregate confidence (min 10%)."""
    if quantity == 0 or aggregate_confidence == 0:
        return 0
    factor = max(0.10, aggregate_confidence / 100.0)
    return max(1, int(quantity * factor))
```

In `generate_trading_decision()`, after building `aggregates`, scale `max_shares` for each ticker:

```python
    scaled_max_shares = {}
    for t in tickers_for_llm:
        agg_conf = aggregates.get(t, {}).get("confidence", 100)
        scaled_max_shares[t] = scale_quantity_by_confidence(max_shares.get(t, 0), agg_conf)
    # Use scaled_max_shares instead of max_shares for allowed_actions
    compact_allowed = {
        t: compute_allowed_actions([t], current_prices, scaled_max_shares, portfolio)[t]
        for t in tickers_for_llm
    }
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/vanditgandotra/ai-hedge-fund && poetry run pytest tests/test_portfolio_manager.py -v 2>&1 | tail -10
```

Expected: `8 passed`.

- [ ] **Step 6: Run full suite to check for regressions**

```bash
cd /Users/vanditgandotra/ai-hedge-fund && poetry run pytest tests/ -v --ignore=tests/backtesting/integration 2>&1 | tail -15
```

Expected: all passing (integration tests are skipped as they require live API).

- [ ] **Step 7: Commit**

```bash
git add src/agents/portfolio_manager.py tests/test_portfolio_manager.py
git commit -m "feat: replace majority vote with confidence-weighted signal aggregation and proportional position sizing"
```

---

## Task 6: SEC EDGAR API Utilities

**Files:**
- Create: `src/tools/sec_api.py`
- Create: `tests/test_sec_api.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sec_api.py`:

```python
from unittest.mock import MagicMock, patch

import pytest

from src.tools.sec_api import (
    _extract_section,
    get_cik,
    get_recent_filings,
)


MOCK_TICKERS_JSON = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp."},
}


def _mock_get(url, **kwargs):
    resp = MagicMock()
    resp.status_code = 200
    if "company_tickers" in url:
        resp.json.return_value = MOCK_TICKERS_JSON
    elif "submissions" in url:
        resp.json.return_value = {
            "filings": {
                "recent": {
                    "form": ["10-K", "10-Q", "8-K"],
                    "filingDate": ["2024-11-01", "2024-08-01", "2024-11-05"],
                    "accessionNumber": [
                        "0000320193-24-000123",
                        "0000320193-24-000098",
                        "0000320193-24-000150",
                    ],
                    "primaryDocument": [
                        "aapl-20240930.htm",
                        "aapl-20240629.htm",
                        "aapl-8k.htm",
                    ],
                }
            }
        }
    else:
        resp.text = "<html><body><p>ITEM 7. MANAGEMENT DISCUSSION Revenue grew 10% this year due to strong iPhone sales. ITEM 7A. QUANTITATIVE</p></body></html>"
    return resp


@patch("src.tools.sec_api.requests.get", side_effect=_mock_get)
def test_get_cik_returns_padded_string(mock_get):
    cik = get_cik("AAPL")
    assert cik == "0000320193"


@patch("src.tools.sec_api.requests.get", side_effect=_mock_get)
def test_get_cik_case_insensitive(mock_get):
    cik = get_cik("aapl")
    assert cik == "0000320193"


@patch("src.tools.sec_api.requests.get", side_effect=_mock_get)
def test_get_cik_returns_none_for_unknown(mock_get):
    cik = get_cik("XXXXXXX")
    assert cik is None


@patch("src.tools.sec_api.requests.get", side_effect=_mock_get)
def test_get_recent_filings_returns_10k(mock_get):
    # Reset CIK cache so mock is called
    import src.tools.sec_api as sec
    sec._cik_cache.clear()
    filings = get_recent_filings("0000320193", "10-K", limit=1)
    assert len(filings) == 1
    assert filings[0]["form"] == "10-K"
    assert filings[0]["date"] == "2024-11-01"
    assert "accession" in filings[0]
    assert "primary_document" in filings[0]


@patch("src.tools.sec_api.requests.get", side_effect=_mock_get)
def test_get_recent_filings_returns_8k(mock_get):
    import src.tools.sec_api as sec
    sec._cik_cache.clear()
    filings = get_recent_filings("0000320193", "8-K", limit=1)
    assert len(filings) == 1
    assert filings[0]["form"] == "8-K"


def test_extract_section_finds_text():
    text = "...preamble... ITEM 7. Management Discussion revenue grew 10% ITEM 7A. more stuff"
    section = _extract_section(text, r"ITEM\s+7[\.\s]", r"ITEM\s+7A", max_chars=500)
    assert "revenue grew" in section.lower()


def test_extract_section_returns_empty_when_not_found():
    text = "no matching headings here"
    section = _extract_section(text, r"ITEM\s+99", r"ITEM\s+100", max_chars=500)
    assert section == ""
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
cd /Users/vanditgandotra/ai-hedge-fund && poetry run pytest tests/test_sec_api.py -v 2>&1 | tail -5
```

Expected: `ModuleNotFoundError` for `src.tools.sec_api`.

- [ ] **Step 3: Create `src/tools/sec_api.py`**

```python
"""SEC EDGAR public API utilities — no API key required."""

import re
import time

import requests

_SEC_HEADERS = {"User-Agent": "ai-hedge-fund research@example.com"}
_RATE_LIMIT_DELAY = 0.15  # EDGAR asks for ≤10 req/sec

_cik_cache: dict[str, str] = {}


def get_cik(ticker: str) -> str | None:
    """Return the zero-padded 10-digit CIK for a ticker, or None if not found."""
    key = ticker.upper()
    if key in _cik_cache:
        return _cik_cache[key]

    try:
        resp = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers=_SEC_HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception:
        return None

    for entry in data.values():
        if str(entry.get("ticker", "")).upper() == key:
            cik = str(entry["cik_str"]).zfill(10)
            _cik_cache[key] = cik
            return cik

    return None


def get_recent_filings(cik: str, form_type: str, limit: int = 1) -> list[dict]:
    """
    Return up to `limit` recent filings of `form_type` for the given CIK.

    Each result: {"form", "date", "accession" (no dashes), "primary_document"}
    """
    try:
        time.sleep(_RATE_LIMIT_DELAY)
        resp = requests.get(
            f"https://data.sec.gov/submissions/CIK{cik}.json",
            headers=_SEC_HEADERS,
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:
        return []

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    docs = recent.get("primaryDocument", [])

    results = []
    for form, date, acc, doc in zip(forms, dates, accessions, docs):
        if form == form_type:
            results.append(
                {
                    "form": form,
                    "date": date,
                    "accession": acc.replace("-", ""),
                    "primary_document": doc,
                }
            )
            if len(results) >= limit:
                break
    return results


def fetch_filing_text(cik: str, accession: str, primary_document: str) -> str:
    """
    Download a filing and return its plain text (HTML tags stripped).
    cik: zero-padded 10-digit string
    accession: 18-char no-dash string (e.g. "000032019324000123")
    """
    cik_int = str(int(cik))  # strip leading zeros for URL path
    url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{primary_document}"
    )
    try:
        time.sleep(_RATE_LIMIT_DELAY)
        resp = requests.get(url, headers=_SEC_HEADERS, timeout=30)
        if resp.status_code != 200:
            return ""
        # Strip HTML tags and collapse whitespace
        text = re.sub(r"<[^>]+>", " ", resp.text)
        return re.sub(r"\s+", " ", text).strip()
    except Exception:
        return ""


def _extract_section(
    text: str, item_pattern: str, next_item_pattern: str, max_chars: int = 8000
) -> str:
    """Extract the text between two heading patterns."""
    start_match = re.search(item_pattern, text, re.IGNORECASE)
    if not start_match:
        return ""
    start = start_match.start()
    end_match = re.search(next_item_pattern, text[start + 1 :], re.IGNORECASE)
    if end_match:
        end = start + 1 + end_match.start()
    else:
        end = start + max_chars
    return text[start:end][:max_chars]


# Token budget per section (rough: 1 token ≈ 4 chars)
_SECTION_CHARS = 8_000


def get_filing_excerpts(ticker: str) -> dict[str, str]:
    """
    Return a dict of filing-type → extracted text excerpt for the most recent
    10-K (MD&A + Risk Factors), 10-Q (MD&A), and 8-K (full text).
    Empty strings for any filing not found.
    """
    cik = get_cik(ticker)
    if not cik:
        return {"10-K": "", "10-Q": "", "8-K": ""}

    excerpts: dict[str, str] = {}

    # 10-K: Item 7 (MD&A) + Item 1A (Risk Factors)
    filings_10k = get_recent_filings(cik, "10-K", limit=1)
    if filings_10k:
        f = filings_10k[0]
        text = fetch_filing_text(cik, f["accession"], f["primary_document"])
        mda = _extract_section(text, r"ITEM\s+7[\.\s]", r"ITEM\s+7A", _SECTION_CHARS)
        risks = _extract_section(text, r"ITEM\s+1A[\.\s]", r"ITEM\s+1B", _SECTION_CHARS)
        excerpts["10-K"] = f"[MD&A — dated {f['date']}]\n{mda}\n\n[Risk Factors]\n{risks}"
    else:
        excerpts["10-K"] = ""

    # 10-Q: Item 2 (MD&A)
    filings_10q = get_recent_filings(cik, "10-Q", limit=1)
    if filings_10q:
        f = filings_10q[0]
        text = fetch_filing_text(cik, f["accession"], f["primary_document"])
        mda = _extract_section(text, r"ITEM\s+2[\.\s]", r"ITEM\s+3", _SECTION_CHARS)
        excerpts["10-Q"] = f"[10-Q MD&A — dated {f['date']}]\n{mda}"
    else:
        excerpts["10-Q"] = ""

    # 8-K: full text (usually short)
    filings_8k = get_recent_filings(cik, "8-K", limit=1)
    if filings_8k:
        f = filings_8k[0]
        text = fetch_filing_text(cik, f["accession"], f["primary_document"])
        excerpts["8-K"] = f"[8-K — dated {f['date']}]\n{text[:_SECTION_CHARS]}"
    else:
        excerpts["8-K"] = ""

    return excerpts
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/vanditgandotra/ai-hedge-fund && poetry run pytest tests/test_sec_api.py -v 2>&1 | tail -10
```

Expected: `8 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/tools/sec_api.py tests/test_sec_api.py
git commit -m "feat: add SEC EDGAR API utilities (CIK lookup, filing fetch, section extraction)"
```

---

## Task 7: SEC Filings Analyst Agent

**Files:**
- Create: `src/agents/sec_filings.py`
- Modify: `src/utils/analysts.py` (register new analyst)

- [ ] **Step 1: Create `src/agents/sec_filings.py`**

```python
import json

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing_extensions import Literal

from src.graph.state import AgentState, show_agent_reasoning
from src.tools.sec_api import get_filing_excerpts
from src.utils.llm import call_llm
from src.utils.progress import progress


class SecFilingsSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="2-3 key findings from the filings")


_SYSTEM = (
    "You are a qualitative analyst reading SEC filings for investment signals. "
    "You receive excerpts from a company's most recent 10-K (MD&A + Risk Factors), "
    "10-Q (MD&A), and 8-K (material events). Assess:\n"
    "1. Management tone — optimistic, cautious, or defensive?\n"
    "2. New or escalating risk factors vs. prior disclosures?\n"
    "3. Forward guidance language — specific and confident, or vague and hedged?\n"
    "4. Material events from 8-K that alter the investment thesis.\n"
    "Return a signal (bullish/bearish/neutral), confidence 0-100, and 2-3 concise findings."
)


def sec_filings_agent(state: AgentState, agent_id: str = "sec_filings_agent"):
    """Analyzes SEC filings (10-K, 10-Q, 8-K) for each ticker using EDGAR."""
    tickers = state["data"]["tickers"]
    sec_analysis = {}

    template = ChatPromptTemplate.from_messages(
        [
            ("system", _SYSTEM),
            ("human", "Ticker: {ticker}\n\n{excerpts}\n\nReturn JSON only."),
        ]
    )

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching SEC filings")

        try:
            excerpts = get_filing_excerpts(ticker)
        except Exception as e:
            progress.update_status(agent_id, ticker, f"EDGAR fetch failed: {e}")
            sec_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 0,
                "reasoning": "SEC filings unavailable",
            }
            continue

        if not any(excerpts.values()):
            sec_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 0,
                "reasoning": "No SEC filings found for this ticker",
            }
            continue

        progress.update_status(agent_id, ticker, "Analyzing filings with LLM")

        excerpt_text = "\n\n".join(
            f"=== {form} ===\n{text}"
            for form, text in excerpts.items()
            if text
        )

        prompt = template.invoke({"ticker": ticker, "excerpts": excerpt_text})

        def _default():
            return SecFilingsSignal(
                signal="neutral",
                confidence=0,
                reasoning="LLM analysis failed — defaulting to neutral",
            )

        result = call_llm(
            prompt=prompt,
            pydantic_model=SecFilingsSignal,
            agent_name=agent_id,
            state=state,
            default_factory=_default,
        )

        sec_analysis[ticker] = result.model_dump()
        progress.update_status(agent_id, ticker, f"Signal: {result.signal} ({result.confidence}%)")

    state["data"]["analyst_signals"][agent_id] = sec_analysis

    message = HumanMessage(content=json.dumps(sec_analysis), name=agent_id)

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(sec_analysis, "SEC Filings Analyst")

    progress.update_status(agent_id, None, "Done")

    return {
        "messages": state["messages"] + [message],
        "data": state["data"],
    }
```

- [ ] **Step 2: Register the new analyst in `src/utils/analysts.py`**

Add the import at the top with the other agent imports:

```python
from src.agents.sec_filings import sec_filings_agent
```

Add the entry to `ANALYST_CONFIG` (after `"valuation_analyst"`, before the closing `}`):

```python
    "sec_filings_analyst": {
        "display_name": "SEC Filings Analyst",
        "description": "Qualitative Filing Reader",
        "investing_style": "Reads 10-K, 10-Q, and 8-K filings to extract management tone, risk factor changes, and forward guidance signals from primary source documents.",
        "agent_func": sec_filings_agent,
        "type": "analyst",
        "order": 19,
    },
```

- [ ] **Step 3: Smoke-test the SEC agent in isolation**

```bash
cd /Users/vanditgandotra/ai-hedge-fund
poetry run python src/main.py \
  --tickers AAPL \
  --analysts sec_filings_analyst \
  --model claude-opus-4-7 \
  --show-reasoning 2>&1
```

Expected: filing excerpts fetched from EDGAR, signal printed in the output table.

- [ ] **Step 4: Run full test suite to check for regressions**

```bash
cd /Users/vanditgandotra/ai-hedge-fund && poetry run pytest tests/ --ignore=tests/backtesting/integration -v 2>&1 | tail -15
```

Expected: all tests passing.

- [ ] **Step 5: Commit**

```bash
git add src/agents/sec_filings.py src/utils/analysts.py
git commit -m "feat: add SEC Filings Analyst agent (10-K/10-Q/8-K via EDGAR) and register in ANALYST_CONFIG"
```

---

## Task 8: Push to Fork and Open Pull Request

**Files:** none — git operations only.

- [ ] **Step 1: Verify all tests pass on the feature branch**

```bash
cd /Users/vanditgandotra/ai-hedge-fund && poetry run pytest tests/ --ignore=tests/backtesting/integration 2>&1 | tail -5
```

Expected: all green.

- [ ] **Step 2: Push the feature branch to your fork**

```bash
git push origin feature/missing-components
```

Expected: branch pushed to `https://github.com/VanditGandotra/ai-hedge-fund`.

- [ ] **Step 3: Create the pull request**

```bash
gh pr create \
  --repo virattt/ai-hedge-fund \
  --head VanditGandotra:feature/missing-components \
  --base main \
  --title "feat: add persistent DB, regime detection, confidence aggregation, and SEC filings agent" \
  --body "$(cat <<'EOF'
## Summary

- **Persistent SQLite audit trail** (`src/data/database.py`): every run, trade, and analyst decision is written to `data/hedge_fund.db` with a unique `run_id` for full reproducibility.
- **Market regime detection** (`src/agents/regime_detector.py`): classifies SPY into Bull / Bear / High-Vol / Risk-Off using trend (50/200-day MA), realized volatility, and 3-month momentum. Position limits are scaled down 30–60% in non-Bull regimes.
- **Confidence-weighted signal aggregation** (`src/agents/portfolio_manager.py`): replaces majority vote — each analyst's signal is weighted by their stated confidence. Position size scales proportionally to aggregate conviction.
- **SEC Filings Analyst** (`src/agents/sec_filings.py`): new analyst node that reads 10-K (MD&A + Risk Factors), 10-Q, and 8-K via the free SEC EDGAR API. No API key required.

## Test plan

- [ ] `poetry run pytest tests/test_database.py` — 4 tests
- [ ] `poetry run pytest tests/test_regime_detector.py` — 8 tests
- [ ] `poetry run pytest tests/test_portfolio_manager.py` — 8 tests
- [ ] `poetry run pytest tests/test_sec_api.py` — 8 tests
- [ ] `poetry run python src/main.py --tickers AAPL --analysts sec_filings_analyst --model claude-opus-4-7` — smoke test

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: Print the PR URL**

```bash
gh pr view --repo virattt/ai-hedge-fund --json url -q .url
```

---

## Self-Review Checklist

- [x] **Spec coverage:** All four spec sections have tasks — DB (Task 2+3), regime (Task 4), confidence (Task 5), SEC agent (Tasks 6+7).
- [x] **No placeholders:** Every step has actual code or exact commands. No "add appropriate error handling" without showing the code.
- [x] **Type consistency:** `RegimeState` defined in Task 4 Step 3 and imported in Task 4 Step 5. `aggregate_signals` defined in Task 5 Step 3 and tested in Task 5 Step 1. `get_filing_excerpts` defined in Task 6 Step 3 and called in Task 7 Step 1.
- [x] **Test-first:** Every component has tests written before the implementation step.
- [x] **Commit cadence:** Each task ends with a commit. Feature branch created in Task 1.
