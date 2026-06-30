"""Tests for backtest fixes -- deepcopy isolation and result fields.

We mock heavy transitive imports (langchain, langgraph) to avoid
needing those packages installed in the test environment.
"""

import asyncio
import copy
import sys
from types import SimpleNamespace, ModuleType
from unittest.mock import patch, MagicMock

import pandas as pd

# -----------------------------------------------------------------------
# Stub out heavy transitive imports before importing backtest_service
# -----------------------------------------------------------------------
_STUBS = {}


def _ensure_stub(name):
    """Insert a fake module into sys.modules if it doesn't exist."""
    if name not in sys.modules:
        mod = ModuleType(name)
        sys.modules[name] = mod
        _STUBS[name] = mod
    return sys.modules[name]


# langchain / langgraph stubs
for _mod_name in [
    "langchain_core",
    "langchain_core.messages",
    "langgraph",
    "langgraph.graph",
    "langchain_anthropic",
    "langchain_openai",
    "langchain_groq",
    "langchain_deepseek",
    "langchain_ollama",
    "langchain_google_genai",
    "langchain_gigachat",
    "langchain_xai",
    "langchain",
    "langchain.chat_models",
    "langchain_community",
    "langchain_community.chat_models",
]:
    _ensure_stub(_mod_name)

# Provide HumanMessage and END/StateGraph stubs so the import chain doesn't blow up
sys.modules["langchain_core.messages"].HumanMessage = type("HumanMessage", (), {})
sys.modules["langgraph.graph"].END = "END"
sys.modules["langgraph.graph"].StateGraph = MagicMock


def _create_portfolio(initial_cash, margin_requirement, tickers, portfolio_positions=None):
    """Lightweight replica of create_portfolio to avoid schema import chain."""
    portfolio = {
        "cash": initial_cash,
        "margin_requirement": margin_requirement,
        "margin_used": 0.0,
        "positions": {
            t: {
                "long": 0,
                "short": 0,
                "long_cost_basis": 0.0,
                "short_cost_basis": 0.0,
                "short_margin_used": 0.0,
            }
            for t in tickers
        },
        "realized_gains": {
            t: {"long": 0.0, "short": 0.0}
            for t in tickers
        },
    }
    return portfolio


# Now we can safely import after stubs are in place.
# But we still need to mock sub-modules that backtest_service imports at
# module level (graph, portfolio).
# Patch graph and portfolio modules *before* backtest_service is imported.
_graph_mod = ModuleType("app.backend.services.graph")
_graph_mod.run_graph_async = MagicMock()
_graph_mod.parse_hedge_fund_response = MagicMock(return_value={})
_graph_mod.extract_base_agent_key = lambda x: x
sys.modules["app.backend.services.graph"] = _graph_mod

# Patch portfolio module to avoid its deep schema import
_portfolio_mod = ModuleType("app.backend.services.portfolio")
_portfolio_mod.create_portfolio = _create_portfolio
sys.modules["app.backend.services.portfolio"] = _portfolio_mod

# Now import BacktestService
from app.backend.services.backtest_service import BacktestService


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def _build_service(start_date="2024-01-01", end_date="2024-01-03"):
    """Build a BacktestService with minimal dependencies."""
    portfolio = _create_portfolio(
        initial_cash=1000.0,
        margin_requirement=0.5,
        tickers=["AAPL"],
    )
    return BacktestService(
        graph=object(),
        portfolio=portfolio,
        tickers=["AAPL"],
        start_date=start_date,
        end_date=end_date,
        initial_capital=1000.0,
        request=SimpleNamespace(api_keys={}),
    )


# -----------------------------------------------------------------------
# Tests: deepcopy isolation
# -----------------------------------------------------------------------

def test_deepcopy_isolates_nested_portfolio_state():
    """Modifying a deepcopy must not affect the original portfolio."""
    portfolio = {
        "positions": {"AAPL": {"long": 1, "meta": {"source": "original"}}},
        "realized_gains": {"AAPL": {"long": 0.0}},
    }

    portfolio_copy = copy.deepcopy(portfolio)
    portfolio_copy["positions"]["AAPL"]["long"] = 99
    portfolio_copy["positions"]["AAPL"]["meta"]["source"] = "copy"

    assert portfolio["positions"]["AAPL"]["long"] == 1
    assert portfolio["positions"]["AAPL"]["meta"]["source"] == "original"


def test_backtest_uses_independent_portfolio_copy_for_graph():
    """Each iteration of run_backtest_async should pass a deepcopy to the graph."""
    service = _build_service()
    seen_long_positions = []

    async def fake_run_graph_async(**kwargs):
        seen_long_positions.append(kwargs["portfolio"]["positions"]["AAPL"]["long"])
        # Mutate the copy -- should NOT affect the original service.portfolio
        kwargs["portfolio"]["positions"]["AAPL"]["long"] = 99
        kwargs["portfolio"]["realized_gains"]["AAPL"]["long"] = 42.0
        return {}

    with patch.object(BacktestService, "prefetch_data", return_value=None), \
         patch("app.backend.services.backtest_service.get_price_data",
               return_value=pd.DataFrame({"close": [100.0]})), \
         patch("app.backend.services.backtest_service.run_graph_async",
               side_effect=fake_run_graph_async):
        result = asyncio.run(service.run_backtest_async())

    # Each call should see 0, because deepcopy gives a fresh copy each time
    assert seen_long_positions == [0, 0, 0]
    # Original portfolio should be untouched
    assert service.portfolio["positions"]["AAPL"]["long"] == 0
    assert service.portfolio["realized_gains"]["AAPL"]["long"] == 0.0
    assert len(result["results"]) == 3


# -----------------------------------------------------------------------
# Tests: result fields (skipped_days, error_count, total_days)
# -----------------------------------------------------------------------

def test_run_backtest_tracks_skipped_days_and_error_count():
    """When price data is missing, the result should track skipped days."""
    service = _build_service()

    with patch.object(BacktestService, "prefetch_data", return_value=None), \
         patch("app.backend.services.backtest_service.get_price_data",
               return_value=pd.DataFrame()):
        result = asyncio.run(service.run_backtest_async())

    assert result["total_days"] == 3
    assert result["error_count"] == 3
    assert len(result["skipped_days"]) == 3
    assert all(item["reason"] == "price_data_missing" for item in result["skipped_days"])
    assert result["results"] == []


def test_result_contains_required_metadata_keys():
    """The result dict must contain skipped_days, error_count, total_days."""
    service = _build_service()

    with patch.object(BacktestService, "prefetch_data", return_value=None), \
         patch("app.backend.services.backtest_service.get_price_data",
               return_value=pd.DataFrame()):
        result = asyncio.run(service.run_backtest_async())

    assert "skipped_days" in result
    assert "error_count" in result
    assert "total_days" in result
    assert isinstance(result["skipped_days"], list)
    assert isinstance(result["error_count"], int)
    assert isinstance(result["total_days"], int)


def test_run_backtest_warns_when_failed_days_exceed_threshold():
    """Logger should warn when error_count > 20% of total_days."""
    service = _build_service()

    with patch.object(BacktestService, "prefetch_data", return_value=None), \
         patch("app.backend.services.backtest_service.get_price_data",
               return_value=pd.DataFrame()), \
         patch("app.backend.services.backtest_service.logger.warning") as mock_warning:
        result = asyncio.run(service.run_backtest_async())

    assert result["error_count"] == 3
    mock_warning.assert_called_once_with(
        "Backtest encountered %s errors across %s trading days",
        3,
        3,
    )
