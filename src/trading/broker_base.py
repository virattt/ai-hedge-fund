"""Base broker interface for trading implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Position:
    """Represents a trading position."""
    symbol: str
    quantity: float
    side: str  # "long" or "short"
    avg_entry_price: float
    market_value: float
    unrealized_pnl: float
    cost_basis: float


@dataclass
class Order:
    """Represents a trading order."""
    id: str
    symbol: str
    quantity: float
    side: str  # "buy", "sell", "sell_short"
    order_type: str  # "market", "limit", "stop"
    status: str  # "pending", "filled", "canceled", "rejected"
    filled_price: float | None = None
    filled_quantity: float | None = None
    submitted_at: datetime | None = None
    filled_at: datetime | None = None


@dataclass
class Account:
    """Represents account information."""
    cash: float
    buying_power: float
    portfolio_value: float
    equity: float
    initial_margin: float
    maintenance_margin: float
    sma: float  # Special Memorandum Account
    day_trade_count: int
    regt_buying_power: float
    daytrading_buying_power: float
    multiplier: float


class BrokerBase(ABC):
    """Abstract base class for broker implementations."""
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to the broker API.
        
        Returns:
            bool: True if connection successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the broker API."""
        pass
    
    @abstractmethod
    def get_account(self) -> Account:
        """Get current account information.
        
        Returns:
            Account: Current account details.
        """
        pass
    
    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Get current positions.
        
        Returns:
            list[Position]: List of current positions.
        """
        pass
    
    @abstractmethod
    def get_position(self, symbol: str) -> Position | None:
        """Get position for a specific symbol.
        
        Args:
            symbol: Stock symbol.
            
        Returns:
            Position | None: Position if exists, None otherwise.
        """
        pass
    
    @abstractmethod
    def place_order(self, symbol: str, quantity: float, side: str, 
                   order_type: str = "market", limit_price: float | None = None,
                   stop_price: float | None = None) -> Order:
        """Place a trading order.
        
        Args:
            symbol: Stock symbol.
            quantity: Number of shares.
            side: "buy", "sell", or "sell_short".
            order_type: "market", "limit", or "stop".
            limit_price: Limit price for limit orders.
            stop_price: Stop price for stop orders.
            
        Returns:
            Order: The placed order.
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order.
        
        Args:
            order_id: Order ID to cancel.
            
        Returns:
            bool: True if cancellation successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def get_orders(self, status: str | None = None) -> list[Order]:
        """Get orders.
        
        Args:
            status: Filter by order status. None for all orders.
            
        Returns:
            list[Order]: List of orders.
        """
        pass
    
    @abstractmethod
    def get_order(self, order_id: str) -> Order | None:
        """Get specific order.
        
        Args:
            order_id: Order ID.
            
        Returns:
            Order | None: Order if exists, None otherwise.
        """
        pass
    
    @abstractmethod
    def get_current_price(self, symbol: str) -> float:
        """Get current price for a symbol.
        
        Args:
            symbol: Stock symbol.
            
        Returns:
            float: Current price.
        """
        pass
    
    @abstractmethod
    def is_market_open(self) -> bool:
        """Check if market is currently open.
        
        Returns:
            bool: True if market is open, False otherwise.
        """
        pass
    
    @abstractmethod
    def is_paper_trading(self) -> bool:
        """Check if this is a paper trading account.
        
        Returns:
            bool: True if paper trading, False if live trading.
        """
        pass
    
    @abstractmethod
    def get_margin_requirement(self, symbol: str | None = None) -> float:
        """Get margin requirement ratio for positions.
        
        Args:
            symbol: Stock symbol to get specific margin requirement for. 
                   If None, returns account default margin requirement.
        
        Returns:
            float: Margin requirement ratio (e.g., 0.5 for 50% margin requirement).
        """
        pass