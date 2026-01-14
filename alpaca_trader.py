"""
Alpaca Trader - Automated Order Execution

Provides automated trading capabilities using Alpaca's Trading API.
Executes bracket orders with entry, stop loss, and take profit levels.
"""

import os
from typing import Optional, Dict, Any
from decimal import Decimal, ROUND_DOWN

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    LimitOrderRequest,
    TakeProfitRequest,
    StopLossRequest
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass


class AlpacaTrader:
    """
    Alpaca trading client for automated order execution.
    
    Executes bracket orders (market entry + stop loss + take profit)
    using dollar-based position sizing (notional orders).
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        paper: bool = True
    ):
        """
        Initialize Alpaca trading client.
        
        Args:
            api_key: Alpaca API key. If None, reads from ALPACA_API_KEY env var.
            secret_key: Alpaca secret key. If None, reads from ALPACA_SECRET_KEY env var.
            paper: Use paper trading endpoint (default True for safety).
        """
        self.api_key = api_key or os.environ.get("ALPACA_API_KEY")
        self.secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY")
        self.paper = paper
        
        if not self.api_key or not self.secret_key:
            raise ValueError(
                "Alpaca API keys required. Set ALPACA_API_KEY and "
                "ALPACA_SECRET_KEY environment variables or pass them directly."
            )
        
        # Initialize trading client
        self.client = TradingClient(
            api_key=self.api_key,
            secret_key=self.secret_key,
            paper=paper
        )
        
        print(f"AlpacaTrader initialized (paper={paper})")
    
    def get_account(self) -> Dict[str, Any]:
        """
        Get account information.
        
        Returns:
            Account details including buying power, equity, etc.
        """
        account = self.client.get_account()
        return {
            'buying_power': float(account.buying_power),
            'cash': float(account.cash),
            'equity': float(account.equity),
            'pattern_day_trader': account.pattern_day_trader,
            'trading_blocked': account.trading_blocked
        }
    
    def execute_bracket_order(
        self,
        symbol: str,
        side: str,
        notional: float,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float
    ) -> Dict[str, Any]:
        """
        Execute a bracket order with limit entry, stop loss, and take profit.
        
        A bracket order creates three linked orders:
        1. Limit order to enter the position at entry_price
        2. Stop loss order (activates when entry fills)
        3. Take profit limit order (activates when entry fills)
        
        Only one of the exit orders will execute; the other is automatically cancelled.
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            side: Trade direction - 'LONG' (buy) or 'SHORT' (sell)
            notional: Dollar amount to trade (e.g., 100.0 for $100)
            entry_price: Limit price for entry order
            stop_loss_price: Stop loss price level
            take_profit_price: Take profit price level
            
        Returns:
            Order details including order_id, status, and filled quantity
        """
        # Determine order side
        order_side = OrderSide.BUY if side == 'LONG' else OrderSide.SELL
        
        # Round prices to 2 decimal places
        entry_price = round(entry_price, 2)
        stop_loss_price = round(stop_loss_price, 2)
        take_profit_price = round(take_profit_price, 2)
        
        try:
            # Create bracket order request with limit entry
            order_request = LimitOrderRequest(
                symbol=symbol,
                notional=notional,
                limit_price=entry_price,
                side=order_side,
                time_in_force=TimeInForce.DAY,
                order_class=OrderClass.BRACKET,
                stop_loss=StopLossRequest(stop_price=stop_loss_price),
                take_profit=TakeProfitRequest(limit_price=take_profit_price)
            )
            
            # Submit order
            order = self.client.submit_order(order_data=order_request)
            
            result = {
                'success': True,
                'order_id': str(order.id),
                'symbol': order.symbol,
                'side': order.side.value,
                'notional': notional,
                'entry_price': entry_price,
                'status': order.status.value,
                'stop_loss_price': stop_loss_price,
                'take_profit_price': take_profit_price,
                'created_at': str(order.created_at)
            }
            
            print(f"✓ Bracket order submitted: {symbol} {side} ${notional}")
            print(f"  Order ID: {order.id}")
            print(f"  Entry (Limit): ${entry_price}")
            print(f"  Stop Loss: ${stop_loss_price}")
            print(f"  Take Profit: ${take_profit_price}")
            
            return result
            
        except Exception as e:
            error_result = {
                'success': False,
                'error': str(e),
                'symbol': symbol,
                'side': side,
                'notional': notional
            }
            
            print(f"✗ Order failed: {symbol} {side} ${notional}")
            print(f"  Error: {e}")
            
            return error_result
    
    def execute_market_order(
        self,
        symbol: str,
        side: str,
        notional: float
    ) -> Dict[str, Any]:
        """
        Execute a simple market order without bracket legs.
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            side: Trade direction - 'LONG' (buy) or 'SHORT' (sell)
            notional: Dollar amount to trade
            
        Returns:
            Order details
        """
        order_side = OrderSide.BUY if side == 'LONG' else OrderSide.SELL
        
        try:
            order_request = MarketOrderRequest(
                symbol=symbol,
                notional=notional,
                side=order_side,
                time_in_force=TimeInForce.DAY
            )
            
            order = self.client.submit_order(order_data=order_request)
            
            return {
                'success': True,
                'order_id': str(order.id),
                'symbol': order.symbol,
                'side': order.side.value,
                'notional': notional,
                'status': order.status.value
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'symbol': symbol,
                'side': side,
                'notional': notional
            }
    
    def get_positions(self) -> list:
        """
        Get all open positions.
        
        Returns:
            List of position details
        """
        positions = self.client.get_all_positions()
        return [
            {
                'symbol': pos.symbol,
                'qty': float(pos.qty),
                'side': pos.side.value,
                'avg_entry_price': float(pos.avg_entry_price),
                'market_value': float(pos.market_value),
                'unrealized_pl': float(pos.unrealized_pl),
                'unrealized_plpc': float(pos.unrealized_plpc)
            }
            for pos in positions
        ]
    
    def cancel_all_orders(self) -> list:
        """
        Cancel all open orders.
        
        Returns:
            List of cancellation results
        """
        cancel_responses = self.client.cancel_orders()
        return [
            {
                'order_id': str(resp.id),
                'status': resp.status
            }
            for resp in cancel_responses
        ]
    
    def close_all_positions(self) -> list:
        """
        Close all open positions.
        
        Returns:
            List of close order results
        """
        close_responses = self.client.close_all_positions(cancel_orders=True)
        return [
            {
                'symbol': resp.symbol,
                'status': 'closed'
            }
            for resp in close_responses
        ]
