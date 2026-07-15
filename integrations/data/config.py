"""Data provider configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class DataConfig:
    provider: str
    alpaca_api_key: str
    alpaca_secret_key: str
    finnhub_api_key: str


def load_data_config() -> DataConfig:
    provider = os.getenv("DATA_PROVIDER", "financialdatasets").strip().lower()
    return DataConfig(
        provider=provider,
        alpaca_api_key=os.getenv("ALPACA_API_KEY", "").strip(),
        alpaca_secret_key=os.getenv("ALPACA_SECRET_KEY", "").strip(),
        finnhub_api_key=os.getenv("FINNHUB_API_KEY", "").strip(),
    )


def validate_composite_config(config: DataConfig) -> None:
    missing = []
    if not config.alpaca_api_key:
        missing.append("ALPACA_API_KEY")
    if not config.alpaca_secret_key:
        missing.append("ALPACA_SECRET_KEY")
    if not config.finnhub_api_key:
        missing.append("FINNHUB_API_KEY")
    if missing:
        raise ValueError(
            "Composite data provider requires: "
            + ", ".join(missing)
            + ". Get Finnhub key at https://finnhub.io/register"
        )
