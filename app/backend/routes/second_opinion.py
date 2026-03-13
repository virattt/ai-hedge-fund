from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
import asyncio

from app.backend.database import get_db, SessionLocal
from app.backend.database.models import HedgeFundFlowRun
from app.backend.models.schemas import (
    ErrorResponse,
    HedgeFundRequest,
    FlowRunStatus,
)
from app.backend.services.graph import create_graph, run_graph, parse_hedge_fund_response
from app.backend.services.portfolio import create_portfolio
from app.backend.repositories.flow_run_repository import FlowRunRepository


router = APIRouter(prefix="/api/v1/second-opinion", tags=["second-opinion"])


class SecondOpinionRunStatus(str):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _create_flow_run_for_second_opinion(db: Session, request_data: dict) -> HedgeFundFlowRun:
    """
    Minimal adapter that reuses the existing HedgeFundFlowRun table to persist
    second-opinion jobs. We create a synthetic flow row with id=0 semantics by
    using flow_id=0 and storing the request on the run.
    """
    repo = FlowRunRepository(db)
    # Use flow_id=0 to indicate an ad-hoc second-opinion run not tied to a saved flow
    flow_run = repo.create_flow_run(flow_id=0, request_data=request_data)
    # Mark as IN_PROGRESS once the worker starts; caller will update via repository
    return flow_run


async def _execute_second_opinion_run(flow_run_id: int, request_data: dict) -> None:
    """
    Background worker: builds graph from request_data, runs it once, and stores
    the result JSON into HedgeFundFlowRun.results.
    """
    db = SessionLocal()
    repo = FlowRunRepository(db)
    try:
        flow_run = repo.get_flow_run_by_id(flow_run_id)
        if not flow_run:
            return

        # Mark run as started so polling clients can observe progress.
        repo.update_flow_run(
            run_id=flow_run_id,
            status=FlowRunStatus.IN_PROGRESS,
            results=None,
            error_message=None,
        )

        hedge_req = HedgeFundRequest(**request_data)
        graph = create_graph(
            graph_nodes=hedge_req.graph_nodes,
            graph_edges=hedge_req.graph_edges,
        )
        graph = graph.compile()

        # Keep portfolio shape consistent with the main hedge-fund flow:
        # positions must be a dict keyed by ticker (not a list).
        portfolio = create_portfolio(
            hedge_req.initial_cash,
            hedge_req.margin_requirement,
            hedge_req.tickers,
            hedge_req.portfolio_positions,
        )

        # Run graph work in a worker thread so we don't block the event loop.
        result = await asyncio.to_thread(
            run_graph,
            graph=graph,
            portfolio=portfolio,
            tickers=hedge_req.tickers,
            start_date=hedge_req.get_start_date(),
            end_date=hedge_req.end_date,
            model_name=hedge_req.model_name or "gpt-4.1",
            model_provider=str(hedge_req.model_provider.value if hedge_req.model_provider else "openai"),
            request=hedge_req,
        )

        # `run_graph` currently returns the full final state dict from graph.invoke(...)
        # while some callers expect a flattened {"decisions", "analyst_signals"} shape.
        # Normalize both shapes here to keep API output stable.
        if isinstance(result, dict) and "messages" in result and "data" in result:
            messages = result.get("messages") or []
            last_content = messages[-1].content if messages else None
            extracted_decisions = parse_hedge_fund_response(last_content) if last_content else None
            extracted_signals = (result.get("data") or {}).get("analyst_signals")
        else:
            extracted_decisions = result.get("decisions") if isinstance(result, dict) else None
            extracted_signals = result.get("analyst_signals") if isinstance(result, dict) else None

        # Store a JSON-serializable subset of the result on the run
        safe_results = jsonable_encoder(
            {
                "decisions": extracted_decisions,
                "analyst_signals": extracted_signals,
                "meta": {
                    "start_date": hedge_req.get_start_date(),
                    "end_date": hedge_req.end_date,
                    "tickers": hedge_req.tickers,
                    "sleeve": request_data.get("sleeve"),
                    "params_profile": request_data.get("params_profile"),
                },
            }
        )

        repo.update_flow_run(
            run_id=flow_run_id,
            status=FlowRunStatus.COMPLETE,
            results=safe_results,
            error_message=None,
        )
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        repo.update_flow_run(
            run_id=flow_run_id,
            status=FlowRunStatus.ERROR,
            results=None,
            error_message=str(e),
        )
    finally:
        db.close()


@router.post(
    "/runs",
    responses={
        202: {"description": "Second-opinion run accepted"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def submit_second_opinion_run(
    request: HedgeFundRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Submit a second-opinion job. This reuses the HedgeFundFlowRun persistence
    model but runs the graph once in a background task instead of streaming SSE.
    """
    try:
        payload = request.model_dump()
        flow_run = _create_flow_run_for_second_opinion(db, payload)

        # Detach execution so the submit endpoint can return immediately.
        asyncio.create_task(_execute_second_opinion_run(flow_run.id, payload))

        return {
            "run_id": flow_run.id,
            "status": SecondOpinionRunStatus.QUEUED,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit second-opinion run: {str(e)}")


@router.get(
    "/runs/{run_id}",
    responses={
        200: {"description": "Run status"},
        404: {"model": ErrorResponse, "description": "Run not found"},
    },
)
async def get_second_opinion_status(
    run_id: int,
    db: Session = Depends(get_db),
):
    """Return basic status metadata for a second-opinion job."""
    repo = FlowRunRepository(db)
    flow_run = repo.get_flow_run_by_id(run_id)
    if not flow_run:
        raise HTTPException(status_code=404, detail="Run not found")

    return {
        "run_id": flow_run.id,
        "status": flow_run.status,
        "created_at": flow_run.created_at,
        "started_at": flow_run.started_at,
        "completed_at": flow_run.completed_at,
        "error_message": flow_run.error_message,
    }


@router.get(
    "/runs/{run_id}/result",
    responses={
        200: {"description": "Completed result payload"},
        404: {"model": ErrorResponse, "description": "Run not found"},
        409: {"model": ErrorResponse, "description": "Run not completed yet"},
    },
)
async def get_second_opinion_result(
    run_id: int,
    db: Session = Depends(get_db),
):
    """Return the final run result once the job is COMPLETE."""
    repo = FlowRunRepository(db)
    flow_run = repo.get_flow_run_by_id(run_id)
    if not flow_run:
        raise HTTPException(status_code=404, detail="Run not found")
    if flow_run.status not in ("COMPLETE", "ERROR"):
        raise HTTPException(status_code=409, detail=f"Run not completed (status={flow_run.status})")

    return {
        "run_id": flow_run.id,
        "status": flow_run.status,
        "results": flow_run.results,
        "error_message": flow_run.error_message,
    }


