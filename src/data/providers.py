"""Data provider configuration and utilities."""

from enum import Enum
from pydantic import BaseModel
from typing import Tuple


class DataProvider(str, Enum):
    """Enum for supported data providers"""
    
    FINANCIAL_DATASETS = "FinancialDatasets"
    YFINANCE = "Yahoo Finance"


class DataSourceModel(BaseModel):
    """Represents a data source configuration"""
    
    display_name: str
    provider: DataProvider
    requires_api_key: bool
    description: str
    
    def to_choice_tuple(self) -> Tuple[str, str]:
        """Convert to format needed for questionary choices"""
        return (self.display_name, self.provider.value)


# Data source configurations
DATA_SOURCES = {
    "financial_datasets": DataSourceModel(
        display_name="Financial Datasets API (Premium)",
        provider=DataProvider.FINANCIAL_DATASETS,
        requires_api_key=True,
        description="Professional grade financial data with extended coverage"
    ),
    "yfinance": DataSourceModel(
        display_name="Yahoo Finance (Free)",
        provider=DataProvider.YFINANCE,
        requires_api_key=False,
        description="Free financial data from Yahoo Finance"
    ),
}

# Order for display in CLI (yfinance first as default)
DATA_SOURCE_ORDER = [
    (
        DATA_SOURCES["yfinance"].display_name,
        "yfinance",
        DATA_SOURCES["yfinance"].provider.value
    ),
    (
        DATA_SOURCES["financial_datasets"].display_name,
        "financial_datasets", 
        DATA_SOURCES["financial_datasets"].provider.value
    ),
]


def get_data_source_info(provider_key: str) -> DataSourceModel:
    """Get data source configuration by key"""
    return DATA_SOURCES.get(provider_key)


def get_default_data_provider() -> str:
    """Get the default data provider for the system"""
    return "yfinance"  # Default to free option


def get_data_provider_for_agent(state: dict, agent_id: str = None) -> str:
    """
    Get the appropriate data provider for an agent from state.
    Centralizes data provider logic and removes hardcoded defaults from agents.
    
    Args:
        state: Agent state containing metadata
        agent_id: Optional agent ID for agent-specific overrides
        
    Returns:
        str: Data provider key (e.g., "yfinance", "financial_datasets")
    """
    # Check if data provider is specified in metadata
    metadata = state.get("metadata", {})
    data_provider = metadata.get("data_provider")
    
    if data_provider:
        return data_provider
    
    # Agent-specific defaults (if needed)
    agent_specific_defaults = {
        "technicals_agent": "financial_datasets",
        "technical_analyst_agent": "financial_datasets",
    }
    
    if agent_id and agent_id in agent_specific_defaults:
        return agent_specific_defaults[agent_id]
    
    # System default
    return get_default_data_provider()