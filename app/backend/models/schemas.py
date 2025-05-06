from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from typing import List, Optional
from src.llm.models import ModelProvider


class HedgeFundResponse(BaseModel):
    decisions: dict
    analyst_signals: dict


class ErrorResponse(BaseModel):
    message: str
    error: str | None = None


class HedgeFundRequest(BaseModel):
    tickers: List[str]
    selected_agents: List[str]
    end_date: Optional[str] = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    start_date: Optional[str] = None
    model_name: str = "gpt-4o"
    model_provider: ModelProvider = ModelProvider.OPENAI
    initial_cash: float = 100000.0
    margin_requirement: float = 0.0

    def get_start_date(self) -> str:
        """Calculate start date if not provided"""
        if self.start_date:
            return self.start_date
        return (datetime.strptime(self.end_date, "%Y-%m-%d") - timedelta(days=90)).strftime("%Y-%m-%d")
