"""FastAPI route for the structured ticker snapshot.

Endpoints:
    GET /snapshot/{ticker}            -> JSON SnapshotReport
    GET /snapshot/{ticker}/html       -> HTML dashboard (single page)
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from src.analysis import generate_snapshot, render_html

router = APIRouter()


def _dataclass_to_dict(obj):
    if dataclasses.is_dataclass(obj):
        return {k: _dataclass_to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, (list, tuple)):
        return [_dataclass_to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _dataclass_to_dict(v) for k, v in obj.items()}
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


@router.get("/snapshot/{ticker}")
async def get_snapshot(ticker: str):
    """Return the SnapshotReport as JSON."""
    try:
        report = generate_snapshot(ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Snapshot generation failed: {e}")
    return JSONResponse(_dataclass_to_dict(report))


@router.get("/snapshot/{ticker}/html", response_class=HTMLResponse)
async def get_snapshot_html(ticker: str):
    """Return the SnapshotReport as a rendered HTML page."""
    try:
        report = generate_snapshot(ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Snapshot generation failed: {e}")

    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as tmp:
        tmp_path = Path(tmp.name)
    render_html(report, tmp_path)
    html_str = tmp_path.read_text(encoding="utf-8")
    try:
        tmp_path.unlink()
    except OSError:
        pass
    return HTMLResponse(html_str)
