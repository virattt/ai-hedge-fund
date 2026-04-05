"""Service for finviz-style stock screening using finvizfinance."""
import asyncio
import logging

logger = logging.getLogger(__name__)

# In-memory cache for filter metadata (rarely changes)
_filters_cache: dict | None = None


def _get_screener_class(view: str):
    """Return the appropriate finvizfinance screener class for the given view."""
    from finvizfinance.screener.overview import Overview
    from finvizfinance.screener.valuation import Valuation
    from finvizfinance.screener.financial import Financial
    from finvizfinance.screener.technical import Technical
    from finvizfinance.screener.performance import Performance
    from finvizfinance.screener.ownership import Ownership

    view_map = {
        "overview": Overview,
        "valuation": Valuation,
        "financial": Financial,
        "technical": Technical,
        "performance": Performance,
        "ownership": Ownership,
    }
    cls = view_map.get(view.lower())
    if cls is None:
        raise ValueError(f"Unknown view: {view}. Must be one of {list(view_map.keys())}")
    return cls


def _fetch_filters() -> dict:
    """Build filter metadata from finvizfinance's internal dictionaries."""
    from finvizfinance.screener.base import filter_dict, signal_dict, order_dict

    filters: dict[str, list[str]] = {}
    for name, info in filter_dict.items():
        options = list(info["option"].keys())
        # Remove the "Any" placeholder — frontend adds its own
        filters[name] = [o for o in options if o != "Any"]

    signals = list(signal_dict.keys())
    orders = list(order_dict.keys())

    return {
        "filters": filters,
        "signals": signals,
        "orders": orders,
    }


async def get_screener_filters() -> dict:
    """Return filter metadata, cached after first call."""
    global _filters_cache
    if _filters_cache is not None:
        return _filters_cache
    result = _fetch_filters()
    _filters_cache = result
    return result


def _run_screener_sync(
    filters_dict: dict[str, str],
    signal: str,
    ticker: str,
    order: str,
    ascend: bool,
    limit: int,
    view: str,
) -> dict:
    """Run the screener query synchronously."""
    cls = _get_screener_class(view)
    screener = cls()

    kwargs: dict = {}
    if filters_dict:
        kwargs["filters_dict"] = filters_dict
    if signal:
        kwargs["signal"] = signal
    if ticker:
        kwargs["ticker"] = ticker
    if kwargs:
        screener.set_filter(**kwargs)

    df = screener.screener_view(order=order, ascend=ascend, limit=limit, verbose=0)

    if df is None or df.empty:
        return {"columns": [], "rows": [], "total": 0}

    columns = list(df.columns)
    rows = df.fillna("").to_dict(orient="records")
    return {"columns": columns, "rows": rows, "total": len(rows)}


async def run_screener(
    filters_dict: dict[str, str],
    signal: str = "",
    ticker: str = "",
    order: str = "Ticker",
    ascend: bool = True,
    limit: int = 200,
    view: str = "overview",
) -> dict:
    """Run a screener query asynchronously."""
    return await asyncio.to_thread(
        _run_screener_sync,
        filters_dict,
        signal,
        ticker,
        order,
        ascend,
        limit,
        view,
    )
