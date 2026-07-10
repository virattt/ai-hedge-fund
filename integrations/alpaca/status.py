"""Show Alpaca account status without running agents."""

from __future__ import annotations

import sys

from colorama import Fore, Style, init

from integrations.alpaca.broker import AlpacaBroker
from integrations.alpaca.config import load_alpaca_config

init(autoreset=True)


def cmd_status() -> int:
    try:
        config = load_alpaca_config()
        broker = AlpacaBroker(config)
    except (ValueError, ImportError) as exc:
        print(f"{Fore.RED}Error: {exc}{Style.RESET_ALL}", file=sys.stderr)
        return 1

    account = broker.get_account()
    positions = broker.get_positions()
    clock = broker.get_market_clock()
    open_orders = broker.get_open_orders()

    mode = config.mode_label
    mode_color = Fore.RED if mode == "LIVE" else Fore.GREEN if config.paper else Fore.YELLOW
    market_color = Fore.GREEN if clock.is_open else Fore.RED

    print(f"\n{Fore.CYAN}{Style.BRIGHT}Alpaca Account Status{Style.RESET_ALL}")
    print(f"{Fore.WHITE}{'=' * 50}{Style.RESET_ALL}")
    print(f"Mode:           {mode_color}{mode}{Style.RESET_ALL}")
    print(f"Execution:      {'enabled' if config.execution_enabled else 'disabled (read-only)'}")
    print(f"Shorting:       {'enabled' if broker.shorting_enabled() else 'disabled'}")
    print(f"Trading block:  {'YES' if broker.trading_blocked() else 'no'}")
    print(f"Market:         {market_color}{'OPEN' if clock.is_open else 'CLOSED'}{Style.RESET_ALL}")
    if clock.next_open:
        print(f"Next open:      {clock.next_open}")
    if clock.next_close:
        print(f"Next close:     {clock.next_close}")
    print()
    print(f"Cash:           ${account.cash:,.2f}")
    print(f"Equity:         ${account.equity:,.2f}")
    print(f"Buying power:   ${account.buying_power:,.2f}")
    print(f"Portfolio:      ${account.portfolio_value:,.2f}")

    if positions:
        print(f"\n{Fore.WHITE}{Style.BRIGHT}Positions{Style.RESET_ALL}")
        for pos in positions:
            print(
                f"  {pos.ticker:6s} {pos.quantity:+6d}  "
                f"avg ${pos.avg_entry_price:>8,.2f}  "
                f"mkt ${pos.market_value:>10,.2f}"
            )
    else:
        print(f"\n{Fore.YELLOW}No open positions.{Style.RESET_ALL}")

    if open_orders:
        print(f"\n{Fore.WHITE}{Style.BRIGHT}Open Orders{Style.RESET_ALL}")
        for order in open_orders:
            print(
                f"  {order.ticker:6s} {order.side:4s} {order.quantity:>6.0f}  "
                f"status={order.status}  id={order.order_id[:8]}..."
            )
    else:
        print(f"\n{Fore.YELLOW}No open orders.{Style.RESET_ALL}")

    print()
    return 0
