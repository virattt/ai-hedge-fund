from fastapi import APIRouter, HTTPException
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from pydantic import BaseModel

from app.backend.models.schemas import ErrorResponse

router = APIRouter(prefix="/storage")

class SaveJsonRequest(BaseModel):
    filename: str
    data: dict


def _safe_output_path(outputs_dir: Path, filename: str) -> Path:
    """Resolve `filename` inside `outputs_dir`, rejecting path traversal.

    Rejects absolute paths, drive letters, and any component like ``..`` so the
    resulting file is guaranteed to live directly under ``outputs_dir``.
    """
    if not filename or not filename.strip():
        raise HTTPException(status_code=400, detail="filename must not be empty")

    # Reject path separators / parent references / absolute paths outright.
    # We require a plain filename (no directory components).
    if (
        "/" in filename
        or "\\" in filename
        or filename in (".", "..")
        or PurePosixPath(filename).is_absolute()
        or PureWindowsPath(filename).is_absolute()
    ):
        raise HTTPException(status_code=400, detail="Invalid filename")

    outputs_dir_resolved = outputs_dir.resolve()
    file_path = (outputs_dir_resolved / filename).resolve()

    # Belt-and-suspenders: ensure the resolved path is directly inside outputs_dir.
    if file_path.parent != outputs_dir_resolved:
        raise HTTPException(status_code=400, detail="Invalid filename")

    return file_path


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

        # Construct and validate file path (prevents path traversal - CWE-22)
        file_path = _safe_output_path(outputs_dir, request.filename)

        # Save JSON data to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(request.data, f, indent=2, ensure_ascii=False)
        
        return {
            "success": True,
            "message": f"File saved successfully to {file_path}",
            "filename": request.filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}") 
