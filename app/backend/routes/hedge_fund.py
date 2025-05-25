from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import asyncio
from datetime import datetime
from typing import List

from app.backend.models.schemas import (
    HedgeFundRequest,
    ErrorResponse,
    AgentInfo,
    HedgeFundResponse
)
from app.backend.models.events import (
    StartEvent,
    ProgressUpdateEvent,
    ErrorEvent,
    CompleteEvent
)
from app.backend.services.hedge_fund import HedgeFundService

router = APIRouter(prefix="/hedge-fund")

@router.get(
    "/agents",
    response_model=List[AgentInfo],
    responses={
        200: {"description": "List of available agents"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_agents():
    """Get a list of available agents with their descriptions."""
    try:
        return HedgeFundService.get_available_agents()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/run",
    responses={
        200: {"description": "Successful response with streaming updates"},
        400: {"model": ErrorResponse, "description": "Invalid request parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def run_hedge_fund(request: HedgeFundRequest):
    """Run the hedge fund with the given parameters and stream progress updates."""
    try:
        # Create a queue for progress updates
        progress_queue = asyncio.Queue()
        
        # Define progress handler
        def progress_handler(agent_name, ticker, status, analysis, timestamp):
            event = ProgressUpdateEvent(
                agent=agent_name,
                ticker=ticker,
                status=status,
                analysis=analysis,
                timestamp=timestamp or datetime.now()
            )
            progress_queue.put_nowait(event)
        
        async def event_generator():
            try:
                # Send start event
                yield StartEvent().to_sse()
                
                # Run the hedge fund in a background task
                run_task = asyncio.create_task(
                    HedgeFundService.run_hedge_fund(
                        tickers=request.tickers,
                        selected_agents=request.selected_agents,
                        initial_cash=request.initial_cash,
                        margin_requirement=request.margin_requirement,
                        start_date=request.start_date,
                        end_date=request.end_date,
                        model_name=request.model_name,
                        model_provider=request.model_provider,
                        show_reasoning=request.show_reasoning
                    )
                )
                
                # Stream progress updates until run_task completes
                while not run_task.done():
                    try:
                        event = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                        yield event.to_sse()
                    except asyncio.TimeoutError:
                        continue
                
                # Get the final result
                result = run_task.result()
                
                if not result:
                    yield ErrorEvent(message="Failed to generate hedge fund decisions").to_sse()
                    return
                
                # Send the final result
                final_data = CompleteEvent(data=result)
                yield final_data.to_sse()
                
            except Exception as e:
                yield ErrorEvent(message=str(e)).to_sse()
            finally:
                if "run_task" in locals() and not run_task.done():
                    run_task.cancel()
        
        # Return a streaming response
        return StreamingResponse(event_generator(), media_type="text/event-stream")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
