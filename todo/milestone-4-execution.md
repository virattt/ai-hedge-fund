# Milestone 4: Execution & Risk Improvements

**Goal:** Add slippage estimation and Kelly criterion position sizing to make backtests more realistic and risk management smarter.

**Risk:** Low — utility functions are pure math, modifications to existing agents are additive.

## Tasks

- [ ] Create `src/utils/execution.py`
  - `estimate_slippage(volume, order_size, volatility) -> float`
    - Square-root market impact model: `slippage = volatility * sqrt(order_size / volume)`
  - `kelly_position_size(win_rate, avg_win, avg_loss, portfolio_value, fraction=0.5) -> float`
    - Half-Kelly by default: `kelly_fraction = (win_rate / avg_loss) - ((1 - win_rate) / avg_win)`
    - Returns dollar amount, capped at `fraction * portfolio_value`
  - `calculate_effective_price(price, slippage_pct, action) -> float`
    - Buy: `price * (1 + slippage_pct)`, Sell: `price * (1 - slippage_pct)`
- [ ] Update `src/agents/risk_manager.py`
  - Add Kelly sizing as additional constraint alongside volatility-adjusted limit
  - Add slippage estimate to reasoning output
  - Does not change risk manager's signal format
- [ ] Update `src/agents/portfolio_manager.py`
  - Include slippage estimate info in LLM prompt context
  - PM can factor slippage into trade size decisions
- [ ] Update `src/backtesting/trader.py`
  - Use `calculate_effective_price()` instead of raw price in `execute_trade()`
  - Buy fills at slightly higher price, sell fills at slightly lower price
- [ ] Update `src/backtesting/engine.py`
  - Pass volume data to trade executor (needed for slippage calculation)
- [ ] Write tests in `tests/test_execution.py`
  - Unit tests for `estimate_slippage` with known inputs/outputs
  - Unit tests for `kelly_position_size` edge cases (0 win rate, extreme values)
  - Unit tests for `calculate_effective_price` buy/sell scenarios
- [ ] Backtest comparison: before vs after
  - Results should be slightly more conservative (slippage reduces returns)
  - Existing backtest tests still pass

## Files

| Action | File |
|--------|------|
| Create | `src/utils/execution.py` |
| Create | `tests/test_execution.py` |
| Modify | `src/agents/risk_manager.py` |
| Modify | `src/agents/portfolio_manager.py` |
| Modify | `src/backtesting/trader.py` |
| Modify | `src/backtesting/engine.py` |
