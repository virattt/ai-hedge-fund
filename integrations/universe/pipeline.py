"""Universe build pipeline — orchestrates all stages and writes the artifact.

Stage 0  candidate pool: all tradable US equities -> cheap eligibility gates
Stage 1  price-based factor scoring on all survivors -> shortlist
Stage 2  API-backed factors (fundamentals, earnings, news) + Alpha
         Learnability on the shortlist -> final composite
Select   greedy diversified selection (sector caps + correlation limit)

Everything is computed as of an explicit date using only data available on
that date, so the same code builds today's live universe and historical
universes for validation backtests.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd

from integrations.universe.candidates import Candidate, bars_start_date, build_candidate_pool
from integrations.universe.config import UniverseConfig
from integrations.universe.data import UniverseDataSource
from integrations.universe.factors import stage1_factors, stage2_factors
from integrations.universe.factors.base import FactorContext
from integrations.universe.learnability import SignalReplayer, compute_learnability
from integrations.universe.models import TickerScore, UniverseSnapshot
from integrations.universe.scoring import score_candidates
from integrations.universe.select import select_universe
from integrations.universe.store import save_universe

logger = logging.getLogger(__name__)

_CAVEATS = [
    "Candidate pool comes from the broker's current asset master, so historical builds carry survivorship bias.",
    "Shortability flags (shortable/easy_to_borrow) are current-state, not point-in-time.",
    "No short-interest data source is available; crowding uses price/volume proxies.",
    "Spread is estimated from daily high/low bars (Corwin-Schultz), not historical quotes.",
]


def _make_context(candidate: Candidate, as_of: str, config: UniverseConfig) -> FactorContext:
    return FactorContext(
        ticker=candidate.symbol,
        as_of=as_of,
        config=config,
        prices=candidate.prices,
        shortable=candidate.shortable,
        easy_to_borrow=candidate.easy_to_borrow,
    )


def _enrich_shortlist(
    contexts: dict[str, FactorContext],
    source: UniverseDataSource,
    as_of: str,
) -> None:
    """Attach sector, fundamentals, earnings, and news data to the shortlist."""
    month_ago = (pd.Timestamp(as_of) - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
    for ticker, ctx in contexts.items():
        facts = source.get_company_facts(ticker)
        if facts:
            ctx.sector = facts.get("sector") or facts.get("industry")
        ctx.fundamentals = source.get_fundamentals(ticker, as_of)
        ctx.earnings_events = source.get_earnings_events(ticker, as_of)
        ctx.news_count_30d = source.get_news_count(ticker, month_ago, as_of)


def build_universe(
    source: UniverseDataSource,
    config: UniverseConfig,
    as_of: str,
    *,
    replayer: SignalReplayer | None = None,
    save: bool = True,
) -> UniverseSnapshot:
    """Run the full pipeline and (optionally) persist the snapshot."""
    logger.info("Building universe as of %s (target size %d)", as_of, config.size)

    # Stage 0 — candidate pool
    candidates = build_candidate_pool(source, config, as_of)
    contexts = {c.symbol: _make_context(c, as_of, config) for c in candidates}

    # Stage 1 — cheap factor scoring over the whole pool
    stage1_scores = score_candidates(contexts, stage1_factors(), config.factor_weights)
    shortlist = [s.ticker for s in stage1_scores[: config.stage2_size]]
    shortlist_contexts = {t: contexts[t] for t in shortlist}
    logger.info("Stage 1: scored %d candidates, shortlisted %d", len(stage1_scores), len(shortlist))

    # Stage 2 — enrich with API data + Alpha Learnability
    _enrich_shortlist(shortlist_contexts, source, as_of)

    if config.require_fundamentals:
        no_fundamentals = sorted(t for t, ctx in shortlist_contexts.items() if not ctx.fundamentals)
        for ticker in no_fundamentals:
            del shortlist_contexts[ticker]
        if no_fundamentals:
            logger.info(
                "Dropped %d shortlist tickers with no fundamentals filings "
                "(funds/trusts that slipped past name markers): %s",
                len(no_fundamentals),
                ", ".join(no_fundamentals),
            )

    if config.learnability_enabled and shortlist:
        spy_bars = source.get_bars(["SPY"], bars_start_date(as_of, config), as_of).get("SPY")
        if spy_bars is None or spy_bars.empty:
            logger.warning("SPY bars unavailable — skipping learnability")
        else:
            spy_closes = spy_bars.loc[spy_bars.index <= pd.Timestamp(as_of), "close"]
            price_frames = {t: ctx.prices for t, ctx in shortlist_contexts.items()}
            results = compute_learnability(price_frames, spy_closes, as_of, config, replayer)
            for ticker, result in results.items():
                shortlist_contexts[ticker].learnability = result

    # Final composite over the shortlist with ALL factors
    final_scores: list[TickerScore] = score_candidates(
        shortlist_contexts,
        stage1_factors() + stage2_factors(),
        config.factor_weights,
    )

    # Diversified selection
    price_frames = {t: ctx.prices for t, ctx in shortlist_contexts.items()}
    selected = select_universe(final_scores, price_frames, config)
    logger.info("Selected %d tickers", len(selected))

    snapshot = UniverseSnapshot(
        as_of=as_of,
        generated_at=datetime.now(timezone.utc).isoformat(),
        size=len(selected),
        tickers=selected,
        scores=final_scores,
        stage_counts={
            "stage0_candidates": len(candidates),
            "stage1_scored": len(stage1_scores),
            "stage2_shortlist": len(shortlist),
            "selected": len(selected),
        },
        config={
            "size": config.size,
            "min_price": config.min_price,
            "min_median_dollar_volume": config.min_median_dollar_volume,
            "stage2_size": config.stage2_size,
            "sector_cap_pct": config.sector_cap_pct,
            "max_correlation": config.max_correlation,
            "require_fundamentals": config.require_fundamentals,
            "learnability_enabled": config.learnability_enabled,
            "learnability_analysts": list(config.learnability_analysts),
            "factor_weights": dict(config.factor_weights),
        },
        caveats=list(_CAVEATS),
    )

    if save:
        path = save_universe(snapshot, config.output_dir)
        logger.info("Universe snapshot written: %s", path)
    return snapshot
