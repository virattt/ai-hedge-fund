import os
from dataclasses import dataclass


@dataclass
class BaseAPIConfig:
    """Configuration for the Financial Datasets API."""

    api_key: str
    base_url: str

    @classmethod
    def from_env(cls) -> "BaseAPIConfig":
        """Create configuration from environment variables."""
        pass


@dataclass
class FinancialDatasetAPIConfig(BaseAPIConfig):
    """Configuration for the Financial Datasets API."""

    api_key: str
    base_url: str = "https://api.financialdatasets.ai"

    @classmethod
    def from_env(cls) -> "FinancialDatasetAPIConfig":
        """Create configuration from environment variables."""
        api_key = os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if not api_key:
            raise ValueError("FINANCIAL_DATASETS_API_KEY environment variable not set")
        return cls(api_key=api_key)
