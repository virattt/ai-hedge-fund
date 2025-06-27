"""Alpaca broker implementation for live trading."""

import os
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, StopOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.common.exceptions import APIError
from colorama import Fore, Style
import logging

from .broker_base import BrokerBase, Position, Order, Account


logger = logging.getLogger(__name__)


class AlpacaBroker(BrokerBase):
    """Alpaca broker implementation."""
    
    def __init__(self, paper_trading: bool = None):
        """Initialize Alpaca broker.
        
        Args:
            paper_trading: Whether to use paper trading account. If None, reads from ALPACA_PAPER env var.
        """
        # Read from environment variable if not explicitly set
        if paper_trading is None:
            paper_trading = os.getenv("ALPACA_PAPER", "true").lower() in ("true", "1", "yes")
        
        self.paper_trading = paper_trading
        self.trading_client = None
        self.data_client = None
        self._connected = False
        
        # Check required environment variables
        required_vars = ["ALPACA_API_KEY", "ALPACA_SECRET_KEY"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}. Please set these in your .env file")
        
        # Get API credentials from environment
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY")
    
    def connect(self) -> bool:
        """Connect to Alpaca API."""
        try:
            self.trading_client = TradingClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
                paper=self.paper_trading
            )
            
            self.data_client = StockHistoricalDataClient(
                api_key=self.api_key,
                secret_key=self.secret_key
            )
            
            # Test connection by getting account info
            account = self.trading_client.get_account()
            self._connected = True
            
            env_type = "Paper" if self.paper_trading else "Live"
            print(f"{Fore.GREEN}Connected to Alpaca {env_type} Trading API{Style.RESET_ALL}")
            print(f"Account Status: {account.status}")
            print(f"Buying Power: ${float(account.buying_power):,.2f}")
            
            return True
            
        except APIError as e:
            logger.error(f"Failed to connect to Alpaca: {e}")
            print(f"{Fore.RED}Failed to connect to Alpaca: {e}{Style.RESET_ALL}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to Alpaca: {e}")
            print(f"{Fore.RED}Unexpected error: {e}{Style.RESET_ALL}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from Alpaca API."""
        self.trading_client = None
        self.data_client = None
        self._connected = False
        print(f"{Fore.YELLOW}Disconnected from Alpaca API{Style.RESET_ALL}")
    
    def get_account(self) -> Account:
        """Get current account information."""
        if not self._connected:
            raise RuntimeError("Not connected to broker")
        
        account = self.trading_client.get_account()
        
        return Account(
            cash=float(account.cash),
            buying_power=float(account.buying_power),
            portfolio_value=float(account.portfolio_value),
            equity=float(account.equity),
            initial_margin=float(account.initial_margin),
            maintenance_margin=float(account.maintenance_margin),
            sma=float(account.sma),
            day_trade_count=int(account.daytrade_count),
            regt_buying_power=float(account.regt_buying_power),
            daytrading_buying_power=float(account.daytrading_buying_power),
            multiplier=float(account.multiplier)
        )
    
    def get_positions(self) -> list[Position]:
        """Get current positions."""
        if not self._connected:
            raise RuntimeError("Not connected to broker")
        
        positions = []
        alpaca_positions = self.trading_client.get_all_positions()
        
        for pos in alpaca_positions:
            side = "long" if float(pos.qty) > 0 else "short"
            
            # Handle optional unrealized_pnl - calculate if missing
            unrealized_pnl = 0.0
            if hasattr(pos, 'unrealized_pnl') and pos.unrealized_pnl is not None:
                unrealized_pnl = float(pos.unrealized_pnl)
            else:
                # Calculate unrealized P&L if not provided
                # unrealized_pnl = market_value - cost_basis
                unrealized_pnl = float(pos.market_value) - float(pos.cost_basis)
            
            positions.append(Position(
                symbol=pos.symbol,
                quantity=abs(float(pos.qty)),
                side=side,
                avg_entry_price=float(pos.avg_entry_price),
                market_value=float(pos.market_value),
                unrealized_pnl=unrealized_pnl,
                cost_basis=float(pos.cost_basis)
            ))
        
        return positions
    
    def get_position(self, symbol: str) -> Position | None:
        """Get position for a specific symbol."""
        if not self._connected:
            raise RuntimeError("Not connected to broker")
        
        try:
            pos = self.trading_client.get_open_position(symbol)
            side = "long" if float(pos.qty) > 0 else "short"
            
            # Handle optional unrealized_pnl - calculate if missing
            unrealized_pnl = 0.0
            if hasattr(pos, 'unrealized_pnl') and pos.unrealized_pnl is not None:
                unrealized_pnl = float(pos.unrealized_pnl)
            else:
                # Calculate unrealized P&L if not provided
                unrealized_pnl = float(pos.market_value) - float(pos.cost_basis)
            
            return Position(
                symbol=pos.symbol,
                quantity=abs(float(pos.qty)),
                side=side,
                avg_entry_price=float(pos.avg_entry_price),
                market_value=float(pos.market_value),
                unrealized_pnl=unrealized_pnl,
                cost_basis=float(pos.cost_basis)
            )
            
        except APIError:
            # Position doesn't exist
            return None
    
    def place_order(self, symbol: str, quantity: float, side: str, 
                   order_type: str = "market", limit_price: float | None = None,
                   stop_price: float | None = None) -> Order:
        """Place a trading order."""
        if not self._connected:
            raise RuntimeError("Not connected to broker")
        
        # Convert side to Alpaca format
        if side == "buy":
            order_side = OrderSide.BUY
        elif side == "sell":
            order_side = OrderSide.SELL
        elif side == "sell_short":
            order_side = OrderSide.SELL
            # Note: Alpaca handles short selling automatically when selling more than owned
        else:
            raise ValueError(f"Invalid order side: {side}")
        
        # Create order request based on type
        try:
            if order_type == "market":
                order_request = MarketOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    time_in_force=TimeInForce.DAY
                )
            elif order_type == "limit":
                if limit_price is None:
                    raise ValueError("Limit price required for limit orders")
                order_request = LimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    time_in_force=TimeInForce.DAY,
                    limit_price=limit_price
                )
            elif order_type == "stop":
                if stop_price is None:
                    raise ValueError("Stop price required for stop orders")
                order_request = StopOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    time_in_force=TimeInForce.DAY,
                    stop_price=stop_price
                )
            else:
                raise ValueError(f"Invalid order type: {order_type}")
            
            alpaca_order = self.trading_client.submit_order(order_request)
            
            return Order(
                id=str(alpaca_order.id),
                symbol=alpaca_order.symbol,
                quantity=float(alpaca_order.qty),
                side=side,
                order_type=order_type,
                status=alpaca_order.status.value,
                filled_price=float(alpaca_order.filled_avg_price) if alpaca_order.filled_avg_price else None,
                filled_quantity=float(alpaca_order.filled_qty) if alpaca_order.filled_qty else None,
                submitted_at=alpaca_order.submitted_at,
                filled_at=alpaca_order.filled_at
            )
            
        except APIError as e:
            logger.error(f"Failed to place order: {e}")
            raise RuntimeError(f"Failed to place order: {e}")
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if not self._connected:
            raise RuntimeError("Not connected to broker")
        
        try:
            self.trading_client.cancel_order_by_id(order_id)
            return True
        except APIError as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    def get_orders(self, status: str | None = None) -> list[Order]:
        """Get orders."""
        if not self._connected:
            raise RuntimeError("Not connected to broker")
        
        orders = []
        alpaca_orders = self.trading_client.get_orders()
        
        for order in alpaca_orders:
            if status is None or order.status.value == status:
                # Convert Alpaca side back to our format
                side = "buy" if order.side == OrderSide.BUY else "sell"
                
                orders.append(Order(
                    id=str(order.id),
                    symbol=order.symbol,
                    quantity=float(order.qty),
                    side=side,
                    order_type=order.order_type.value,
                    status=order.status.value,
                    filled_price=float(order.filled_avg_price) if order.filled_avg_price else None,
                    filled_quantity=float(order.filled_qty) if order.filled_qty else None,
                    submitted_at=order.submitted_at,
                    filled_at=order.filled_at
                ))
        
        return orders
    
    def get_order(self, order_id: str) -> Order | None:
        """Get specific order."""
        if not self._connected:
            raise RuntimeError("Not connected to broker")
        
        try:
            order = self.trading_client.get_order_by_id(order_id)
            side = "buy" if order.side == OrderSide.BUY else "sell"
            
            return Order(
                id=str(order.id),
                symbol=order.symbol,
                quantity=float(order.qty),
                side=side,
                order_type=order.order_type.value,
                status=order.status.value,
                filled_price=float(order.filled_avg_price) if order.filled_avg_price else None,
                filled_quantity=float(order.filled_qty) if order.filled_qty else None,
                submitted_at=order.submitted_at,
                filled_at=order.filled_at
            )
            
        except APIError:
            return None
    
    def get_current_price(self, symbol: str) -> float:
        """Get current price for a symbol."""
        if not self._connected:
            raise RuntimeError("Not connected to broker")
        
        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
            quote = self.data_client.get_stock_latest_quote(request)
            
            if symbol in quote:
                return float(quote[symbol].bid_price)
            else:
                raise ValueError(f"No quote available for {symbol}")
                
        except APIError as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            raise RuntimeError(f"Failed to get price for {symbol}: {e}")
    
    def is_market_open(self) -> bool:
        """Check if market is currently open."""
        if not self._connected:
            raise RuntimeError("Not connected to broker")
        
        try:
            clock = self.trading_client.get_clock()
            return clock.is_open
        except APIError as e:
            logger.error(f"Failed to get market status: {e}")
            return False
    
    def is_paper_trading(self) -> bool:
        """Check if this is a paper trading account."""
        return self.paper_trading
    
    def get_margin_requirement(self, symbol: str | None = None) -> float:
        """Get margin requirement ratio for positions.
        
        Args:
            symbol: Stock symbol to get specific margin requirement for. 
                   If None, returns account default margin requirement.
        
        Returns:
            float: Margin requirement ratio (e.g., 0.5 for 50% margin requirement).
        """
        if not self._connected:
            raise RuntimeError("Not connected to broker")
        
        try:
            # If a specific symbol is requested, get its asset-specific margin requirement
            if symbol:
                try:
                    asset = self.trading_client.get_asset(symbol)
                    if asset and hasattr(asset, 'maintenance_margin_requirement') and asset.maintenance_margin_requirement is not None:
                        # Alpaca returns margin requirement as percentage points (30.0 = 30%)
                        margin_req = asset.maintenance_margin_requirement
                        margin_float = float(margin_req)
                        
                        # Convert percentage points to ratio (30.0 -> 0.30)
                        if margin_float > 0:
                            return margin_float / 100.0
                        else:
                            # Invalid margin requirement, fall through to account default
                            print(f"WARNING: Invalid margin requirement {margin_float} for {symbol}, using account default")
                except APIError:
                    # Fall through to account-level default if asset not found
                    pass
                except Exception as e:
                    print(f"DEBUG: Error processing margin requirement for {symbol}: {e}")
                    # Fall through to account default
            
            # Fallback to account-level margin requirement
            account = self.trading_client.get_account()
            multiplier = float(account.multiplier) if account.multiplier else 1.0
            
            if multiplier > 1:
                # Margin account - typical requirement is 50% for most stocks
                return 0.5  # 50% margin requirement for margin accounts
            else:
                # Cash account - cannot use margin for overnight positions
                return 1.0  # 100% cash requirement for cash accounts (no margin)
                
        except APIError as e:
            logger.error(f"Failed to get margin requirement: {e}")
            return 0.5  # Default to 50% if we can't determine