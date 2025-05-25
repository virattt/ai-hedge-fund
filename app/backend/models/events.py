from typing import Dict, Optional, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class BaseEvent(BaseModel):
    """Base class for all Server-Sent Event events"""

    def to_sse(self) -> str:
        """Convert event to Server-Sent Events format"""
        event_type = self.__class__.__name__.lower()
        data = self.model_dump_json()
        return f"event: {event_type}\ndata: {data}\n\n"


class StartEvent(BaseEvent):
    """Event indicating the start of processing"""

    type: Literal["start"] = "start"
    timestamp: datetime = Field(default_factory=datetime.now)

class ProgressUpdateEvent(BaseEvent):
    """Event containing an agent's progress update"""

    type: Literal["progress"] = "progress"
    agent: str
    ticker: str
    status: str
    analysis: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class ErrorEvent(BaseEvent):
    """Event indicating an error occurred"""

    type: Literal["error"] = "error"
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)


class CompleteEvent(BaseEvent):
    """Event indicating successful completion with results"""

    type: Literal["complete"] = "complete"
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)
