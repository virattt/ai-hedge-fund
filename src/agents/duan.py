
from typing import Literal

from pydantic import BaseModel, Field
from src.graph.state import AgentState
"""
============================================================================
BaseModel 是 Pydantic 的核心类，用来做数据建模 + 校验 + 解析 + 序列化。

你可以把它理解为一句话：

👉 “带类型检查能力的 Python 数据结构（比 dataclass 更强的版本）”
"""
class duanSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int=Field(description="Confidence 0-100")
    reasoning: str=Field(description="Reasoning for the signal")
    

def duan_agent(state: AgentState, agent_id: str = "duan_agent"):            
        