"""Orchestrate one live-trading cycle: sync → analyze → execute."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from colorama import Fore, Style, init

from integrations.alpaca.broker import AlpacaBroker
from integrations.alpaca.config import AlpacaConfig, load_alpaca_config
from integrations.alpaca.executor import decisions_to_orders, execute_orders
from integrations.alpaca.portfolio_sync import merge_tickers, positions_to_portfolio
from integrations.broker.models import OrderResult
from integrations.broker.noop import NoOpBroker
from integrations.alpaca.light_cycle import run_light_analysis
from integrations.alpaca.strategy import CycleKind
from integrations.broker.protocol import BrokerClient
from src.main import run_hedge_fund
from src.utils.display import print_trading_output

init(autoreset=True)
logger = logging.getLogger(__name__)


@dataclass
class CycleInputs:
    tickers: list[str]
    start_date: str
    end_date: str
    show_reasoning: bool
    selected_analysts: list[str]
    model_name: str
    model_provider: str
    margin_requirement: float
    initial_cash: float
    execute: bool = False
    save_ledger: bool = True
    cycle_kind: CycleKind = "heavy"
    trigger_reason: str | None = None


@dataclass
class CycleResult:
    broker_name: str
    portfolio: dict
    agent_result: dict[str, Any]
    orders: list
    execution_results: list[OrderResult]
    account_summary: str


def create_broker(
    broker_name: str,
    *,
    initial_cash: float,
    margin_requirement: float,
    execute: bool = False,
) -> tuple[BrokerClient, AlpacaConfig | None]:
    if broker_name == "alpaca":
        config = load_alpaca_config(execute=execute)
        return AlpacaBroker(config), config

    return NoOpBroker(cash=initial_cash), None


def build_portfolio(
    broker: BrokerClient,
    tickers: list[str],
    *,
    margin_requirement: float,
    initial_cash: float,
) -> dict:
    account = broker.get_account()
    positions = broker.get_positions()
    merged_tickers = merge_tickers(tickers, positions)

    if broker.name == "noop":
        return {
            "cash": initial_cash,
            "margin_requirement": margin_requirement,
            "margin_used": 0.0,
            "positions": {
                ticker: {
                    "long": 0,
                    "short": 0,
                    "long_cost_basis": 0.0,
                    "short_cost_basis": 0.0,
                    "short_margin_used": 0.0,
                }
                for ticker in merged_tickers
            },
            "realized_gains": {ticker: {"long": 0.0, "short": 0.0} for ticker in merged_tickers},
        }

    return positions_to_portfolio(
        account=account,
        positions=positions,
        tickers=merged_tickers,
        margin_requirement=margin_requirement,
    )


def run_cycle(
    broker_name: str,
    inputs: CycleInputs,
) -> CycleResult:
    broker, config = create_broker(
        broker_name,
        initial_cash=inputs.initial_cash,
        margin_requirement=inputs.margin_requirement,
        execute=inputs.execute,
    )

    portfolio = build_portfolio(
        broker,
        inputs.tickers,
        margin_requirement=inputs.margin_requirement,
        initial_cash=inputs.initial_cash,
    )
    tickers = list(portfolio["positions"].keys())

    _print_broker_header(broker, config)

    if inputs.cycle_kind == "light":
        agent_result = run_light_analysis(
            tickers=tickers,
            portfolio=portfolio,
            start_date=inputs.start_date,
            end_date=inputs.end_date,
            light_analysts=inputs.selected_analysts,
            show_reasoning=inputs.show_reasoning,
        )
    else:
        agent_result = run_hedge_fund(
            tickers=tickers,
            start_date=inputs.start_date,
            end_date=inputs.end_date,
            portfolio=portfolio,
            show_reasoning=inputs.show_reasoning,
            selected_analysts=inputs.selected_analysts,
            model_name=inputs.model_name,
            model_provider=inputs.model_provider,
        )

    print_trading_output(agent_result)

    orders = decisions_to_orders(agent_result.get("decisions"))
    reference_prices = _extract_reference_prices(agent_result)

    vetoed: list[OrderResult] = []
    governor = None
    if config is not None:  # live/paper Alpaca — enforce portfolio guardrails
        from integrations.alpaca.risk_governor import RiskGovernor

        governor = RiskGovernor()
        orders, vetoed = governor.filter_orders(
            orders,
            positions=portfolio.get("positions", {}),
            equity=portfolio.get("equity"),
            prices=reference_prices,
            cycle_kind=inputs.cycle_kind,
            decisions=agent_result.get("decisions"),
        )
        for veto in vetoed:
            print(
                f"{Fore.YELLOW}Vetoed: {veto.order.ticker} {veto.order.action.upper()} "
                f"{veto.order.quantity} — {veto.message}{Style.RESET_ALL}"
            )

    execution_results = execute_orders(
        broker,
        orders,
        config=config,
        reference_prices=reference_prices,
    )
    if governor is not None:
        governor.record_submissions(execution_results, reference_prices)
        execution_results = execution_results + vetoed

    _print_execution_summary(broker, execution_results)

    account = broker.get_account()
    account_summary = (
        f"Cash: ${account.cash:,.2f} | "
        f"Equity: ${account.equity:,.2f} | "
        f"Portfolio: ${account.portfolio_value:,.2f}"
    )

    result = CycleResult(
        broker_name=broker.name,
        portfolio=portfolio,
        agent_result=agent_result,
        orders=orders,
        execution_results=execution_results,
        account_summary=account_summary,
    )

    if inputs.save_ledger:
        from integrations.alpaca.ledger import save_cycle

        ledger_path = save_cycle(
            result,
            broker_name=broker.name,
            cycle_kind=inputs.cycle_kind,
            trigger_reason=inputs.trigger_reason,
        )
        print(f"\n{Fore.CYAN}Ledger saved: {ledger_path}{Style.RESET_ALL}")

    return result


def _extract_reference_prices(agent_result: dict[str, Any]) -> dict[str, float]:
    prices: dict[str, float] = {}
    for _agent, signals in agent_result.get("analyst_signals", {}).items():
        for ticker, signal in signals.items():
            price = signal.get("current_price")
            if price is not None:
                prices[ticker.upper()] = float(price)
    return prices


def _print_broker_header(broker: BrokerClient, config: AlpacaConfig | None) -> None:
    print(f"\n{Fore.CYAN}{Style.BRIGHT}Broker: {broker.name}{Style.RESET_ALL}")
    account = broker.get_account()
    print(
        f"Account — Cash: ${account.cash:,.2f} | "
        f"Equity: ${account.equity:,.2f} | "
        f"Buying power: ${account.buying_power:,.2f}"
    )

    positions = broker.get_positions()
    if positions:
        print(f"{Fore.WHITE}Open positions:{Style.RESET_ALL}")
        for pos in positions:
            print(
                f"  {pos.ticker}: {pos.quantity:+d} @ ${pos.avg_entry_price:,.2f} "
                f"(mkt ${pos.market_value:,.2f})"
            )
    else:
        print(f"{Fore.YELLOW}No open positions at broker.{Style.RESET_ALL}")

    if config is not None:
        mode = config.mode_label
        color = Fore.GREEN if config.paper else Fore.RED
        print(f"Trading mode: {color}{mode}{Style.RESET_ALL}")
        if isinstance(broker, AlpacaBroker):
            clock = broker.get_market_clock()
            status = "OPEN" if clock.is_open else "CLOSED"
            print(f"Market: {status}")


def _print_execution_summary(broker: BrokerClient, results: list[OrderResult]) -> None:
    actionable = [r for r in results if r.order.action != "hold" and r.order.quantity > 0]
    if not actionable:
        print(f"\n{Fore.YELLOW}No trade orders to execute.{Style.RESET_ALL}")
        return

    print(f"\n{Fore.WHITE}{Style.BRIGHT}Execution Summary ({broker.name}){Style.RESET_ALL}")
    print(f"{Fore.WHITE}{'=' * 50}{Style.RESET_ALL}")
    for result in actionable:
        order = result.order
        if result.submitted:
            status = f"{Fore.GREEN}SUBMITTED{Style.RESET_ALL}"
        elif result.dry_run:
            status = f"{Fore.YELLOW}DRY RUN{Style.RESET_ALL}"
        else:
            status = f"{Fore.RED}BLOCKED{Style.RESET_ALL}"
        print(
            f"  {order.ticker}: {order.action.upper()} {order.quantity} — "
            f"{status} — {result.message}"
        )

