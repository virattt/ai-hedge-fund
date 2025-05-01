from fastapi import FastAPI

from app.backend.routes import api_router

app = FastAPI(
    title="AI Hedge Fund API",
    description="Backend API for AI Hedge Fund",
    version="0.1.0"
)

# Include all routes
app.include_router(api_router)
