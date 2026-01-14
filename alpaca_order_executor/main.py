"""
Alpaca Order Executor Cloud Function
Receives trading signals via POST and executes bracket orders via Alpaca API.
"""

import os
import functions_framework
from flask import Request

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    LimitOrderRequest,
    TakeProfitRequest,
    StopLossRequest
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass


# Environment variables (from Secret Manager)
ALPACA_API_KEY = os.environ.get('ALPACA_API_KEY')
ALPACA_SECRET_KEY = os.environ.get('ALPACA_SECRET_KEY')
ALPACA_PAPER = os.environ.get('ALPACA_PAPER', 'true').lower() == 'true'


def execute_bracket_order(
    symbol: str,
    side: str,
    notional: float,
    entry_price: float,
    stop_loss_price: float,
    take_profit_price: float
) -> dict:
    """
    Execute a bracket order with limit entry, stop loss, and take profit.
    
    Args:
        symbol: Stock symbol (e.g., 'AAPL')
        side: Trade direction - 'LONG' (buy) or 'SHORT' (sell)
        notional: Dollar amount to trade (e.g., 100.0 for $100)
        entry_price: Limit price for entry order
        stop_loss_price: Stop loss price level
        take_profit_price: Take profit price level
        
    Returns:
        Order result dictionary
    """
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set")
    
    # Initialize trading client
    client = TradingClient(
        api_key=ALPACA_API_KEY,
        secret_key=ALPACA_SECRET_KEY,
        paper=ALPACA_PAPER
    )
    
    # Determine order side
    order_side = OrderSide.BUY if side == 'LONG' else OrderSide.SELL
    
    # Round prices to 2 decimal places
    entry_price = round(entry_price, 2)
    stop_loss_price = round(stop_loss_price, 2)
    take_profit_price = round(take_profit_price, 2)
    
    # Calculate quantity from notional (bracket orders don't support notional/fractional)
    # Use whole shares only
    qty = int(notional / entry_price)
    if qty < 1:
        qty = 1  # Minimum 1 share
    
    # Create bracket order request with limit entry and quantity
    order_request = LimitOrderRequest(
        symbol=symbol,
        qty=qty,
        limit_price=entry_price,
        side=order_side,
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.BRACKET,
        stop_loss=StopLossRequest(stop_price=stop_loss_price),
        take_profit=TakeProfitRequest(limit_price=take_profit_price)
    )
    
    # Submit order
    order = client.submit_order(order_data=order_request)
    
    return {
        'success': True,
        'order_id': str(order.id),
        'symbol': order.symbol,
        'side': order.side.value,
        'qty': qty,
        'notional_requested': notional,
        'entry_price': entry_price,
        'status': order.status.value,
        'stop_loss_price': stop_loss_price,
        'take_profit_price': take_profit_price,
        'created_at': str(order.created_at)
    }


@functions_framework.http
def alpaca_order_executor(request: Request):
    """
    Cloud Function entry point.
    
    Accepts POST requests with order details and executes bracket orders via Alpaca.
    
    Expected JSON body:
    {
        "symbol": "AAPL",
        "side": "LONG" or "SHORT",
        "notional": 100.0,
        "entry_price": 150.00,
        "stop_loss_price": 148.00,
        "take_profit_price": 155.00
    }
    
    Args:
        request: Flask Request object
        
    Returns:
        Tuple of (response_body, status_code)
    """
    # Only accept POST requests
    if request.method != 'POST':
        return {'error': 'Method not allowed'}, 405
    
    # Parse JSON body
    try:
        order_data = request.get_json(silent=True)
        if not order_data:
            return {'error': 'Invalid JSON body'}, 400
    except Exception as e:
        return {'error': f'Failed to parse JSON: {str(e)}'}, 400
    
    # Validate required fields
    required_fields = ['symbol', 'side', 'notional', 'entry_price', 'stop_loss_price', 'take_profit_price']
    missing_fields = [f for f in required_fields if f not in order_data]
    
    if missing_fields:
        return {'error': f'Missing required fields: {missing_fields}'}, 400
    
    # Validate side
    if order_data['side'] not in ['LONG', 'SHORT']:
        return {'error': 'side must be "LONG" or "SHORT"'}, 400
    
    # Execute order
    try:
        result = execute_bracket_order(
            symbol=order_data['symbol'],
            side=order_data['side'],
            notional=float(order_data['notional']),
            entry_price=float(order_data['entry_price']),
            stop_loss_price=float(order_data['stop_loss_price']),
            take_profit_price=float(order_data['take_profit_price'])
        )
        
        return result, 200
        
    except ValueError as e:
        return {'error': str(e)}, 500
    except Exception as e:
        return {'error': f'Order execution failed: {str(e)}'}, 502
