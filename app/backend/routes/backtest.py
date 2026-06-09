"""Backtest replay route — replay rule thresholds against discovery_snapshots."""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.backend.models.backtest_schemas import (
    BacktestParamsResponse,
    BacktestResultResponse,
    BacktestTriggerResponse,
)
from app.backend.services.discovery_backtest_service import (
    MODE_HIGH_CONFLUENCE,
    MODE_SCORE_THRESHOLD,
    MODE_SOURCE_THRESHOLD,
    run_backtest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.get("/run", response_model=BacktestResultResponse)
async def run_endpoint(
    mode: str = Query(
        MODE_HIGH_CONFLUENCE,
        description=f"One of: {MODE_SCORE_THRESHOLD}, {MODE_HIGH_CONFLUENCE}, {MODE_SOURCE_THRESHOLD}",
    ),
    score_threshold: float = Query(60.0, ge=0),
    min_sources: int = Query(4, ge=1),
    source_filter: str | None = Query(None),
    source_score_threshold: float = Query(20.0, ge=0),
    lookback_days: int = Query(90, ge=1, le=365),
    hold_days: int = Query(30, ge=1, le=365),
) -> BacktestResultResponse:
    try:
        result = await run_backtest(
            mode=mode,
            score_threshold=score_threshold,
            min_sources=min_sources,
            source_filter=source_filter,
            source_score_threshold=source_score_threshold,
            lookback_days=lookback_days,
            hold_days=hold_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Backtest run failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return BacktestResultResponse(
        mode=result.mode,
        lookback_days=result.lookback_days,
        hold_days=result.hold_days,
        params=BacktestParamsResponse(
            score_threshold=result.params.score_threshold,
            min_sources=result.params.min_sources,
            source_filter=result.params.source_filter,
            source_score_threshold=result.params.source_score_threshold,
        ),
        total_triggers=result.total_triggers,
        triggers_with_returns=result.triggers_with_returns,
        win_rate_pct=result.win_rate_pct,
        avg_return_pct=result.avg_return_pct,
        median_return_pct=result.median_return_pct,
        avg_alpha_pct=result.avg_alpha_pct,
        best_return_pct=result.best_return_pct,
        worst_return_pct=result.worst_return_pct,
        snapshot_count_in_window=result.snapshot_count_in_window,
        distinct_tickers_in_window=result.distinct_tickers_in_window,
        triggers=[
            BacktestTriggerResponse(
                ticker=t.ticker,
                trigger_date=t.trigger_date,
                snapshot_score=t.snapshot_score,
                distinct_sources_at_trigger=t.distinct_sources_at_trigger,
                signal_sources=t.signal_sources,
                holding_period_days=t.holding_period_days,
                entry_price=t.entry_price,
                exit_price=t.exit_price,
                return_pct=t.return_pct,
                spy_return_pct=t.spy_return_pct,
                alpha_pct=t.alpha_pct,
            )
            for t in result.triggers
        ],
    )
