from src.backtesting.types import AgentOutput


class MockConfigurableAgent:
    """Mock agent that executes a predefined sequence of trading decisions."""
    
    def __init__(self, decision_sequence: list[dict], tickers: list[str]):
        """
        Args:
            decision_sequence: List of decision dicts for each day/call
            tickers: List of tickers to include in decisions
            
        Example:
            decision_sequence = [
                {"AAPL": {"action": "buy", "quantity": 100}, "MSFT": {"action": "buy", "quantity": 30}},
                {},  # Hold all (empty dict means hold)
                {"AAPL": {"action": "sell", "quantity": 30}},  # Partial sell
            ]
        """
        self.decision_sequence = decision_sequence
        self.tickers = tickers
        self.call_count = 0
    
    def __call__(self, **kwargs) -> AgentOutput:
        """Execute the predefined decision sequence."""
        tickers = kwargs.get("tickers", self.tickers)
        
        # Get decisions for current call
        if self.call_count < len(self.decision_sequence):
            day_decisions = self.decision_sequence[self.call_count]
        else:
            day_decisions = {}  # Default to hold if past sequence
        
        self.call_count += 1
        
        # Build full decision dict, defaulting to hold for any missing tickers
        decisions = {}
        for ticker in tickers:
            if ticker in day_decisions:
                decisions[ticker] = day_decisions[ticker]
            else:
                decisions[ticker] = {"action": "hold", "quantity": 0}
        
        return {
            "decisions": decisions,
            "analyst_signals": {}
        }