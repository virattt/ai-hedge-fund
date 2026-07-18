from fastapi import APIRouter, HTTPException
import json
import re
from pathlib import Path
from pydantic import BaseModel, field_validator

from app.backend.models.schemas import ErrorResponse

router = APIRouter(prefix="/storage")

class SaveJsonRequest(BaseModel):
    filename: str
    data: dict

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        # Only allow alphanumeric, hyphens, underscores, and dots; no path separators
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', v):
            raise ValueError("Filename contains invalid characters")
        if '..' in v:
            raise ValueError("Filename must not contain '..'")
        return v

@router.post(
    path="/save-json",
    responses={
        200: {"description": "File saved successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def save_json_file(request: SaveJsonRequest):
    """Save JSON data to the project's /outputs directory."""
    try:
        # Create outputs directory if it doesn't exist
        project_root = Path(__file__).parent.parent.parent.parent  # Navigate to project root
        outputs_dir = project_root / "outputs"
        outputs_dir.mkdir(exist_ok=True)

        # Construct file path and verify it stays within outputs_dir
        file_path = (outputs_dir / request.filename).resolve()
        if not str(file_path).startswith(str(outputs_dir.resolve())):
            raise HTTPException(status_code=400, detail="Invalid filename")

        # Save JSON data to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(request.data, f, indent=2, ensure_ascii=False)

        return {
            "success": True,
            "message": "File saved successfully",
            "filename": request.filename
        }

    except HTTPException:
        raise
    except (IOError, OSError):
        raise HTTPException(status_code=500, detail="Failed to save file")
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error") 