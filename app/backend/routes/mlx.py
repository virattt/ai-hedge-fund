import os
from fastapi import APIRouter, HTTPException
from app.backend.models.schemas import ErrorResponse

router = APIRouter(prefix="/mlx")


@router.get(
    path="/status",
    responses={
        200: {"description": "MLX server status"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_mlx_status():
    """Check if the MLX LM server is reachable."""
    try:
        from src.utils.mlx_lm import is_mlx_server_running, _get_mlx_base_url
        running = is_mlx_server_running()
        base_url = _get_mlx_base_url()
        # Strip /v1 suffix for display
        server_url = base_url.rstrip("/v1").rstrip("/") if base_url.endswith("/v1") else base_url
        return {
            "running": running,
            "server_url": server_url,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check MLX status: {str(e)}")
