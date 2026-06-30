from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio
import json

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    return {"status": "ok", "message": "AI Hedge Fund API"}


@router.get("/ping")
async def ping():
    async def event_generator():
        for i in range(5):
            data = {"ping": f"ping {i+1}/5", "timestamp": i + 1}
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
