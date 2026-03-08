"""Fetch live options chains from Tastytrade API."""

from typing import Any

try:
    from tastytrade import Session
    _HAS_TASTY = True
except ImportError:
    _HAS_TASTY = False
    Session = None  # type: ignore


class OptionsChainFetcher:
    """
    Pull live option chains from Tastytrade. Requires tastytrade package and
    a valid session (login + token).
    """

    def __init__(self, session: Any = None):
        if not _HAS_TASTY:
            raise RuntimeError("tastytrade package is required: pip install tastytrade")
        self._session = session

    def set_session(self, session: Any) -> None:
        self._session = session

    def get_chain(
        self,
        symbol: str,
        expiry_from: str | None = None,
        expiry_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return list of option instruments (strike, expiry, type, symbol).
        expiry format YYYY-MM-DD. When session is None, returns [].
        """
        if self._session is None:
            return []
        try:
            from tastytrade.instruments import get_option_chain
            chain = get_option_chain(self._session, symbol)
            out: list[dict[str, Any]] = []
            for opt in getattr(chain, "data", []) or []:
                exp = getattr(opt, "expiration_date", None) or getattr(opt, "expirationDate", "")
                strike = getattr(opt, "strike_price", None) or getattr(opt, "strikePrice", 0)
                typ = getattr(opt, "option_type", None) or getattr(opt, "optionType", "call")
                sym = getattr(opt, "symbol", None) or ""
                if expiry_from and str(exp) < expiry_from:
                    continue
                if expiry_to and str(exp) > expiry_to:
                    continue
                out.append({
                    "symbol": sym,
                    "strike": float(strike),
                    "expiry": str(exp),
                    "option_type": typ.lower() if typ else "call",
                })
            return out
        except Exception:
            return []
