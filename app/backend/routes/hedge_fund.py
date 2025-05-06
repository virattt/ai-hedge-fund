from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import asyncio

from app.backend.models.schemas import ErrorResponse, HedgeFundRequest
from app.backend.models.events import StartEvent, ProgressUpdateEvent, ErrorEvent, CompleteEvent
from app.backend.services.graphy import create_graph, parse_hedge_fund_response, run_graph_async
from app.backend.services.portfolio import create_portfolio
from src.utils.progress import progress

router = APIRouter(prefix="/hedge-fund")


@router.post(
    path="/run",
    responses={
        200: {"description": "Successful response with streaming updates"},
        400: {"model": ErrorResponse, "description": "Invalid request parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def run_hedge_fund(request: HedgeFundRequest):
    try:
        # Get the start date if not provided
        start_date = request.get_start_date()

        # Create the portfolio
        portfolio = create_portfolio(request.initial_cash, request.margin_requirement, request.tickers)

        # Construct agent graph
        graph = create_graph(request.selected_agents)
        graph = graph.compile()

        # Log a test progress update for debugging
        progress.update_status("system", None, "Preparing hedge fund run")

        # Convert model_provider to string if it's an enum
        model_provider = request.model_provider
        if hasattr(model_provider, "value"):
            model_provider = model_provider.value

        # Set up streaming response
        async def event_generator():
            # Queue for progress updates
            progress_queue = asyncio.Queue()

            # Simple handler to add updates to the queue
            def progress_handler(agent_name, ticker, status):
                event = ProgressUpdateEvent(agent=agent_name, ticker=ticker, status=status)
                progress_queue.put_nowait(event)

            # Register our handler with the progress tracker
            progress.register_handler(progress_handler)

            try:
                # Start the graph execution in a background task
                run_task = asyncio.create_task(
                    run_graph_async(
                        graph=graph,
                        portfolio=portfolio,
                        tickers=request.tickers,
                        start_date=start_date,
                        end_date=request.end_date,
                        model_name=request.model_name,
                        model_provider=model_provider,
                    )
                )
                # Send initial message
                yield StartEvent().to_sse()

                # Stream progress updates until run_task completes
                while not run_task.done():
                    # Either get a progress update or wait a bit
                    try:
                        event = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                        yield event.to_sse()
                    except asyncio.TimeoutError:
                        # Just continue the loop
                        pass

                # Get the final result
                result = run_task.result()

                if not result or not result.get("messages"):
                    yield ErrorEvent(message="Failed to generate hedge fund decisions").to_sse()
                    return

                # Send the final result
                final_data = CompleteEvent(
                    data={
                        "decisions": parse_hedge_fund_response(result.get("messages", [])[-1].content),
                        "analyst_signals": result.get("data", {}).get("analyst_signals", {}),
                    }
                )
                yield final_data.to_sse()

            finally:
                # Clean up
                progress.unregister_handler(progress_handler)
                if "run_task" in locals() and not run_task.done():
                    run_task.cancel()

        # Return a streaming response
        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while processing the request: {str(e)}")
