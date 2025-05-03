from fastapi import APIRouter, HTTPException

from app.backend.models.schemas import HedgeFundResponse, ErrorResponse, HedgeFundRequest
from app.backend.services.graphy import create_graph, parse_hedge_fund_response, run_graph
from app.backend.services.portfolio import create_portfolio

router = APIRouter()


@router.post(
    path="/run-hedge-fund",
    response_model=HedgeFundResponse,
    responses={
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

        # Convert model_provider to string if it's an enum
        model_provider = request.model_provider
        if hasattr(model_provider, "value"):
            model_provider = model_provider.value

        # Run the hedge fund
        result = run_graph(graph, portfolio, request.tickers, start_date, request.end_date, request.model_name, model_provider)

        if not result or not result.get("messages"):
            raise HTTPException(status_code=500, detail="Failed to generate hedge fund decisions")

        # Return the response from the graph
        return HedgeFundResponse(decisions=parse_hedge_fund_response(result.get("messages", [])[-1].content), analyst_signals=result.get("data", {}).get("analyst_signals", {}))

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while processing the request: {str(e)}")
