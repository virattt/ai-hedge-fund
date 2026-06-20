import pandas as pd

from src.data.models import Price
from src.tools.api import prices_to_df

EXPECTED_COLUMNS = ["open", "close", "high", "low", "volume", "time"]


class TestPricesToDf:
    """Test prices_to_df DataFrame conversion."""

    def test_converts_prices_to_dataframe(self):
        prices = [
            Price(open=1.0, close=2.0, high=3.0, low=0.5, volume=100, time="2024-01-01"),
            Price(open=2.0, close=3.0, high=4.0, low=1.5, volume=200, time="2024-01-02"),
        ]
        df = prices_to_df(prices)
        assert list(df.columns) == EXPECTED_COLUMNS
        assert df.index.name == "Date"
        assert len(df) == 2
        # Index should be sorted ascending by date
        assert df.index.is_monotonic_increasing

    def test_empty_prices_returns_empty_dataframe(self):
        """An empty price list (e.g. API failure or no data) must not raise."""
        df = prices_to_df([])
        assert isinstance(df, pd.DataFrame)
        assert df.empty
        assert list(df.columns) == EXPECTED_COLUMNS
        assert df.index.name == "Date"
        assert isinstance(df.index, pd.DatetimeIndex)
