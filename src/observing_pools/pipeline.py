"""Weekly observing-pool refresh pipeline (PRD v4 Phase 5).

Orchestrates: init taxonomy → load/validate universe → deterministic classify →
run the analyst committee (injected, so tests run offline) → aggregate into the
blended composite → rank → persist top-N with full reproducible breakdown +
provenance. Loud cost ceiling: a breach marks the run ``partial``, never silent.

The ``run_analysts`` callable is injected: production passes
``scoring_graph.run_scoring_analysts`` (real LLM committee); tests pass a
deterministic stub (no network, no spend).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy.orm import Session

from src.observing_pools.agents_bridge import committee_analyst_keys, component_scores
from src.observing_pools.classify import classify_candidate
from src.observing_pools.platforms import PLATFORM_BY_KEY, init_platforms
from src.observing_pools.scoring import (
    COMPONENT_WEIGHTS,
    FORMULA_4COMP,
    build_components,
    composite,
    validate_weights,
)
from src.observing_pools.universe import load_seed_csv, upsert_candidates
from src.storage.models import (
    ObservationPoolEntry,
    PoolEntryStatus,
    PoolRefreshRun,
    RefreshRunStatus,
)


class RunAnalysts(Protocol):
    def __call__(self, tickers: list[str], selected_analysts: list[str], end_date: str) -> tuple[dict[str, dict[str, dict]], dict]:
        ...


@dataclass(frozen=True)
class RefreshConfig:
    platform_key: str
    universe_csv: str
    top_n: int = 20
    formula_version: str = FORMULA_4COMP
    classify_min_confidence: float = 0.3
    token_budget: int | None = None  # max analyst "calls" proxy; None = unbounded
    selected_analysts: list[str] | None = None  # None → full blended committee
    dry_run: bool = False
    weights: dict = field(default_factory=lambda: dict(COMPONENT_WEIGHTS))


@dataclass
class ScoredCandidate:
    ticker: str
    composite_score: float | None
    components: dict[str, float | None]
    breakdown: dict
    platform_fit: float | None
    rationale: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def refresh_pool(
    session: Session,
    config: RefreshConfig,
    run_analysts: RunAnalysts,
    *,
    end_date: str,
    provider_name: str = "yfinance",
) -> PoolRefreshRun:
    """Run one refresh for ``config.platform_key`` ending at ``end_date``.

    Persists a ``PoolRefreshRun`` and up-to-``top_n`` ranked ``ObservationPoolEntry``
    rows (+ any ``data_unavailable`` exclusions), unless ``config.dry_run``.
    """
    if config.platform_key not in PLATFORM_BY_KEY:
        raise ValueError(f"unknown platform_key: {config.platform_key}")
    validate_weights(config.weights)

    init_platforms(session)
    seed_rows, rejected = load_seed_csv(config.universe_csv)
    if not config.dry_run:
        upsert_candidates(session, seed_rows)

    # Deterministic classification → candidates for THIS platform above threshold.
    platform_fit: dict[str, float] = {}
    for row in seed_rows:
        results = classify_candidate(name=row.name, sector=row.sector, industry=row.industry, explicit_platforms=row.platforms)
        hit = results.get(config.platform_key)
        if hit is not None and hit.confidence >= config.classify_min_confidence:
            platform_fit[row.ticker] = hit.confidence * 100.0
    candidate_tickers = sorted(platform_fit)

    run = PoolRefreshRun(
        status=RefreshRunStatus.RUNNING.value,
        provider_name=provider_name,
        universe_source=config.universe_csv,
        universe_version=str(len(seed_rows)),
        composite_formula_version=config.formula_version,
        platform_keys=[config.platform_key],
        candidate_count=len(candidate_tickers),
        rejected=rejected or None,
    )
    if not config.dry_run:
        session.add(run)
        session.flush()  # need run.id for entry FK

    committee = config.selected_analysts or committee_analyst_keys()
    analyst_signals, token_cost = ({}, {"calls": 0}) if not candidate_tickers else run_analysts(candidate_tickers, committee, end_date)

    # Score every candidate.
    scored: list[ScoredCandidate] = []
    for ticker in candidate_tickers:
        comps, breakdown = component_scores(analyst_signals, ticker, platform_fit_score=platform_fit[ticker])
        comp_map = build_components(comps, formula_version=config.formula_version, weights=config.weights)
        score = composite(comp_map, pool_serenity_median=None, formula_version=config.formula_version)
        breakdown["formula_version"] = config.formula_version
        breakdown["weights"] = {k: config.weights[k] for k, _ in comp_map.items()}
        breakdown["composite"] = score
        rationale = f"platform={config.platform_key} fit={platform_fit[ticker]:.0f}; " f"composite={'n/a' if score is None else round(score, 1)} ({config.formula_version})"
        scored.append(ScoredCandidate(ticker, score, comps, breakdown, platform_fit[ticker], rationale))

    # Rank the rankable (composite not None) desc; data_unavailable kept unranked.
    rankable = sorted((c for c in scored if c.composite_score is not None), key=lambda c: c.composite_score, reverse=True)
    unavailable = [c for c in scored if c.composite_score is None]
    top = rankable[: config.top_n]

    if not config.dry_run:
        for rank, cand in enumerate(top, start=1):
            _upsert_entry(session, run, config, cand, rank=rank, status=PoolEntryStatus.CANDIDATE)
        for cand in unavailable:
            _upsert_entry(session, run, config, cand, rank=None, status=PoolEntryStatus.DATA_UNAVAILABLE)

    # Loud cost ceiling + provenance.
    calls = token_cost.get("calls", 0)
    over_budget = config.token_budget is not None and calls > config.token_budget
    # Analysts that hit a provider fetch error are degraded for the run (node-boundary
    # handler) — record them so the run is visibly partial, not silently missing data.
    degraded = sorted(set(token_cost.get("degraded_analysts") or []))
    run.token_cost = token_cost
    run.completed_at = _now()
    run.summary = {
        "ranked": len(top),
        "data_unavailable": len(unavailable),
        "candidates": len(candidate_tickers),
        "top_tickers": [c.ticker for c in top],
    }
    if degraded:
        run.fetch_errors = {"degraded_analysts": degraded}
    if over_budget:
        run.status = RefreshRunStatus.PARTIAL.value
        run.error = f"token budget exceeded: {calls} calls > {config.token_budget}"
    elif rejected or degraded:
        run.status = RefreshRunStatus.PARTIAL.value
    else:
        run.status = RefreshRunStatus.COMPLETE.value

    if not config.dry_run:
        session.flush()
    return run


def _upsert_entry(
    session: Session,
    run: PoolRefreshRun,
    config: RefreshConfig,
    cand: ScoredCandidate,
    *,
    rank: int | None,
    status: PoolEntryStatus,
) -> ObservationPoolEntry:
    entry = session.query(ObservationPoolEntry).filter_by(ticker=cand.ticker, platform_key=config.platform_key).one_or_none()
    if entry is None:
        entry = ObservationPoolEntry(ticker=cand.ticker, platform_key=config.platform_key)
        session.add(entry)
    entry.status = status.value
    entry.platform_fit_score = cand.platform_fit
    entry.value_investor_score = cand.components.get("value_investor")
    entry.innovation_growth_score = cand.components.get("innovation_growth")
    entry.serenity_bottleneck_score = cand.components.get("serenity_bottleneck")
    entry.risk_adjusted_momentum_score = cand.components.get("risk_adjusted_momentum")
    entry.composite_score = cand.composite_score
    entry.composite_formula_version = config.formula_version
    entry.score_breakdown = cand.breakdown
    entry.rank = rank
    entry.rationale = cand.rationale
    entry.last_refresh_run_id = run.id
    return entry
