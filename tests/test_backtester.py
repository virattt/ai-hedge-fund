import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.backtester import Backtester


class TestBacktester:
    """Test suite for the backtesting engine."""

    @pytest.fixture
    def sample_price_data(self):
        """Create sample price data for testing."""
        dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
        data = []
        
        for i, date in enumerate(dates):
            # Create realistic price movements
            base_price = 100
            price = base_price + np.sin(i * 0.1) * 10 + np.random.normal(0, 2)
            
            data.append({
                'date': date,
                'open': price - 0.5,
                'high': price + 1,
                'low': price - 1,
                'close': price,
                'volume': 1000000 + np.random.randint(-100000, 100000)
            })
        
        return pd.DataFrame(data)

    @pytest.fixture
    def backtester(self):
        """Create a backtester instance."""
        return Backtester(
            initial_cash=100000,
            commission_rate=0.001,
            slippage_rate=0.0001
        )

    def test_backtester_initialization(self, backtester):
        """Test backtester initialization."""
        assert backtester.initial_cash == 100000
        assert backtester.commission_rate == 0.001
        assert backtester.slippage_rate == 0.0001
        assert backtester.current_cash == 100000
        assert backtester.positions == {}
        assert backtester.trades == []

    def test_backtester_buy_signal(self, backtester, sample_price_data, sample_signals):
        """Test executing a buy signal."""
        # Setup
        price_data = sample_price_data.head(10)
        signals = sample_signals.head(1)
        signals.iloc[0, signals.columns.get_loc('signal')] = 'buy'
        signals.iloc[0, signals.columns.get_loc('confidence')] = 0.8
        
        # Execute trade
        backtester.execute_trades(signals, price_data)
        
        # Verify trade execution
        assert len(backtester.trades) == 1
        assert backtester.trades[0]['action'] == 'buy'
        assert 'AAPL' in backtester.positions
        assert backtester.current_cash < 100000  # Cash reduced by purchase

    def test_backtester_sell_signal(self, backtester, sample_price_data, sample_signals):
        """Test executing a sell signal."""
        # First buy to establish position
        price_data = sample_price_data.head(10)
        
        # Create initial position
        backtester.positions['AAPL'] = {
            'quantity': 100,
            'avg_price': 100.0,
            'total_cost': 10000.0
        }
        
        # Create sell signal
        signals = sample_signals.head(1)
        signals.iloc[0, signals.columns.get_loc('signal')] = 'sell'
        signals.iloc[0, signals.columns.get_loc('confidence')] = 0.8
        
        # Execute trade
        backtester.execute_trades(signals, price_data)
        
        # Verify trade execution
        assert len(backtester.trades) == 1
        assert backtester.trades[0]['action'] == 'sell'
        assert backtester.current_cash > 100000  # Cash increased by sale

    def test_backtester_hold_signal(self, backtester, sample_price_data, sample_signals):
        """Test executing a hold signal."""
        # Setup
        price_data = sample_price_data.head(10)
        signals = sample_signals.head(1)
        signals.iloc[0, signals.columns.get_loc('signal')] = 'hold'
        
        initial_cash = backtester.current_cash
        initial_trades = len(backtester.trades)
        
        # Execute trade
        backtester.execute_trades(signals, price_data)
        
        # Verify no trade executed
        assert len(backtester.trades) == initial_trades
        assert backtester.current_cash == initial_cash

    def test_backtester_commission_calculation(self, backtester, sample_price_data, sample_signals):
        """Test commission calculation on trades."""
        # Setup
        price_data = sample_price_data.head(10)
        signals = sample_signals.head(1)
        signals.iloc[0, signals.columns.get_loc('signal')] = 'buy'
        signals.iloc[0, signals.columns.get_loc('confidence')] = 0.8
        
        # Execute trade
        backtester.execute_trades(signals, price_data)
        
        # Verify commission applied
        trade = backtester.trades[0]
        assert 'commission' in trade
        assert trade['commission'] > 0

    def test_backtester_slippage_calculation(self, backtester, sample_price_data, sample_signals):
        """Test slippage calculation on trades."""
        # Setup
        price_data = sample_price_data.head(10)
        signals = sample_signals.head(1)
        signals.iloc[0, signals.columns.get_loc('signal')] = 'buy'
        signals.iloc[0, signals.columns.get_loc('confidence')] = 0.8
        
        # Execute trade
        backtester.execute_trades(signals, price_data)
        
        # Verify slippage applied
        trade = backtester.trades[0]
        assert 'slippage' in trade
        assert trade['slippage'] > 0

    def test_backtester_position_sizing(self, backtester, sample_price_data, sample_signals):
        """Test position sizing logic."""
        # Setup
        price_data = sample_price_data.head(10)
        signals = sample_signals.head(1)
        signals.iloc[0, signals.columns.get_loc('signal')] = 'buy'
        signals.iloc[0, signals.columns.get_loc('confidence')] = 0.8
        
        # Execute trade
        backtester.execute_trades(signals, price_data)
        
        # Verify position size is reasonable
        trade = backtester.trades[0]
        assert 'quantity' in trade
        assert trade['quantity'] > 0
        assert trade['quantity'] * trade['price'] < backtester.initial_cash

    def test_backtester_multiple_trades(self, backtester, sample_price_data, sample_signals):
        """Test executing multiple trades."""
        # Setup multiple signals
        signals = sample_signals.head(5)
        
        # Alternate buy and sell signals
        for i in range(len(signals)):
            if i % 2 == 0:
                signals.iloc[i, signals.columns.get_loc('signal')] = 'buy'
            else:
                signals.iloc[i, signals.columns.get_loc('signal')] = 'sell'
            signals.iloc[i, signals.columns.get_loc('confidence')] = 0.8
        
        # Execute trades
        backtester.execute_trades(signals, sample_price_data.head(10))
        
        # Verify multiple trades executed
        assert len(backtester.trades) > 1

    def test_backtester_portfolio_value_calculation(self, backtester, sample_price_data):
        """Test portfolio value calculation."""
        # Add some positions
        backtester.positions['AAPL'] = {
            'quantity': 100,
            'avg_price': 100.0,
            'total_cost': 10000.0
        }
        backtester.positions['GOOGL'] = {
            'quantity': 50,
            'avg_price': 150.0,
            'total_cost': 7500.0
        }
        
        # Calculate portfolio value
        portfolio_value = backtester.calculate_portfolio_value(sample_price_data.head(1))
        
        # Verify calculation
        assert portfolio_value > backtester.current_cash
        assert isinstance(portfolio_value, (int, float))

    def test_backtester_performance_metrics(self, backtester, sample_price_data, sample_signals):
        """Test performance metrics calculation."""
        # Execute some trades
        signals = sample_signals.head(10)
        for i in range(len(signals)):
            if i % 3 == 0:
                signals.iloc[i, signals.columns.get_loc('signal')] = 'buy'
            elif i % 3 == 1:
                signals.iloc[i, signals.columns.get_loc('signal')] = 'sell'
            signals.iloc[i, signals.columns.get_loc('confidence')] = 0.8
        
        backtester.execute_trades(signals, sample_price_data)
        
        # Calculate performance metrics
        metrics = backtester.calculate_performance_metrics(sample_price_data)
        
        # Verify metrics structure
        expected_metrics = [
            'total_return', 'annualized_return', 'sharpe_ratio',
            'max_drawdown', 'win_rate', 'profit_factor', 'total_trades'
        ]
        
        for metric in expected_metrics:
            assert metric in metrics

    def test_backtester_risk_metrics(self, backtester, sample_price_data, sample_signals):
        """Test risk metrics calculation."""
        # Execute trades
        signals = sample_signals.head(20)
        for i in range(len(signals)):
            signals.iloc[i, signals.columns.get_loc('signal')] = np.random.choice(['buy', 'sell'])
            signals.iloc[i, signals.columns.get_loc('confidence')] = 0.8
        
        backtester.execute_trades(signals, sample_price_data)
        
        # Calculate risk metrics
        risk_metrics = backtester.calculate_risk_metrics(sample_price_data)
        
        # Verify risk metrics structure
        expected_risk_metrics = [
            'volatility', 'var_95', 'cvar_95', 'beta', 'correlation_to_market'
        ]
        
        for metric in expected_risk_metrics:
            assert metric in risk_metrics

    def test_backtester_edge_cases(self, backtester):
        """Test backtester edge cases."""
        # Test with empty data
        empty_price_data = pd.DataFrame()
        empty_signals = pd.DataFrame()
        
        # Should handle empty data gracefully
        try:
            backtester.execute_trades(empty_signals, empty_price_data)
        except Exception:
            pytest.fail("Backtester should handle empty data gracefully")

    def test_backtester_insufficient_cash(self, backtester, sample_price_data, sample_signals):
        """Test behavior when insufficient cash for trade."""
        # Reduce cash to minimal amount
        backtester.current_cash = 100
        
        # Create buy signal
        signals = sample_signals.head(1)
        signals.iloc[0, signals.columns.get_loc('signal')] = 'buy'
        signals.iloc[0, signals.columns.get_loc('confidence')] = 0.8
        
        # Execute trade
        backtester.execute_trades(signals, sample_price_data.head(10))
        
        # Should handle insufficient cash gracefully
        # Either no trade executed or minimal position taken

    def test_backtester_duplicate_signals(self, backtester, sample_price_data, sample_signals):
        """Test handling of duplicate signals."""
        # Create duplicate buy signals
        signals = pd.concat([sample_signals.head(1), sample_signals.head(1)])
        for i in range(len(signals)):
            signals.iloc[i, signals.columns.get_loc('signal')] = 'buy'
            signals.iloc[i, signals.columns.get_loc('confidence')] = 0.8
        
        initial_trades = len(backtester.trades)
        
        # Execute trades
        backtester.execute_trades(signals, sample_price_data.head(10))
        
        # Should handle duplicates appropriately
        # Either execute both or skip duplicate

    def test_backtester_confidence_filtering(self, backtester, sample_price_data, sample_signals):
        """Test filtering trades by confidence level."""
        # Create low confidence signal
        signals = sample_signals.head(1)
        signals.iloc[0, signals.columns.get_loc('signal')] = 'buy'
        signals.iloc[0, signals.columns.get_loc('confidence')] = 0.2  # Low confidence
        
        initial_trades = len(backtester.trades)
        
        # Execute trades
        backtester.execute_trades(signals, sample_price_data.head(10))
        
        # Should filter low confidence trades
        # Depending on implementation, may or may not execute trade


if __name__ == "__main__":
    pytest.main([__file__])
