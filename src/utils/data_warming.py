"""Pre-warm the shared data cache before the analyst fan-out.

Why this exists
---------------
Analysts run concurrently (LangGraph fans ``start_node`` out to every selected
analyst). Each analyst asks for a different basket of financial data:

* ``get_financial_metrics`` — same shape, but agents pass different ``period``
  and ``limit`` values.
* ``search_line_items`` — each agent passes a *different* list of fields.

With a cold cache, every agent fires its own API request — for the rate-limited
financialdatasets API that wastes quota and adds latency. The cache layer
(:mod:`src.data.cache`) already de-duplicates *exact* and *subset* requests, but
field overlap across agents is low, so lazy caching alone only helps a little
(see ``tests/test_api_dedup.py``'s benchmark).

This module does the complementary job: it introspects the installed analyst
modules to learn, per ``(period, limit)``, the **union** of line items and the
**max** metrics limit any agent will request, then issues a single fetch per
distinct key *before* the analysts start. After warming, every analyst request
is a cache hit (the union ⊇ whatever the agent asks for), so the analyst fan-out
makes zero additional API calls.

Agents whose field lists are built from variables (not literals) can't be
introspected; they simply fall back to the lazy cache at run time — warm is a
pure optimisation, never a correctness requirement.
"""
from __future__ import annotations

import ast
import logging
import pathlib
from concurrent.futures import ThreadPoolExecutor
from typing import Any

logger = logging.getLogger(__name__)

_AGENTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "agents"


def _const(node: Any, default):
    return node.value if isinstance(node, ast.Constant) else default


def extract_agent_data_requests() -> list[dict]:
    """Scan ``src/agents/*.py`` and return every literal data request.

    Returns a list of dicts, each either::

        {"kind": "metrics", "period": str, "limit": int}
        {"kind": "line_items", "fields": list[str], "period": str, "limit": int}

    Calls whose field list is not a literal (e.g. built from a variable) are
    skipped — those agents just use the lazy cache instead of being pre-warmed.
    """
    requests: list[dict] = []
    for path in sorted(_AGENTS_DIR.glob("*.py")):
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            fname = node.func.id
            kws = {k.arg: k.value for k in node.keywords}

            if fname == "search_line_items" and len(node.args) >= 2 and isinstance(node.args[1], ast.List):
                try:
                    fields = list(ast.literal_eval(node.args[1]))
                except Exception:
                    continue
                requests.append(
                    {
                        "kind": "line_items",
                        "fields": fields,
                        "period": _const(kws.get("period"), "ttm"),
                        "limit": int(_const(kws.get("limit"), 10)),
                    }
                )
            elif fname == "get_financial_metrics":
                requests.append(
                    {
                        "kind": "metrics",
                        "period": _const(kws.get("period"), "ttm"),
                        "limit": int(_const(kws.get("limit"), 10)),
                    }
                )
    return requests


def compute_agent_data_needs() -> dict:
    """Aggregate :func:`extract_agent_data_requests` into a warm plan.

    Returns::

        {
            "metrics": {period: max_limit},                  # one fetch/period
            "line_items": {(period, limit): set(fields)},    # one fetch/key
        }
    """
    metrics: dict[str, int] = {}
    line_items: dict[tuple[str, int], set[str]] = {}
    for req in extract_agent_data_requests():
        if req["kind"] == "metrics":
            metrics[req["period"]] = max(metrics.get(req["period"], 0), req["limit"])
        else:
            key = (req["period"], req["limit"])
            line_items.setdefault(key, set()).update(req["fields"])
    return {"metrics": metrics, "line_items": line_items}


def warm_cache_for_tickers(
    tickers: list[str],
    end_date: str,
    api_key: str | None = None,
    max_workers: int = 8,
) -> None:
    """Pre-fetch each ticker's data into the shared cache.

    Call this from the workflow's entry node, before the analyst fan-out.
    Per-ticker/per-key failures are swallowed and logged: a missed warm only
    means the relevant agent fetches lazily later.
    """
    # Import here to avoid a circular import at module load time.
    from src.tools.api import get_financial_metrics, search_line_items

    needs = compute_agent_data_needs()

    def warm_one(ticker: str) -> None:
        for period, limit in needs["metrics"].items():
            try:
                get_financial_metrics(ticker, end_date, period=period, limit=limit, api_key=api_key)
            except Exception as e:  # noqa: BLE001 - never let warm break the run
                logger.warning("warm metrics failed for %s (%s): %s", ticker, period, e)
        for (period, limit), fields in needs["line_items"].items():
            if not fields:
                continue
            try:
                search_line_items(ticker, sorted(fields), end_date, period=period, limit=limit, api_key=api_key)
            except Exception as e:  # noqa: BLE001
                logger.warning("warm line_items failed for %s (%s/%s): %s", ticker, period, limit, e)

    tickers = list(tickers or [])
    if len(tickers) <= 1:
        for ticker in tickers:
            warm_one(ticker)
    else:
        with ThreadPoolExecutor(max_workers=min(max_workers, len(tickers))) as ex:
            list(ex.map(warm_one, tickers))
