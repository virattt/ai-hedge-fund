from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

from app.backend.database import get_db
from app.backend.repositories.api_key_repository import ApiKeyRepository
from app.backend.models.schemas import (
    ApiKeyCreateRequest,
    ApiKeyUpdateRequest,
    ApiKeyResponse,
    ApiKeySummaryResponse,
    ApiKeyBulkUpdateRequest,
    ErrorResponse
)

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post(
    "/",
    response_model=ApiKeyResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def create_or_update_api_key(request: ApiKeyCreateRequest, db: Session = Depends(get_db)):
    """Create a new API key or update existing one"""
    try:
        repo = ApiKeyRepository(db)
        api_key = repo.create_or_update_api_key(
            provider=request.provider,
            key_value=request.key_value,
            description=request.description,
            is_active=request.is_active
        )
        return ApiKeyResponse.from_orm(api_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create/update API key: {str(e)}")


@router.get(
    "/",
    response_model=List[ApiKeySummaryResponse],
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_api_keys(include_inactive: bool = False, db: Session = Depends(get_db)):
    """Get all API keys (without actual key values for security)"""
    try:
        repo = ApiKeyRepository(db)
        api_keys = repo.get_all_api_keys(include_inactive=include_inactive)
        return [ApiKeySummaryResponse.from_orm(key) for key in api_keys]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve API keys: {str(e)}")


@router.get(
    "/{provider}",
    response_model=ApiKeyResponse,
    responses={
        404: {"model": ErrorResponse, "description": "API key not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_api_key(provider: str, db: Session = Depends(get_db)):
    """Get a specific API key by provider"""
    try:
        repo = ApiKeyRepository(db)
        api_key = repo.get_api_key_by_provider(provider)
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        return ApiKeyResponse.from_orm(api_key)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve API key: {str(e)}")


@router.put(
    "/{provider}",
    response_model=ApiKeyResponse,
    responses={
        404: {"model": ErrorResponse, "description": "API key not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def update_api_key(provider: str, request: ApiKeyUpdateRequest, db: Session = Depends(get_db)):
    """Update an existing API key"""
    try:
        repo = ApiKeyRepository(db)
        api_key = repo.update_api_key(
            provider=provider,
            key_value=request.key_value,
            description=request.description,
            is_active=request.is_active
        )
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        return ApiKeyResponse.from_orm(api_key)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update API key: {str(e)}")


@router.delete(
    "/{provider}",
    responses={
        204: {"description": "API key deleted successfully"},
        404: {"model": ErrorResponse, "description": "API key not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def delete_api_key(provider: str, db: Session = Depends(get_db)):
    """Delete an API key"""
    try:
        repo = ApiKeyRepository(db)
        success = repo.delete_api_key(provider)
        if not success:
            raise HTTPException(status_code=404, detail="API key not found")
        return {"message": "API key deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete API key: {str(e)}")


@router.patch(
    "/{provider}/deactivate",
    response_model=ApiKeySummaryResponse,
    responses={
        404: {"model": ErrorResponse, "description": "API key not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def deactivate_api_key(provider: str, db: Session = Depends(get_db)):
    """Deactivate an API key without deleting it"""
    try:
        repo = ApiKeyRepository(db)
        success = repo.deactivate_api_key(provider)
        if not success:
            raise HTTPException(status_code=404, detail="API key not found")
        
        # Return the updated key
        api_key = repo.get_api_key_by_provider(provider)
        return ApiKeySummaryResponse.from_orm(api_key)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to deactivate API key: {str(e)}")


@router.post(
    "/bulk",
    response_model=List[ApiKeyResponse],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def bulk_update_api_keys(request: ApiKeyBulkUpdateRequest, db: Session = Depends(get_db)):
    """Bulk create or update multiple API keys"""
    try:
        repo = ApiKeyRepository(db)
        api_keys_data = [
            {
                'provider': key.provider,
                'key_value': key.key_value,
                'description': key.description,
                'is_active': key.is_active
            }
            for key in request.api_keys
        ]
        api_keys = repo.bulk_create_or_update(api_keys_data)
        return [ApiKeyResponse.from_orm(key) for key in api_keys]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk update API keys: {str(e)}")


@router.patch(
    "/{provider}/last-used",
    responses={
        200: {"description": "Last used timestamp updated"},
        404: {"model": ErrorResponse, "description": "API key not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def update_last_used(provider: str, db: Session = Depends(get_db)):
    """Update the last used timestamp for an API key"""
    try:
        repo = ApiKeyRepository(db)
        success = repo.update_last_used(provider)
        if not success:
            raise HTTPException(status_code=404, detail="API key not found")
        return {"message": "Last used timestamp updated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update last used timestamp: {str(e)}") 