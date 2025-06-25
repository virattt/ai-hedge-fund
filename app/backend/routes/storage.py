from fastapi import APIRouter, HTTPException
import json
from pathlib import Path
from pydantic import BaseModel

from app.backend.models.schemas import ErrorResponse

router = APIRouter(prefix="/storage")

class SaveJsonRequest(BaseModel):
    filename: str
    data: dict

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
        
        # Construct file path
        file_path = outputs_dir / request.filename
        
        # Save JSON data to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(request.data, f, indent=2, ensure_ascii=False)
        
        return {
            "success": True,
            "message": f"File saved successfully to {file_path}",
            "filename": request.filename
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}") 