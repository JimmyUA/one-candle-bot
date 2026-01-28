"""
Gap Fill Bot for TSLA
Executes the Gap Fill strategy: fades opening gaps > 1% back to previous close.
Intended to run once daily at market open (~09:31-09:35 EST).
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import pytz
from datetime import datetime, timedelta, time
import google.auth.transport.requests
import google.oauth2.id_token

import config

class GapFillBot:
    def __init__(self, symbol: str = "TSLA"):
        self.symbol = symbol
        self.tz = pytz.timezone(config.TIMEZONE)
        self.prev_close = None
        self.open_price = None
        self.gap_percent = 0.0
        
    def fetch_market_data(self):
        """
        Fetch previous close and current open.
        """
        print(f"Fetching data for {self.symbol}...")
        ticker = yf.Ticker(self.symbol)
        
        # 1. Get Previous Close
        # Fetch 5 days to be safe and get the last completed session
        daily_hist = ticker.history(period="5d", interval="1d")
        
        # We need the last COMPLETED trading day. 
        # If running today at 09:30, the last row might be today's incomplete candle.
        # Check dates.
        today_date = datetime.now(self.tz).date()
        
        # Filter out today if present in daily (yfinance sometimes includes today)
        history_dates = pd.to_datetime(daily_hist.index).date
        prev_days = daily_hist[history_dates < today_date]
        
        if len(prev_days) == 0:
            raise ValueError("Could not find previous trading day data")
            
        self.prev_close = prev_days.iloc[-1]['Close']
        prev_date = prev_days.index[-1].date()
        print(f"Previous Close ({prev_date}): ${self.prev_close:.2f}")
        
        # 2. Get Today's Open
        # Fetch 1m data for today
        today_data = ticker.history(period="1d", interval="1m")
        
        if len(today_data) == 0:
            raise ValueError("No data for today yet (Market might be closed or API delay)")
            
        # First candle of the day
        first_candle = today_data.iloc[0]
        self.open_price = first_candle['Open']
        print(f"Current Open ({today_data.index[0].time()}): ${self.open_price:.2f}")

    def check_gap(self):
        """
        Calculate gap and check if it meets threshold.
        """
        if not self.prev_close or not self.open_price:
            return None
            
        self.gap_percent = (self.open_price - self.prev_close) / self.prev_close
        gap_abs_percent = abs(self.gap_percent) * 100
        
        print(f"Gap: {self.gap_percent*100:.2f}%")
        
        if abs(self.gap_percent) >= config.GAP_THRESHOLD:
            print(f"GAP VALID: {gap_abs_percent:.2f}% >= {config.GAP_THRESHOLD*100}%")
            return True
        else:
            print(f"GAP NO-GO: {gap_abs_percent:.2f}% < {config.GAP_THRESHOLD*100}%")
            return False

    def generate_signal(self):
        """
        Generate trading signal payload.
        """
        if self.gap_percent > 0:
            # GAP UP -> SHORT (Fade)
            direction = 'SHORT'
            entry = self.open_price
            target = self.prev_close
            gap_size = abs(entry - target)
            stop = entry + (gap_size * config.GAP_STOP_LOSS_RATIO)
        else:
            # GAP DOWN -> LONG (Fade)
            direction = 'LONG'
            entry = self.open_price
            target = self.prev_close
            gap_size = abs(target - entry)
            stop = entry - (gap_size * config.GAP_STOP_LOSS_RATIO)
            
        return {
            'asset_code': self.symbol,
            'signal_type': direction,
            'entry_price': round(entry, 2),
            'target_price': round(target, 2),
            'stop_loss_price': round(stop, 2),
            'pattern': 'gap_fill',
            'gap_percent': round(self.gap_percent * 100, 2),
            'prev_close': round(self.prev_close, 2),
            'open_price': round(self.open_price, 2),
            'timestamp': datetime.now(self.tz).strftime('%Y-%m-%d %H:%M:%S')
        }

    def send_signal(self, payload):
        """
        Send signal to Cloud Functions.
        """
        headers = {'Content-Type': 'application/json'}
        
        print(f"Sending Signal: {payload['signal_type']} {payload['asset_code']} @ {payload['entry_price']}")
        
        # 1. Telegram
        try:
            resp = requests.post(config.ENDPOINT_URL, json=payload, headers=headers)
            print(f"Telegram response: {resp.status_code}")
        except Exception as e:
            print(f"Telegram error: {e}")
            
        # 2. Alpaca Executor
        if config.ALPACA_TRADING_ENABLED:
            try:
                # Auth
                auth_req = google.auth.transport.requests.Request()
                id_token = google.oauth2.id_token.fetch_id_token(
                    auth_req, config.ALPACA_ORDER_EXECUTOR_URL
                )
                headers['Authorization'] = f"Bearer {id_token}"
                
                # Order Payload
                # Calculate quantity based on Position Size / Entry Price
                # But here we just send params, the cloud function handles size or we send 'notional'
                
                order_payload = {
                    'symbol': payload['asset_code'],
                    'side': payload['signal_type'],
                    'notional': config.ALPACA_POSITION_SIZE_USD, # Default size
                    'entry_price': payload['entry_price'],
                    'stop_loss_price': payload['stop_loss_price'],
                    'take_profit_price': payload['target_price']
                }
                
                resp = requests.post(config.ALPACA_ORDER_EXECUTOR_URL, json=order_payload, headers=headers)
                print(f"Alpaca response: {resp.status_code} - {resp.text}")
                
            except Exception as e:
                print(f"Alpaca error: {e}")

    def run(self):
        print(f"--- Starting Gap Fill Bot ({self.symbol}) ---")
        try:
            self.fetch_market_data()
            if self.check_gap():
                signal = self.generate_signal()
                self.send_signal(signal)
            else:
                print("No trade generated.")
        except Exception as e:
            print(f"Error: {e}")
        print("--- Finished ---")

if __name__ == "__main__":
    bot = GapFillBot()
    bot.run()
