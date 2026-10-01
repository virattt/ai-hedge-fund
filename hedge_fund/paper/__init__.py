"""Paper trading — a deployed fund, its ledger, and the tick that advances it.

    paper/<name>/fund.yaml        the DeployedFund: mandate snapshot + universe
    paper/<name>/ledger/          one SessionRecord per session, hash-chained
    paper/<name>/ledger/superseded/   records replaced by a redo, off the chain
    paper/<name>/broker.json      the PaperBroker's own book
    paper/<name>/control.json     the kill switch
    paper/<name>/events.jsonl     halts, failures, resumes

`tick` is what a scheduler calls after each close. Backtests never import
anything from here: research reads the shared data cache and writes only to
research/.
"""

from hedge_fund.paper.deployed import (
    deploy,
    DeployedFund,
    FUND_FILE,
    list_deployed,
    load_deployed,
    validate_fund_name,
)
from hedge_fund.paper.ledger import Ledger, LedgerError
from hedge_fund.paper.tick import next_session, NothingDue, redo, tick

__all__ = [
    "DeployedFund",
    "FUND_FILE",
    "Ledger",
    "LedgerError",
    "NothingDue",
    "deploy",
    "list_deployed",
    "load_deployed",
    "next_session",
    "redo",
    "tick",
    "validate_fund_name",
]
