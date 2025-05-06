from typing import Dict, Optional, Any, Literal
from pydantic import BaseModel


class BaseEvent(BaseModel):
    """Base class for all Server-Sent Event events"""

    type: str

    def to_sse(self) -> str:
        """Convert to Server-Sent Event format"""
        return f"data: {self.model_dump_json()}\n\n"


class StartEvent(BaseEvent):
    """Event indicating the start of processing"""

    type: Literal["start"] = "start"


class ProgressUpdateEvent(BaseEvent):
    """Event containing an agent's progress update"""

    type: Literal["IN_PROGRESS"] = "IN_PROGRESS"
    agent: str
    ticker: Optional[str] = None
    status: str


class ErrorEvent(BaseEvent):
    """Event indicating an error occurred"""

    type: Literal["ERROR"] = "ERROR"
    message: str


class CompleteEvent(BaseEvent):
    """Event indicating successful completion with results"""

    type: Literal["COMPLETE"] = "COMPLETE"
    data: Dict[str, Any]
