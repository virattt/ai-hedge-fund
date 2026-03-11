```python
import pytest

from src.backtesting.portfolio import Portfolio
import pandas as pd


@pytest.fixture()
def portfolio() -> Portfolio:
    return Portfolio(tickers=["AAPL", "MSFT"], initial_cash=100_000.0, margin_requirement=0.5)


@pytest.fixture()
def prices() -> dict[str, float]:
    return {"AAPL": 100.0, "MSFT": 200.0}


@pytest.fixture()
def price_df_factory():
    def _factory(closes: list[float]):
        # Minimal price DataFrame with a close column
        return pd.DataFrame({"close": closes})

    return _factory
```