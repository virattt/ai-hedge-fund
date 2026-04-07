"""Market state verification agent — pre-trade gate using Headless Oracle.

Checks whether exchanges are open before the portfolio manager places orders.
Uses the free /v5/demo endpoint (no API key required, no new dependencies).
Fail-closed: if the oracle is unreachable or returns anything other than OPEN,
the ticker is marked as blocked and the portfolio manager should hold.
"""

import json
from urllib.request import urlopen, Request
from urllib.error import URLError
from langchain_core.messages import HumanMessage
from src.graph.state import AgentState, show_agent_reasoning
from src.utils.progress import progress

# Maps common ticker suffixes to ISO 10383 Market Identifier Codes (MICs).
# US equities (no suffix) default to XNYS. Extend as needed.
SUFFIX_TO_MIC: dict[str, str] = {
    "":     "XNYS",   # US equities (default)
    ".L":   "XLON",   # London
    ".T":   "XJPX",   # Tokyo
    ".PA":  "XPAR",   # Paris
    ".HK":  "XHKG",   # Hong Kong
    ".SI":  "XSES",   # Singapore
    ".AX":  "XASX",   # Australia
    ".BO":  "XBOM",   # BSE India
    ".NS":  "XNSE",   # NSE India
    ".SS":  "XSHG",   # Shanghai
    ".SZ":  "XSHE",   # Shenzhen
    ".KS":  "XKRX",   # Korea
    ".JO":  "XJSE",   # Johannesburg
    ".SA":  "XBSP",   # Brazil
    ".SW":  "XSWX",   # Switzerland
    ".MI":  "XMIL",   # Milan
    ".IS":  "XIST",   # Istanbul
    ".NZ":  "XNZE",   # New Zealand
    ".HE":  "XHEL",   # Helsinki
    ".ST":  "XSTO",   # Stockholm
}

ORACLE_BASE_URL = "https://headlessoracle.com"


def ticker_to_mic(ticker: str) -> str:
    """Convert a ticker symbol to its exchange MIC code."""
    for suffix, mic in SUFFIX_TO_MIC.items():
        if suffix and ticker.upper().endswith(suffix.upper()):
            return mic
    return "XNYS"  # Default: US equities


def fetch_market_status(mic: str, timeout: int = 5) -> dict:
    """Fetch market status from Headless Oracle. Returns receipt dict or error dict."""
    url = f"{ORACLE_BASE_URL}/v5/demo?mic={mic}"
    try:
        req = Request(url, headers={"User-Agent": "ai-hedge-fund/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            # Response wraps receipt in a 'receipt' field
            return data.get("receipt", data)
    except (URLError, OSError, json.JSONDecodeError, KeyError) as e:
        return {"status": "UNKNOWN", "error": str(e), "mic": mic}


def market_state_verification_agent(state: AgentState, agent_id: str = "market_state_verifier"):
    """Verifies exchange status for all tickers before portfolio decisions.

    For each ticker, calls the Headless Oracle to check if the exchange is OPEN.
    Results are stored in state["data"]["analyst_signals"][agent_id] and a
    summary message is added for the portfolio manager.

    Fail-closed: UNKNOWN, CLOSED, HALTED, or any error → ticker is blocked.
    """
    data = state["data"]
    tickers = data["tickers"]

    market_states: dict[str, dict] = {}
    blocked_tickers: list[str] = []
    open_tickers: list[str] = []

    # Deduplicate MICs to avoid redundant API calls
    mic_results: dict[str, dict] = {}

    for ticker in tickers:
        mic = ticker_to_mic(ticker)
        progress.update_status(agent_id, ticker, f"Checking {mic} market status")

        if mic not in mic_results:
            mic_results[mic] = fetch_market_status(mic)

        result = mic_results[mic]
        status = result.get("status", "UNKNOWN")

        market_states[ticker] = {
            "mic": mic,
            "status": status,
            "is_open": status == "OPEN",
            "issued_at": result.get("issued_at"),
            "expires_at": result.get("expires_at"),
        }

        if status == "OPEN":
            open_tickers.append(ticker)
        else:
            blocked_tickers.append(ticker)
            market_states[ticker]["warning"] = (
                f"Exchange {mic} is {status} — trading blocked for {ticker}"
            )

    # Build summary message for downstream agents
    if blocked_tickers:
        warning = (
            f"⚠ MARKET STATE WARNING: The following tickers are on exchanges that "
            f"are NOT currently open: {', '.join(blocked_tickers)}. "
            f"These tickers should be held (no buy/sell/short/cover). "
            f"Only these tickers have open exchanges: {', '.join(open_tickers) or 'none'}."
        )
    else:
        warning = (
            f"All {len(open_tickers)} exchanges are OPEN. Safe to proceed with trading."
        )

    message = HumanMessage(
        content=json.dumps({
            "market_state_verification": {
                "summary": warning,
                "open_count": len(open_tickers),
                "blocked_count": len(blocked_tickers),
                "blocked_tickers": blocked_tickers,
                "details": market_states,
            }
        }),
        name=agent_id,
    )

    # Show reasoning if enabled
    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(
            {"market_states": market_states, "blocked": blocked_tickers},
            agent_id,
        )

    progress.update_status(agent_id, None, "Done")

    return {
        "messages": [message],
        "data": {
            "analyst_signals": {
                agent_id: market_states,
            },
            "market_state": market_states,
        },
    }
