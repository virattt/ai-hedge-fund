from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import logging

from app.backend.models.schemas import ErrorResponse
from app.backend.services.ollama_service import ollama_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ollama")

class ModelRequest(BaseModel):
    model_name: str

class OllamaStatusResponse(BaseModel):
    installed: bool
    running: bool
    available_models: List[str]
    server_url: str
    error: str | None = None

class ActionResponse(BaseModel):
    success: bool
    message: str

class RecommendedModel(BaseModel):
    display_name: str
    model_name: str
    provider: str

class ProgressResponse(BaseModel):
    status: str
    percentage: float | None = None
    message: str | None = None
    phase: str | None = None
    bytes_downloaded: int | None = None
    total_bytes: int | None = None

@router.get(
    "/status",
    response_model=OllamaStatusResponse,
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_ollama_status():
    """Get Ollama installation and server status."""
    try:
        status = await ollama_service.check_ollama_status()
        return OllamaStatusResponse(**status)
    except Exception as e:
        logger.error(f"Failed to check Ollama status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to check Ollama status: {str(e)}")

@router.post(
    "/start",
    response_model=ActionResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def start_ollama_server():
    """Start the Ollama server."""
    try:
        # First check if it's already running
        status = await ollama_service.check_ollama_status()
        if not status["installed"]:
            raise HTTPException(status_code=400, detail="Ollama is not installed on this system")
        
        if status["running"]:
            return ActionResponse(success=True, message="Ollama server is already running")
        
        result = await ollama_service.start_server()
        
        if not result["success"]:
            logger.error(f"Failed to start Ollama server: {result['message']}")
            raise HTTPException(status_code=500, detail=result["message"])
        
        return ActionResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error starting Ollama server: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start Ollama server: {str(e)}")

@router.post(
    "/stop",
    response_model=ActionResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def stop_ollama_server():
    """Stop the Ollama server."""
    try:
        # First check if it's installed
        status = await ollama_service.check_ollama_status()
        if not status["installed"]:
            raise HTTPException(status_code=400, detail="Ollama is not installed on this system")
        
        if not status["running"]:
            return ActionResponse(success=True, message="Ollama server is already stopped")
        
        result = await ollama_service.stop_server()
        
        if not result["success"]:
            logger.error(f"Failed to stop Ollama server: {result['message']}")
            raise HTTPException(status_code=500, detail=result["message"])
        
        return ActionResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error stopping Ollama server: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop Ollama server: {str(e)}")

@router.post(
    "/models/download",
    response_model=ActionResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def download_model(request: ModelRequest):
    """Download an Ollama model (legacy endpoint)."""
    try:
        logger.info(f"Download request for model: {request.model_name}")
        
        # Check current status
        status = await ollama_service.check_ollama_status()
        logger.debug(f"Current Ollama status: installed={status['installed']}, running={status['running']}")
        
        if not status["installed"]:
            raise HTTPException(status_code=400, detail="Ollama is not installed on this system")
        
        if not status["running"]:
            raise HTTPException(status_code=400, detail="Ollama server is not running. Please start it first.")
        
        result = await ollama_service.download_model(request.model_name)
        
        if not result["success"]:
            logger.error(f"Failed to download model {request.model_name}: {result['message']}")
            raise HTTPException(status_code=500, detail=result["message"])
        
        logger.info(f"Successfully downloaded model: {request.model_name}")
        return ActionResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error downloading model {request.model_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download model: {str(e)}")

@router.post(
    "/models/download/progress",
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def download_model_with_progress(request: ModelRequest):
    """Download an Ollama model with real-time progress updates via Server-Sent Events."""
    try:
        logger.info(f"Progress download request for model: {request.model_name}")
        
        # Check current status
        status = await ollama_service.check_ollama_status()
        logger.debug(f"Current Ollama status: installed={status['installed']}, running={status['running']}")
        
        if not status["installed"]:
            raise HTTPException(status_code=400, detail="Ollama is not installed on this system")
        
        if not status["running"]:
            raise HTTPException(status_code=400, detail="Ollama server is not running. Please start it first.")
        
        # Return Server-Sent Events stream
        return StreamingResponse(
            ollama_service.download_model_with_progress(request.model_name),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error setting up progress download for {request.model_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start progress download: {str(e)}")

@router.get(
    "/models/download/progress/{model_name}",
    response_model=ProgressResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Model download not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_download_progress(model_name: str):
    """Get current download progress for a specific model."""
    try:
        progress = ollama_service.get_download_progress(model_name)
        if progress is None:
            raise HTTPException(status_code=404, detail=f"No active download found for model: {model_name}")
        
        return ProgressResponse(**progress)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting download progress for {model_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get download progress: {str(e)}")

@router.get(
    "/models/downloads/active",
    response_model=Dict[str, ProgressResponse],
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_active_downloads():
    """Get all currently active model downloads."""
    try:
        active_downloads = {}
        all_progress = ollama_service.get_all_download_progress()
        
        # Only return downloads that are actually active (not completed, error, or cancelled)
        for model_name, progress in all_progress.items():
            if progress.get("status") in ["starting", "downloading"]:
                active_downloads[model_name] = ProgressResponse(**progress)
        
        return active_downloads
    except Exception as e:
        logger.error(f"Error getting active downloads: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get active downloads: {str(e)}")

@router.delete(
    "/models/{model_name}",
    response_model=ActionResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def delete_model(model_name: str):
    """Delete an Ollama model."""
    try:
        logger.info(f"Delete request for model: {model_name}")
        
        # Check current status
        status = await ollama_service.check_ollama_status()
        logger.debug(f"Current Ollama status: installed={status['installed']}, running={status['running']}")
        
        if not status["installed"]:
            raise HTTPException(status_code=400, detail="Ollama is not installed on this system")
        
        if not status["running"]:
            raise HTTPException(status_code=400, detail="Ollama server is not running. Please start it first.")
        
        result = await ollama_service.delete_model(model_name)
        
        if not result["success"]:
            logger.error(f"Failed to delete model {model_name}: {result['message']}")
            raise HTTPException(status_code=500, detail=result["message"])
        
        logger.info(f"Successfully deleted model: {model_name}")
        return ActionResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting model {model_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete model: {str(e)}")

@router.get(
    "/models/recommended",
    response_model=List[RecommendedModel],
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_recommended_models():
    """Get list of recommended Ollama models."""
    try:
        models = await ollama_service.get_recommended_models()
        return [RecommendedModel(**model) for model in models]
    except Exception as e:
        logger.error(f"Failed to get recommended models: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recommended models: {str(e)}")

@router.delete(
    "/models/download/{model_name}",
    response_model=ActionResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Download not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def cancel_download(model_name: str):
    """Cancel an active model download."""
    try:
        logger.info(f"Cancel download request for model: {model_name}")
        
        success = ollama_service.cancel_download(model_name)
        
        if success:
            return ActionResponse(success=True, message=f"Download cancelled for {model_name}")
        else:
            raise HTTPException(status_code=404, detail=f"No active download found for model: {model_name}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error cancelling download for {model_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel download: {str(e)}") 