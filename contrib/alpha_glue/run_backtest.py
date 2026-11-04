"""Backtest an ai-hedge-fund mandate on Yahoo, SEC and Alpha Vantage data, with an OpenAI model.

Run inside aihf's own environment, which has the ``hedge_fund`` package:

    ~/Documents/ai-hedge-fund/.venv/bin/python run_backtest.py \\
        ~/Documents/ai-hedge-fund/hedge_fund/strategies/deep-value.yaml \\
        --universe AAPL,NVDA,MSFT --start 2026-07-06 --end 2026-10-26 --model gpt-6-luna

Same as ``aihf backtest`` except for two things: the data client (alpha_client.py, so no
Financial Datasets key or wallet is needed), and OpenAI model ids outside aihf's short
list, such as gpt-6-luna, are routed to OpenAI instead of falling through to Anthropic.
Like aihf's own backtest, the investor agents see blinded prompts. It never trades.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hedge_fund.llm.client as llm_client  # noqa: E402
from hedge_fund.backtesting import backtest_fund, save_result  # noqa: E402
from hedge_fund.data.cached import CachedDataClient  # noqa: E402
from hedge_fund.fund import Fund, load_spec, normalize_universe  # noqa: E402
from hedge_fund.scorecard import score  # noqa: E402

from alpha_client import AlphaClient  # noqa: E402

class FreshEarningsCache(CachedDataClient):
    """aihf's cache treats answers with no date, such as earnings history, as final unless the client
    is live, so a quarter reported after the first run is never seen (virattt/ai-hedge-fund#724).
    Here an answer with no date goes stale after a day, so it is asked for again."""

    DATELESS_TTL = 24 * 3600

    def _fresh(self, hit, method, params):
        if params.get("end_date") is None and "fetched_at" in hit:
            from datetime import datetime, timezone

            age = (datetime.now(timezone.utc) - datetime.fromisoformat(hit["fetched_at"]).astimezone(timezone.utc)).total_seconds()
            return age < self.DATELESS_TTL
        return super()._fresh(hit, method, params)


_registry_provider = llm_client.provider_for
llm_client.provider_for = lambda model: "OpenAI" if model.startswith("gpt-") else _registry_provider(model)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("mandate")
    parser.add_argument("--universe", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--model", default=os.environ.get("HEDGE_FUND_LLM_MODEL", "gpt-6-luna"))
    args = parser.parse_args()
    os.environ["HEDGE_FUND_LLM_MODEL"] = args.model

    spec = load_spec(os.path.expanduser(args.mandate))
    universe = normalize_universe(args.universe.replace(",", " ").split())
    print(f"{spec.name}: {args.start} to {args.end}, {spec.rebalance} rebalance vs {spec.benchmark}, {', '.join(universe)}, model {args.model}", flush=True)

    with AlphaClient() as raw:
        result = backtest_fund(Fund(spec, blind=True), args.start, args.end, FreshEarningsCache(raw), universe)

    m = result.metrics
    print(f"return {m.total_return_pct:+.1%} vs {spec.benchmark} {m.benchmark_return_pct:+.1%}, sharpe {m.sharpe_ratio:.2f}, "
          f"max drawdown {m.max_drawdown_pct:.1%}, {m.n_cycles} rebalances, {m.n_orders} orders, trading cost {m.trading_cost:,.0f}")
    print(f"saved to {save_result(result)}")
    card = score(result.records)
    print(card.model_dump_json(indent=1)[:1500])


if __name__ == "__main__":
    main()
