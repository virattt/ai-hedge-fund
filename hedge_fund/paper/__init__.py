"""Paper trading — a deployed fund, its ledger, and the tick that advances it.

    paper/<name>/fund.yaml        the DeployedFund: mandate snapshot + universe
    paper/<name>/ledger/          one SessionRecord per session, hash-chained
                                  (a minute fund's bars sit in a directory per day,
                                  with a checkpoint once the day closes)
    paper/<name>/ledger/superseded/   records replaced by a redo, off the chain
    paper/<name>/broker.json      the PaperBroker's own book
    paper/<name>/control.json     the kill switch
    paper/<name>/events.jsonl     halts, failures, resumes, gaps, checkpoints
    paper/<name>/runner.pid       the minute fund's runner, while it is alive

`tick` is what a scheduler calls after each close; `run` is the loop a
minute fund lives in. Backtests never import anything from here: research
reads the shared data cache and writes only to research/.
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
from hedge_fund.paper.runner import is_running, PID_FILE, run, serve, stop_runner
from hedge_fund.paper.tick import MinuteFund, next_session, NothingDue, redo, tick

__all__ = [
    "DeployedFund",
    "FUND_FILE",
    "Ledger",
    "LedgerError",
    "MinuteFund",
    "NothingDue",
    "PID_FILE",
    "deploy",
    "is_running",
    "list_deployed",
    "load_deployed",
    "next_session",
    "redo",
    "run",
    "serve",
    "stop_runner",
    "tick",
    "validate_fund_name",
]
