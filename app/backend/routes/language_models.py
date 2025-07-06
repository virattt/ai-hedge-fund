from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

from app.backend.models.schemas import ErrorResponse
from app.backend.services.ollama_service import OllamaService
from src.llm.models import get_models_list

router = APIRouter(prefix="/language-models")

# Initialize Ollama service
ollama_service = OllamaService()

@router.get(
    path="/",
    responses={
        200: {"description": "List of available language models"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_language_models():
    """Get the list of available cloud-based and Ollama language models."""
    try:
        # Start with cloud models
        models = get_models_list()
        
        # Add available Ollama models (handles all checking internally)
        ollama_models = await ollama_service.get_available_models()
        models.extend(ollama_models)
        
        return {"models": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve models: {str(e)}")

@router.get(
    path="/providers",
    responses={
        200: {"description": "List of available model providers"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_language_model_providers():
    """Get the list of available model providers with their models grouped."""
    try:
        models = get_models_list()
        
        # Group models by provider
        providers = {}
        for model in models:
            provider_name = model["provider"]
            if provider_name not in providers:
                providers[provider_name] = {
                    "name": provider_name,
                    "models": []
                }
            providers[provider_name]["models"].append({
                "display_name": model["display_name"],
                "model_name": model["model_name"]
            })
        
        return {"providers": list(providers.values())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve providers: {str(e)}") 