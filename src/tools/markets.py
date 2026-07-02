"""Market detection helpers shared across data sources and trading engines."""
from __future__ import annotations

import re

# Tushare-style A-share ticker: 6-digit code + .SH (Shanghai) / .SZ (Shenzhen) / .BJ (Beijing)
_A_SHARE_PATTERN = re.compile(r"^\d{6}\.(SH|SZ|BJ)$")


def is_a_share(ticker: str | None) -> bool:
    """True for Chinese A-share tickers in Tushare format.

    Examples: ``600519.SH`` (Kweichow Moutai, SHA), ``000001.SZ`` (Ping Yi Bank, SZA),
    ``830799.BJ`` (Beijing Stock Exchange).
    """
    return bool(ticker) and bool(_A_SHARE_PATTERN.match(ticker))  # type: ignore[arg-type]


def a_share_code(ticker: str) -> str:
    """Return the 6-digit bare code (no exchange suffix) expected by akshare."""
    return ticker.split(".", 1)[0]
