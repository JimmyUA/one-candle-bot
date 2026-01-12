"""
Telegram Publisher Cloud Function
Receives trading signals via POST and publishes them to a Telegram channel.
"""

import os
import json
import requests
import functions_framework
from flask import Request


# Environment variables
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')


def format_signal_message(signal: dict) -> str:
    """
    Format trading signal as a Telegram message.
    
    Args:
        signal: Trading signal dictionary
        
    Returns:
        Formatted message string with emoji and markdown
    """
    signal_type = signal.get('signal_type', 'UNKNOWN')
    asset_code = signal.get('asset_code', 'N/A')
    pattern = signal.get('pattern', 'N/A')
    entry_price = signal.get('entry_price', 0)
    target_price = signal.get('target_price', 0)
    stop_loss_price = signal.get('stop_loss_price', 0)
    box_high = signal.get('box_high', 0)
    box_low = signal.get('box_low', 0)
    daily_atr = signal.get('daily_atr', 0)
    timestamp = signal.get('timestamp', 'N/A')
    
    # Emoji based on signal type
    if signal_type == 'LONG':
        emoji = '🟢'
        direction = '📈 LONG'
    elif signal_type == 'SHORT':
        emoji = '🔴'
        direction = '📉 SHORT'
    else:
        emoji = '⚪'
        direction = signal_type
    
    message = f"""
{emoji} *Quick Flip Scalper Signal* {emoji}

*{direction}* {asset_code}

📊 *Pattern:* {pattern.replace('_', ' ').title()}

💰 *Trade Parameters:*
• Entry: ${entry_price:.2f}
• Target: ${target_price:.2f}
• Stop Loss: ${stop_loss_price:.2f}

📦 *Box Range:*
• High: ${box_high:.2f}
• Low: ${box_low:.2f}

📈 *Daily ATR:* ${daily_atr:.2f}

🕐 *Time:* {timestamp}
"""
    return message.strip()


def send_telegram_message(message: str) -> dict:
    """
    Send message to Telegram channel.
    
    Args:
        message: Formatted message to send
        
    Returns:
        Telegram API response
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': True
    }
    
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    
    return response.json()


@functions_framework.http
def telegram_publisher(request: Request):
    """
    Cloud Function entry point.
    
    Accepts POST requests with trading signal JSON and publishes to Telegram.
    
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
        signal = request.get_json(silent=True)
        if not signal:
            return {'error': 'Invalid JSON body'}, 400
    except Exception as e:
        return {'error': f'Failed to parse JSON: {str(e)}'}, 400
    
    # Validate required fields
    required_fields = ['asset_code', 'signal_type', 'entry_price', 'target_price', 'stop_loss_price']
    missing_fields = [f for f in required_fields if f not in signal]
    
    if missing_fields:
        return {'error': f'Missing required fields: {missing_fields}'}, 400
    
    # Format and send message
    try:
        message = format_signal_message(signal)
        result = send_telegram_message(message)
        
        return {
            'success': True,
            'message': 'Signal published to Telegram',
            'telegram_message_id': result.get('result', {}).get('message_id')
        }, 200
        
    except ValueError as e:
        return {'error': str(e)}, 500
    except requests.exceptions.RequestException as e:
        return {'error': f'Telegram API error: {str(e)}'}, 502
    except Exception as e:
        return {'error': f'Internal error: {str(e)}'}, 500
