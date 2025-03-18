import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
from colorama import Fore, Style
import json

class AlpacaClient:
    """Client for interacting with Alpaca Markets API."""
    
    def __init__(self):
        """Initialize the Alpaca API client."""
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.api_secret = os.getenv("ALPACA_API_SECRET")
        self.paper_trading = os.getenv("ALPACA_PAPER_TRADING", "true").lower() == "true"
        
        if not self.api_key or not self.api_secret:
            raise ValueError("Alpaca API credentials not found. Please set ALPACA_API_KEY and ALPACA_API_SECRET in your .env file.")
        
        # Set base URLs based on paper/live trading
        if self.paper_trading:
            self.base_url = "https://paper-api.alpaca.markets"
        else:
            self.base_url = "https://api.alpaca.markets"
            
        self.data_url = "https://data.alpaca.markets"
        
        # Set up auth headers
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
            "Content-Type": "application/json"
        }
        
        # Display account status
        self._print_account_status()
    
    def _make_request(self, method: str, endpoint: str, base: str = None, params: dict = None, data: dict = None):
        """Make a request to the Alpaca API."""
        url = f"{base or self.base_url}/v2/{endpoint}"
        
        try:
            if method.lower() == "get":
                response = requests.get(url, headers=self.headers, params=params)
            elif method.lower() == "post":
                response = requests.post(url, headers=self.headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_details = f"HTTP Error: {e}"
            try:
                error_details += f" - {response.json()}"
            except:
                pass
            print(f"{Fore.RED}{error_details}{Style.RESET_ALL}")
            raise
        except Exception as e:
            print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")
            raise
    
    def _print_account_status(self) -> None:
        """Print account connection status"""
        try:
            account = self.get_account_info()
            account_type = "PAPER" if self.paper_trading else "LIVE"
            
            print(f"\n{Fore.CYAN}Connected to Alpaca {account_type} account:{Style.RESET_ALL}")
            print(f"Account ID: {account['id']}")
            print(f"Account Status: {Fore.GREEN if account['status'] == 'ACTIVE' else Fore.RED}{account['status']}{Style.RESET_ALL}")
            print(f"Buying Power: {Fore.GREEN}${float(account['buying_power']):,.2f}{Style.RESET_ALL}")
            print(f"Cash: ${float(account['cash']):,.2f}")
            print(f"Portfolio Value: ${float(account['portfolio_value']):,.2f}")
            
            # Additional warnings for trading limitations if needed
            if account['pattern_day_trader']:
                print(f"{Fore.RED}WARNING: Account flagged as Pattern Day Trader{Style.RESET_ALL}")
            if not account['trading_blocked'] and not account['account_blocked']:
                print(f"{Fore.GREEN}Account Ready for Trading{Style.RESET_ALL}\n")
            else:
                print(f"{Fore.RED}ALERT: Trading is blocked on this account{Style.RESET_ALL}\n")
        except Exception as e:
            print(f"{Fore.RED}Error connecting to Alpaca: {str(e)}{Style.RESET_ALL}")
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        return self._make_request("GET", "account")
    
    def get_portfolio(self) -> Tuple[Dict[str, Any], List[str]]:
        """
        Get current portfolio positions formatted to match the hedge fund's portfolio structure.
        """
        # Get account information
        account = self.get_account_info()
        
        # Get all positions
        positions = self._make_request("GET", "positions")
        
        # Extract tickers from positions
        tickers = [position["symbol"] for position in positions]
        
        # Build the portfolio structure
        portfolio = {
            "cash": float(account["cash"]),
            "margin_used": float(account.get("initial_margin", 0)),
            "positions": {},
            "realized_gains": {}
        }
        
        # Fill positions
        for position in positions:
            ticker = position["symbol"]
            qty = float(position["qty"])
            avg_price = float(position["avg_entry_price"])
            
            # Determine if position is long or short
            is_long = qty > 0
            is_short = qty < 0
            
            portfolio["positions"][ticker] = {
                "long": abs(qty) if is_long else 0,
                "short": abs(qty) if is_short else 0,
                "long_cost_basis": avg_price if is_long else 0.0,
                "short_cost_basis": avg_price if is_short else 0.0,
                "short_margin_used": float(position.get("initial_margin", 0)) if is_short else 0.0
            }
            
            # Initialize realized gains structure for each position
            portfolio["realized_gains"][ticker] = {
                "long": 0.0,  # We don't have realized gains info from API directly
                "short": 0.0
            }
        
        return portfolio, tickers
    
    def get_historical_prices(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Get historical price data for a specific ticker.
        
        Args:
            ticker: The stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            DataFrame with historical price data
        """
        # Parse dates
        start = pd.Timestamp(start_date).isoformat()
        end = pd.Timestamp(end_date).isoformat()
        
        params = {
            "symbols": ticker,
            "timeframe": "1Day",
            "start": start,
            "end": end,
            "adjustment": "all"
        }
        
        try:
            # Get the data
            bars = self._make_request("GET", "stocks/bars", base=self.data_url, params=params)
            
            # Convert to DataFrame if we have data
            if "bars" in bars and ticker in bars["bars"] and bars["bars"][ticker]:
                df = pd.DataFrame(bars["bars"][ticker])
                df['t'] = pd.to_datetime(df['t'])
                df = df.rename(columns={
                    't': 'timestamp',
                    'o': 'open',
                    'h': 'high',
                    'l': 'low',
                    'c': 'close',
                    'v': 'volume'
                })
                return df
            else:
                print(f"No data found for {ticker} between {start_date} and {end_date}")
                return pd.DataFrame()
        except Exception as e:
            print(f"Error fetching historical data for {ticker}: {e}")
            return pd.DataFrame()
    
    def place_order(self, ticker: str, action: str, quantity: float) -> Dict[str, Any]:
        """
        Place an order with Alpaca.
        
        Args:
            ticker: Stock symbol
            action: 'buy', 'sell', 'short', or 'cover'
            quantity: Number of shares to trade
            
        Returns:
            Dictionary with order details
        """
        # Map actions to Alpaca order parameters
        if action == "buy":
            side = "buy"
        elif action == "sell":
            side = "sell"
        elif action == "short":
            side = "sell"  # Shorting is just selling in Alpaca
        elif action == "cover":
            side = "buy"   # Covering is just buying in Alpaca
        else:
            raise ValueError(f"Invalid action: {action}. Must be 'buy', 'sell', 'short', or 'cover'.")
        
        # Create the order data
        order_data = {
            "symbol": ticker,
            "qty": str(quantity),
            "side": side,
            "type": "market",
            "time_in_force": "day"
        }
        
        try:
            # Submit the order
            order = self._make_request("POST", "orders", data=order_data)
            
            # Return order details
            return {
                "id": order.get("id", ""),
                "client_order_id": order.get("client_order_id", ""),
                "status": order.get("status", ""),
                "symbol": order.get("symbol", ""),
                "quantity": float(order.get("qty", 0)),
                "side": order.get("side", ""),
                "type": order.get("type", ""),
                "submitted_at": order.get("submitted_at", ""),
                "filled_at": order.get("filled_at", ""),
                "filled_qty": float(order.get("filled_qty", 0)) if order.get("filled_qty") else 0,
                "filled_avg_price": float(order.get("filled_avg_price", 0)) if order.get("filled_avg_price") else 0
            }
        except Exception as e:
            print(f"Error placing order: {e}")
            return {"error": str(e)}
    
    def get_recent_orders(self, limit: int = 100, status: str = "all", days_back: int = 7) -> List[Dict[str, Any]]:
        """
        Get recent orders from the account.
        
        Args:
            limit: Maximum number of orders to return
            status: Filter by order status ('open', 'closed', 'all')
            days_back: How many days back to look for orders
            
        Returns:
            List of order details
        """
        # Calculate date range - using proper ISO 8601 format that Alpaca requires
        end_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        params = {
            "limit": limit,
            "status": status,
            "after": start_date,
            "until": end_date
        }
        
        try:
            # Get orders
            orders = self._make_request("GET", "orders", params=params)
            
            # Format order details
            formatted_orders = []
            for order in orders:
                filled_at = order.get("filled_at")
                days_ago = None
                
                if filled_at:
                    try:
                        # Handle different timestamp formats
                        if 'Z' in filled_at:
                            fill_date = datetime.strptime(filled_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                        else:
                            fill_date = datetime.fromisoformat(filled_at)
                        days_ago = (datetime.now() - fill_date).days
                    except ValueError:
                        print(f"Warning: Could not parse date: {filled_at}")
                
                formatted_orders.append({
                    "id": order.get("id", ""),
                    "client_order_id": order.get("client_order_id", ""),
                    "status": order.get("status", ""),
                    "symbol": order.get("symbol", ""),
                    "quantity": float(order.get("qty", 0)),
                    "side": order.get("side", ""),
                    "type": order.get("type", ""),
                    "submitted_at": order.get("submitted_at", ""),
                    "filled_at": filled_at,
                    "filled_qty": float(order.get("filled_qty", 0)) if order.get("filled_qty") else 0,
                    "filled_avg_price": float(order.get("filled_avg_price", 0)) if order.get("filled_avg_price") else 0,
                    "created_at": order.get("created_at", ""),
                    "days_ago": days_ago
                })
            
            return formatted_orders
            
        except Exception as e:
            print(f"Warning: Could not retrieve orders: {e}")
            # Return empty list if there was an error
            return []
    
    def get_trade_history(self, days_back: int = 30, symbols: Optional[List[str]] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get trade history organized by ticker with additional metrics.
        
        Args:
            days_back: How many days back to look for trades
            symbols: Optional list of symbols to filter by
            
        Returns:
            Dictionary with ticker as key and list of trades as value
        """
        try:
            orders = self.get_recent_orders(days_back=days_back)
            
            # Filter to only include filled orders
            filled_orders = [order for order in orders if order["status"] == "filled"]
            
            # Filter by symbols if provided
            if symbols:
                filled_orders = [order for order in filled_orders if order["symbol"] in symbols]
            
            # Organize by ticker
            trades_by_ticker = {}
            
            for order in filled_orders:
                ticker = order["symbol"]
                if ticker not in trades_by_ticker:
                    trades_by_ticker[ticker] = []
                
                # Calculate trade value
                trade_value = order["filled_qty"] * order["filled_avg_price"] if order["filled_qty"] and order["filled_avg_price"] else 0
                
                # Add enhanced trade info
                trade_info = {
                    "id": order["id"],
                    "side": order["side"],
                    "quantity": order["filled_qty"],
                    "price": order["filled_avg_price"],
                    "value": trade_value,
                    "date": order["filled_at"],
                    "days_ago": order["days_ago"]
                }
                
                trades_by_ticker[ticker].append(trade_info)
            
            # Sort each ticker's trades by date (newest first)
            for ticker in trades_by_ticker:
                trades_by_ticker[ticker].sort(key=lambda x: x["days_ago"] if x["days_ago"] is not None else float('inf'))
                
                # Add ticker-level metrics
                if trades_by_ticker[ticker]:
                    # Calculate days since last trade
                    latest_trade = trades_by_ticker[ticker][0]
                    days_since_last_trade = latest_trade["days_ago"]
                    
                    # Count trades per side
                    buy_count = sum(1 for t in trades_by_ticker[ticker] if t["side"] == "buy")
                    sell_count = sum(1 for t in trades_by_ticker[ticker] if t["side"] == "sell")
                    
                    # Add metrics to each trade entry
                    for trade in trades_by_ticker[ticker]:
                        trade["ticker_metrics"] = {
                            "days_since_last_trade": days_since_last_trade,
                            "total_trades": len(trades_by_ticker[ticker]),
                            "buy_count": buy_count,
                            "sell_count": sell_count,
                            "buy_to_sell_ratio": buy_count / sell_count if sell_count > 0 else float('inf')
                        }
            
            return trades_by_ticker
            
        except Exception as e:
            print(f"Warning: Could not retrieve trade history: {e}")
            return {}
    
    def get_trading_frequency_analysis(self, days_back: int = 30) -> Dict[str, Any]:
        """
        Analyze trading frequency and patterns.
        
        Args:
            days_back: How many days back to analyze
            
        Returns:
            Dictionary with trading frequency metrics
        """
        try:
            orders = self.get_recent_orders(days_back=days_back)
            filled_orders = [order for order in orders if order["status"] == "filled"]
            
            if not filled_orders:
                return {
                    "total_trades": 0,
                    "avg_trades_per_day": 0,
                    "avg_trade_value": 0,
                    "most_active_day": None,
                    "trades_by_day": {},
                    "trades_by_symbol": {},
                    "today_trade_count": 0
                }
            
            # Initialize metrics
            trades_by_day = {}
            trades_by_symbol = {}
            daily_values = {}
            total_value = 0
            
            # Get today's date for counting today's trades
            today = datetime.now().strftime("%Y-%m-%d")
            
            # Process each order
            for order in filled_orders:
                # Extract date (without time)
                if order["filled_at"]:
                    try:
                        # Handle different timestamp formats
                        if 'Z' in order["filled_at"]:
                            fill_date = datetime.strptime(order["filled_at"], "%Y-%m-%dT%H:%M:%S.%fZ")
                        else:
                            fill_date = datetime.fromisoformat(order["filled_at"])
                        trade_date = fill_date.strftime("%Y-%m-%d")
                    except ValueError:
                        continue  # Skip if date can't be parsed
                else:
                    continue  # Skip if no filled date
                
                # Calculate trade value
                trade_value = order["filled_qty"] * order["filled_avg_price"] if order["filled_qty"] and order["filled_avg_price"] else 0
                total_value += trade_value
                
                # Count trades by day
                if trade_date not in trades_by_day:
                    trades_by_day[trade_date] = 0
                    daily_values[trade_date] = 0
                trades_by_day[trade_date] += 1
                daily_values[trade_date] += trade_value
                
                # Count trades by symbol
                symbol = order["symbol"]
                if symbol not in trades_by_symbol:
                    trades_by_symbol[symbol] = 0
                trades_by_symbol[symbol] += 1
            
            # Calculate metrics
            total_days = min(days_back, len(trades_by_day))
            total_trades = len(filled_orders)
            avg_trades_per_day = total_trades / total_days if total_days > 0 else 0
            avg_trade_value = total_value / total_trades if total_trades > 0 else 0
            
            # Find most active day
            most_active_day = max(trades_by_day.items(), key=lambda x: x[1]) if trades_by_day else (None, 0)
            
            # Find most traded symbol
            most_traded_symbol = max(trades_by_symbol.items(), key=lambda x: x[1]) if trades_by_symbol else (None, 0)
            
            # Calculate excessive trading flags
            high_frequency_days = {day: count for day, count in trades_by_day.items() if count > 5}  # Flag days with more than 5 trades
            
            return {
                "total_trades": total_trades,
                "avg_trades_per_day": avg_trades_per_day,
                "avg_trade_value": avg_trade_value,
                "total_value": total_value,
                "most_active_day": most_active_day,
                "most_traded_symbol": most_traded_symbol,
                "trades_by_day": trades_by_day,
                "daily_values": daily_values,
                "trades_by_symbol": trades_by_symbol,
                "high_frequency_days": high_frequency_days,
                "today_trade_count": trades_by_day.get(today, 0)
            }
            
        except Exception as e:
            print(f"Warning: Could not analyze trading frequency: {e}")
            return {
                "total_trades": 0,
                "avg_trades_per_day": 0,
                "today_trade_count": 0,
                "error": str(e)
            } 