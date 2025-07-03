"""Live trading implementation using the hedge fund AI agents."""

import sys
import time
import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from colorama import Fore, Style

from .broker_base import BrokerBase, Position, Order
from .alpaca_broker import AlpacaBroker
from src.main import run_hedge_fund
from src.utils.progress import progress


logger = logging.getLogger(__name__)


class Trader:
    """Live trading implementation using AI hedge fund decisions."""
    
    def __init__(
        self,
        broker: BrokerBase,
        tickers: list[str],
        selected_analysts: list[str] = None,
        model_name: str = "gpt-4o",
        model_provider: str = "OpenAI",
        available_capital: float = None,  # Override available capital
        margin_requirement: float = None,  # Margin requirement for short positions
        dry_run: bool = False,
        ignore_market_hours: bool = False
    ):
        """Initialize the trader.
        
        Args:
            broker: Broker implementation to use.
            tickers: List of tickers to trade.
            selected_analysts: List of analysts to use.
            model_name: LLM model name.
            model_provider: LLM provider.
            available_capital: Override available capital (uses broker cash if None).
            margin_requirement: Margin requirement ratio for short positions.
            dry_run: If True, log trades but don't execute them.
            ignore_market_hours: If True, run even when market is closed.
        """
        self.broker = broker
        self.tickers = tickers
        self.selected_analysts = selected_analysts or []
        self.model_name = model_name
        self.model_provider = model_provider
        self.available_capital = available_capital
        self.margin_requirement = margin_requirement
        self.dry_run = dry_run
        self.ignore_market_hours = ignore_market_hours
        
        # Track our virtual portfolio for decision making
        self.virtual_portfolio = None
        self.last_sync_time = None
    
    def _map_order_to_action(self, order: Order, symbol: str) -> str:
        """Map a broker order to our action type."""
        if order.side == "buy":
            # Could be buy or cover - check if we have short positions
            current_pos = self.broker.get_position(symbol)
            if current_pos and current_pos.side == "short":
                return "cover"
            else:
                return "buy"
        elif order.side == "sell":
            # Could be sell or short - check if we have long positions
            current_pos = self.broker.get_position(symbol)
            if current_pos and current_pos.side == "long":
                return "sell"
            else:
                return "short"
        else:
            return "unknown"
    
    def _close_position_and_wait(self, symbol: str, position_type: str, position_size: float) -> Order:
        """Close existing position and wait for fill.
        
        Args:
            symbol: Stock symbol
            position_type: 'long' or 'short'
            position_size: Number of shares to close
            
        Returns:
            Order: The close order
        """
        if position_type == "long":
            action_name = "close long"
            order_side = "sell"
        else:  # short
            action_name = "close short"
            order_side = "buy"
        
        print(f"{Fore.CYAN}Step 1: {action_name.title()} - {order_side} {position_size} shares{Style.RESET_ALL}")
        close_order = self.broker.place_order(symbol, position_size, order_side)
        print(f"{Fore.GREEN}Close order placed: {close_order.id}{Style.RESET_ALL}")
        
        # Wait for close order to fill
        self._wait_for_order_fill(close_order.id, action_name)
        return close_order
    
    def _wait_for_order_fill(self, order_id: str, action_name: str) -> None:
        """Wait for order to fill with timeout.
        
        Args:
            order_id: Order ID to monitor
            action_name: Human-readable action name for logging
        """
        print(f"{Fore.CYAN}Waiting for {action_name} order to fill...{Style.RESET_ALL}")
        max_wait_time = 30  # seconds
        wait_time = 0
        while wait_time < max_wait_time:
            updated_order = self.broker.get_order(order_id)
            if updated_order and updated_order.status == "filled":
                print(f"{Fore.GREEN}{action_name.title()} order filled successfully{Style.RESET_ALL}")
                return
            time.sleep(2)
            wait_time += 2
        
        print(f"{Fore.YELLOW}{action_name.title()} order still pending after {max_wait_time}s, proceeding anyway{Style.RESET_ALL}")
    
    def _execute_position_transition(self, symbol: str, action: str, quantity: float, 
                                   current_long: float, current_short: float) -> Order:
        """Execute position transition with proper sequencing.
        
        Args:
            symbol: Stock symbol
            action: Target action (buy/sell/short/cover)
            quantity: Total quantity for the action
            current_long: Current long position size
            current_short: Current short position size
            
        Returns:
            Order: The final order executed
        """
        if action == "buy" and current_short > 0:
            # Short -> Long transition
            print(f"{Fore.CYAN}Detected short position of {current_short} shares, splitting buy order{Style.RESET_ALL}")
            
            # Close short position
            cover_quantity = min(quantity, current_short)
            close_order = self._close_position_and_wait(symbol, "short", cover_quantity)
            
            # Buy remaining for long position
            remaining_quantity = quantity - cover_quantity
            if remaining_quantity > 0:
                print(f"{Fore.CYAN}Step 2: Buying {remaining_quantity} additional shares for long position{Style.RESET_ALL}")
                return self.broker.place_order(symbol, remaining_quantity, "buy")
            else:
                print(f"{Fore.CYAN}Short position fully covered, no additional long position needed{Style.RESET_ALL}")
                return close_order
                
        elif action == "sell" and current_long > 0 and quantity > current_long:
            # Long -> Short transition (selling more than owned)
            print(f"{Fore.CYAN}Detected long position of {current_long} shares, splitting sell order{Style.RESET_ALL}")
            
            # Close long position
            close_order = self._close_position_and_wait(symbol, "long", current_long)
            
            # Short sell remaining
            remaining_quantity = quantity - current_long
            print(f"{Fore.CYAN}Step 2: Short selling {remaining_quantity} additional shares{Style.RESET_ALL}")
            return self.broker.place_order(symbol, remaining_quantity, "sell_short")
            
        elif action == "short" and current_long > 0:
            # Long -> Short transition (close long first)
            print(f"{Fore.CYAN}Detected long position of {current_long} shares, closing before short sale{Style.RESET_ALL}")
            
            # Close long position
            self._close_position_and_wait(symbol, "long", current_long)
            
            # Short sell the requested quantity
            print(f"{Fore.CYAN}Step 2: Short selling {quantity} shares{Style.RESET_ALL}")
            return self.broker.place_order(symbol, quantity, "sell_short")
            
        elif action == "cover" and current_short > 0 and quantity > current_short:
            # Short -> Long transition (covering more than short)
            print(f"{Fore.CYAN}Detected short position of {current_short} shares, splitting cover order{Style.RESET_ALL}")
            
            # Cover short position
            self._close_position_and_wait(symbol, "short", current_short)
            
            # Buy remaining for long position
            remaining_quantity = quantity - current_short
            print(f"{Fore.CYAN}Step 2: Buying {remaining_quantity} additional shares for long position{Style.RESET_ALL}")
            return self.broker.place_order(symbol, remaining_quantity, "buy")
            
        else:
            # No position transition needed - execute normal order
            return self._execute_simple_order(symbol, action, quantity, current_long, current_short)
    
    def _execute_simple_order(self, symbol: str, action: str, quantity: float,
                            current_long: float, current_short: float) -> Order | None:
        """Execute simple order without position transitions.
        
        Args:
            symbol: Stock symbol
            action: Trading action
            quantity: Number of shares
            current_long: Current long position
            current_short: Current short position
            
        Returns:
            Order or None if cannot execute
        """
        if action == "buy":
            return self.broker.place_order(symbol, quantity, "buy")
        elif action == "sell":
            if current_long > 0:
                return self.broker.place_order(symbol, quantity, "sell")
            else:
                print(f"{Fore.YELLOW}Cannot sell {symbol}: no long position{Style.RESET_ALL}")
                return None
        elif action == "short":
            return self.broker.place_order(symbol, quantity, "sell_short")
        elif action == "cover":
            if current_short > 0:
                return self.broker.place_order(symbol, quantity, "buy")
            else:
                print(f"{Fore.YELLOW}Cannot cover {symbol}: no short position{Style.RESET_ALL}")
                return None
        else:
            print(f"{Fore.RED}Unknown action: {action}{Style.RESET_ALL}")
            return None

    def _handle_hold_decision(self, symbol: str) -> Order | None:
        """Handle AI decision to hold - cancel any pending orders."""
        if self.dry_run:
            print(f"{Fore.CYAN}DRY RUN: Would hold {symbol} (cancel any pending orders){Style.RESET_ALL}")
            return None
        
        # Get pending orders and cancel them
        pending_orders = [order for order in self.broker.get_orders() 
                         if order.symbol == symbol and order.status in ["pending_new", "new", "accepted"]]
        
        if pending_orders:
            print(f"{Fore.CYAN}AI says hold {symbol}, canceling {len(pending_orders)} pending orders{Style.RESET_ALL}")
            for order in pending_orders:
                action = self._map_order_to_action(order, symbol)
                print(f"{Fore.YELLOW}Canceling pending {action} order for {order.quantity} shares{Style.RESET_ALL}")
                if self.broker.cancel_order(order.id):
                    print(f"{Fore.GREEN}Canceled order {order.id}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Failed to cancel order {order.id}{Style.RESET_ALL}")
        else:
            print(f"{Fore.CYAN}Holding {symbol} (no pending orders to cancel){Style.RESET_ALL}")
        
        return None
        
    def connect(self) -> bool:
        """Connect to the broker."""
        return self.broker.connect()
    
    def disconnect(self) -> None:
        """Disconnect from the broker."""
        self.broker.disconnect()
    
    def sync_portfolio(self) -> None:
        """Sync virtual portfolio with actual broker positions."""
        # Temporarily stop progress display to show debug output
        was_started = progress.started
        if was_started:
            progress.stop()
        
        try:
            # Ensure broker connection is active with retry
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    if not self.broker._connected:
                        print(f"{Fore.YELLOW}Reconnecting to broker (attempt {attempt + 1})...{Style.RESET_ALL}")
                        self.broker.connect()
                    
                    account = self.broker.get_account()
                    positions = self.broker.get_positions()
                    pending_orders = self.broker.get_orders() if not self.dry_run else []
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"{Fore.YELLOW}Connection failed, retrying in 5 seconds... ({e}){Style.RESET_ALL}")
                        time.sleep(5)
                        self.broker._connected = False  # Force reconnection
                    else:
                        raise  # Re-raise if all retries failed
            
            # Create virtual portfolio structure similar to backtester
            # Use limited capital if specified, but keep the account's margin capability
            actual_cash = account.cash
            limited_cash = self.available_capital if self.available_capital is not None else actual_cash
            
            # Calculate the fraction of available capital we're using
            capital_fraction = limited_cash / actual_cash if actual_cash > 0 else 1.0
            
            self.virtual_portfolio = {
                "cash": limited_cash,
                "margin_requirement": self.margin_requirement if self.margin_requirement is not None else self.broker.get_margin_requirement(),
                "margin_used": account.initial_margin * capital_fraction,  # Scale margin usage proportionally
                "positions": {},
                "realized_gains": {},
                "pending_orders": {}  # Track pending orders
            }
            
            # Initialize all tickers
            for ticker in self.tickers:
                self.virtual_portfolio["positions"][ticker] = {
                    "long": 0,
                    "short": 0,
                    "long_cost_basis": 0.0,
                    "short_cost_basis": 0.0,
                    "short_margin_used": 0.0,
                }
                self.virtual_portfolio["realized_gains"][ticker] = {
                    "long": 0.0,
                    "short": 0.0,
                }
                self.virtual_portfolio["pending_orders"][ticker] = {
                    "buy": 0,
                    "sell": 0,
                    "short": 0,
                    "cover": 0,
                }
            
            # Update with actual positions
            print(f"{Fore.YELLOW}DEBUG: Syncing {len(positions)} positions from broker{Style.RESET_ALL}")
            for position in positions:
                print(f"DEBUG: Position {position.symbol}: {position.side} {position.quantity} shares")
                if position.symbol in self.virtual_portfolio["positions"]:
                    if position.side == "long":
                        self.virtual_portfolio["positions"][position.symbol]["long"] = position.quantity
                        self.virtual_portfolio["positions"][position.symbol]["long_cost_basis"] = position.avg_entry_price
                        print(f"DEBUG: Updated {position.symbol} long: {position.quantity} shares")
                    else:  # short
                        self.virtual_portfolio["positions"][position.symbol]["short"] = position.quantity
                        self.virtual_portfolio["positions"][position.symbol]["short_cost_basis"] = position.avg_entry_price
                        print(f"DEBUG: Updated {position.symbol} short: {position.quantity} shares")
                else:
                    print(f"DEBUG: Skipping {position.symbol} - not in tickers list")
            
            # Debug: Show what the virtual portfolio looks like after sync
            print(f"{Fore.YELLOW}DEBUG: Virtual portfolio positions after sync:{Style.RESET_ALL}")
            for ticker in self.tickers:
                pos = self.virtual_portfolio["positions"][ticker]
                print(f"  {ticker}: long={pos['long']}, short={pos['short']}")
            
            # Track pending orders
            for order in pending_orders:
                if order.symbol in self.virtual_portfolio["pending_orders"] and order.status in ["pending_new", "new", "accepted"]:
                    # Map order sides to our action types
                    if order.side == "buy":
                        action = "buy"
                    elif order.side == "sell":
                        # Need to determine if this is a sell or cover based on current position
                        current_pos = self.virtual_portfolio["positions"].get(order.symbol, {})
                        if current_pos.get("short", 0) > 0:
                            action = "cover"
                        else:
                            action = "sell"
                    else:
                        action = "short"  # sell_short
                    
                    self.virtual_portfolio["pending_orders"][order.symbol][action] += order.quantity
                    print(f"{Fore.CYAN}Found pending {action} order for {order.symbol}: {order.quantity} shares{Style.RESET_ALL}")
            
            self.last_sync_time = datetime.now()
            print(f"{Fore.GREEN}Portfolio synced with broker{Style.RESET_ALL}")
            
        except Exception as e:
            logger.error(f"Failed to sync portfolio: {e}")
            print(f"{Fore.RED}Failed to sync portfolio: {e}{Style.RESET_ALL}")
            raise
        finally:
            # Restart progress display if it was running
            if was_started:
                progress.start()
    
    def get_hedge_fund_decisions(self) -> dict:
        """Get trading decisions from the AI hedge fund."""
        if not self.virtual_portfolio:
            raise RuntimeError("Portfolio not synced. Call sync_portfolio() first.")
        
        # Use 30-day lookback period
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        print(f"{Fore.CYAN}Getting AI hedge fund decisions...{Style.RESET_ALL}")
        
        try:
            result = run_hedge_fund(
                tickers=self.tickers,
                start_date=start_date,
                end_date=end_date,
                portfolio=self.virtual_portfolio,
                show_reasoning=False,
                selected_analysts=self.selected_analysts,
                model_name=self.model_name,
                model_provider=self.model_provider,
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get hedge fund decisions: {e}")
            print(f"{Fore.RED}Failed to get hedge fund decisions: {e}{Style.RESET_ALL}")
            raise
    
    def calculate_position_size(self, symbol: str, decision: dict) -> float:
        """Get position size from AI decision (Risk Management Agent handles sizing)."""
        if not self.virtual_portfolio:
            raise RuntimeError("Portfolio not synced")
        
        # Trust the Risk Management Agent - just return what it calculated
        requested_quantity = decision.get("quantity", 0)
        return int(requested_quantity) if requested_quantity > 0 else 0
    
    def execute_trade(self, symbol: str, decision: dict) -> Order | None:
        """Execute a single trade based on AI decision."""
        action = decision.get("action", "hold")
        
        if action == "hold":
            return self._handle_hold_decision(symbol)
        
        # Calculate position size
        quantity = self.calculate_position_size(symbol, decision)
        if quantity <= 0:
            print(f"{Fore.YELLOW}Skipping {symbol}: quantity too small{Style.RESET_ALL}")
            return None
        
        # Check for existing pending orders and handle them
        if not self.dry_run:
            existing_orders = [order for order in self.broker.get_orders() 
                             if order.symbol == symbol and order.status in ["pending_new", "new", "accepted"]]
            
            for existing_order in existing_orders:
                # Determine the action of the existing order
                existing_action = self._map_order_to_action(existing_order, symbol)
                
                # If same action and same quantity, skip
                if existing_action == action and existing_order.quantity == quantity:
                    print(f"{Fore.CYAN}Skipping {symbol}: Identical {action} order for {quantity} shares already pending{Style.RESET_ALL}")
                    return None
                
                # Different action or quantity - cancel the existing order
                print(f"{Fore.YELLOW}Canceling existing {existing_action} order for {existing_order.quantity} shares to place new {action} order for {quantity} shares{Style.RESET_ALL}")
                if self.broker.cancel_order(existing_order.id):
                    print(f"{Fore.GREEN}Canceled order {existing_order.id}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Failed to cancel order {existing_order.id}{Style.RESET_ALL}")
        
        # Get current position
        current_position = self.broker.get_position(symbol)
        current_long = current_position.quantity if current_position and current_position.side == "long" else 0
        current_short = current_position.quantity if current_position and current_position.side == "short" else 0
        
        print(f"{Fore.CYAN}Executing {action} {quantity} shares of {symbol}{Style.RESET_ALL}")
        
        if self.dry_run:
            print(f"{Fore.YELLOW}DRY RUN: Would {action} {quantity} shares of {symbol} at current price{Style.RESET_ALL}")
            # Create a mock order for dry run
            return Order(
                id=f"DRY_RUN_{symbol}_{action}_{int(time.time())}",
                symbol=symbol,
                quantity=quantity,
                side=action,
                order_type="market",
                status="filled",
                filled_price=0.0,  # Would need current price in real scenario
                filled_quantity=quantity
            )
        
        try:
            # Double-check dry run protection
            if self.dry_run:
                print(f"{Fore.RED}ERROR: Attempted to place real order in dry-run mode! This should not happen.{Style.RESET_ALL}")
                return None
            
            # Execute order with smart position transition handling
            order = self._execute_position_transition(symbol, action, quantity, current_long, current_short)
            
            if order:
                print(f"{Fore.GREEN}Order placed: {order.id} - {action} {order.quantity} {symbol}{Style.RESET_ALL}")
            return order
            
        except Exception as e:
            logger.error(f"Failed to execute trade for {symbol}: {e}")
            print(f"{Fore.RED}Failed to execute trade for {symbol}: {e}{Style.RESET_ALL}")
            return None
    
    def run_trading_session(self) -> None:
        """Run a single trading session."""
        print(f"{Fore.BLUE}{'='*50}")
        print(f"Starting trading session at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}{Style.RESET_ALL}")
        
        if self.dry_run:
            print(f"{Fore.YELLOW}🔄 DRY RUN MODE - No real trades will be executed{Style.RESET_ALL}")
        
        try:
            # Check if market is open (unless ignoring market hours)
            if not self.ignore_market_hours and not self.broker.is_market_open():
                print(f"{Fore.YELLOW}Market is closed. Skipping trading session.{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Use --ignore-market-hours to run anyway{Style.RESET_ALL}")
                return
            elif self.ignore_market_hours and not self.broker.is_market_open():
                print(f"{Fore.YELLOW}Market is closed, but ignoring market hours as requested{Style.RESET_ALL}")
            
            # Sync portfolio with broker
            print(f"{Fore.CYAN}DEBUG: About to sync portfolio...{Style.RESET_ALL}")
            self.sync_portfolio()
            print(f"{Fore.CYAN}DEBUG: Portfolio sync completed{Style.RESET_ALL}")
            
            # Get AI decisions
            result = self.get_hedge_fund_decisions()
            decisions = result.get("decisions", {})
            analyst_signals = result.get("analyst_signals", {})
            
            # Display decisions
            print(f"\n{Fore.WHITE}{Style.BRIGHT}AI HEDGE FUND DECISIONS:{Style.RESET_ALL}")
            for ticker, decision in decisions.items():
                action = decision.get("action", "hold")
                quantity = decision.get("quantity", 0)
                reasoning = decision.get("reasoning", "No reasoning provided")
                
                color = {
                    "buy": Fore.GREEN,
                    "sell": Fore.RED,
                    "short": Fore.MAGENTA,
                    "cover": Fore.CYAN,
                    "hold": Fore.YELLOW
                }.get(action, Fore.WHITE)
                
                print(f"{color}{ticker}: {action.upper()} {quantity} shares{Style.RESET_ALL}")
                print(f"  Reasoning: {reasoning[:100]}...")
            
            # Execute trades
            executed_orders = []
            print(f"\n{Fore.WHITE}{Style.BRIGHT}EXECUTING TRADES:{Style.RESET_ALL}")
            
            for ticker, decision in decisions.items():
                order = self.execute_trade(ticker, decision)
                if order:
                    executed_orders.append(order)
            
            # Wait for orders to fill (basic implementation)
            if executed_orders and not self.dry_run:
                print(f"\n{Fore.CYAN}Monitoring order execution...{Style.RESET_ALL}")
                time.sleep(5)  # Wait a bit for market orders to fill
                
                for order in executed_orders:
                    updated_order = self.broker.get_order(order.id)
                    if updated_order:
                        status_color = Fore.GREEN if updated_order.status == "filled" else Fore.YELLOW
                        print(f"{status_color}Order {order.id}: {updated_order.status}{Style.RESET_ALL}")
            
            print(f"\n{Fore.GREEN}Trading session completed{Style.RESET_ALL}")
            sys.stdout.flush()
            
        except Exception as e:
            logger.error(f"Trading session failed: {e}")
            print(f"{Fore.RED}Trading session failed: {e}{Style.RESET_ALL}")
    
    def run_continuous_trading(self, interval_minutes: int = 60) -> None:
        """Run continuous trading with specified interval."""
        print(f"{Fore.BLUE}Starting continuous trading (interval: {interval_minutes} minutes){Style.RESET_ALL}")
        
        try:
            while True:
                self.run_trading_session()
                
                print(f"\n{Fore.CYAN}Waiting {interval_minutes} minutes until next session...{Style.RESET_ALL}")
                time.sleep(interval_minutes * 60)
                
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Trading stopped by user{Style.RESET_ALL}")
        except Exception as e:
            logger.error(f"Continuous trading failed: {e}")
            print(f"{Fore.RED}Continuous trading failed: {e}{Style.RESET_ALL}")
    
    def print_portfolio_summary(self) -> None:
        """Print current portfolio summary."""
        try:
            account = self.broker.get_account()
            positions = self.broker.get_positions()
            pending_orders = self.broker.get_orders(status="pending_new") if not self.dry_run else []
            open_orders = self.broker.get_orders() if not self.dry_run else []
            
            print(f"\n{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY:{Style.RESET_ALL}")
            print(f"Portfolio Value: ${account.portfolio_value:,.2f}")
            print(f"Cash: ${account.cash:,.2f}")
            print(f"Buying Power: ${account.buying_power:,.2f}")
            print(f"Day Trade Count: {account.day_trade_count}")
            
            if positions:
                print(f"\n{Fore.WHITE}{Style.BRIGHT}POSITIONS:{Style.RESET_ALL}")
                for pos in positions:
                    color = Fore.GREEN if pos.unrealized_pnl >= 0 else Fore.RED
                    print(f"{pos.symbol}: {pos.side} {pos.quantity:,.0f} shares @ ${pos.avg_entry_price:.2f}")
                    print(f"  Market Value: ${pos.market_value:,.2f}")
                    print(f"  {color}Unrealized P&L: ${pos.unrealized_pnl:,.2f}{Style.RESET_ALL}")
            else:
                print(f"\n{Fore.YELLOW}No open positions{Style.RESET_ALL}")
            
            # Show pending/open orders
            if open_orders:
                print(f"\n{Fore.WHITE}{Style.BRIGHT}ORDERS:{Style.RESET_ALL}")
                for order in open_orders:
                    status_color = {
                        "pending_new": Fore.YELLOW,
                        "new": Fore.CYAN,
                        "partially_filled": Fore.BLUE,
                        "filled": Fore.GREEN,
                        "done_for_day": Fore.MAGENTA,
                        "canceled": Fore.RED,
                        "expired": Fore.RED,
                        "replaced": Fore.YELLOW,
                        "pending_cancel": Fore.YELLOW,
                        "pending_replace": Fore.YELLOW,
                        "accepted": Fore.CYAN,
                        "accepted_for_bidding": Fore.CYAN,
                        "stopped": Fore.RED,
                        "rejected": Fore.RED,
                        "suspended": Fore.RED
                    }.get(order.status, Fore.WHITE)
                    
                    print(f"{order.symbol}: {status_color}{order.status.upper()}{Style.RESET_ALL} - {order.side} {order.quantity} @ {order.order_type}")
                    print(f"  Order ID: {order.id}")
                    if order.submitted_at:
                        print(f"  Submitted: {order.submitted_at.strftime('%Y-%m-%d %H:%M:%S')}")
                    if order.filled_quantity and order.filled_quantity > 0:
                        print(f"  Filled: {order.filled_quantity}/{order.quantity} @ ${order.filled_price:.2f}")
            else:
                print(f"\n{Fore.YELLOW}No pending orders{Style.RESET_ALL}")
                
        except Exception as e:
            logger.error(f"Failed to get portfolio summary: {e}")
            print(f"{Fore.RED}Failed to get portfolio summary: {e}{Style.RESET_ALL}")


def create_trader(
    tickers: list[str],
    selected_analysts: list[str] = None,
    model_name: str = "gpt-4o",
    model_provider: str = "OpenAI",
    available_capital: float = None,
    margin_requirement: float = None,
    dry_run: bool = False,
    ignore_market_hours: bool = False
) -> Trader:
    """Create a configured trader instance.
    
    Args:
        tickers: List of tickers to trade.
        selected_analysts: List of analysts to use.
        model_name: LLM model name.
        model_provider: LLM provider.
        available_capital: Override available capital (uses broker cash if None).
        margin_requirement: Margin requirement ratio for short positions.
        dry_run: If True, log trades but don't execute them.
        ignore_market_hours: If True, run even when market is closed.
        
    Returns:
        Trader: Configured trader instance.
    """
    broker = AlpacaBroker()  # Will read ALPACA_PAPER from environment
    
    return Trader(
        broker=broker,
        tickers=tickers,
        selected_analysts=selected_analysts,
        model_name=model_name,
        model_provider=model_provider,
        available_capital=available_capital,
        margin_requirement=margin_requirement,
        dry_run=dry_run,
        ignore_market_hours=ignore_market_hours
    )