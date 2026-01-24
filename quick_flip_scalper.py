"""
Quick Flip Scalper - Core Trading Bot
Implements the Quick Flip Scalper strategy for intraday trading.
"""

import pandas as pd
import pandas_ta as ta
import yfinance as yf
import requests
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
import pytz
import google.auth.transport.requests
import google.oauth2.id_token

import config

# Conditional import for Alpaca provider
if config.DATA_PROVIDER == "alpaca":
    from alpaca_data_provider import AlpacaDataProvider


class QuickFlipScalper:
    """
    Quick Flip Scalper trading bot.
    
    Strategy:
    1. At 09:45 EST, analyze the first 15-minute candle to establish box range
    2. Validate liquidity (candle range >= 25% of daily ATR)
    3. Scan 5-minute candles for reversal patterns outside the box
    4. Send trading signals via POST endpoint
    """
    
    def __init__(self, symbol: str = None):
        """
        Initialize the scalper with trading symbol.
        
        Args:
            symbol: Trading symbol (e.g., 'NVDA'). Uses config default if None.
        """
        self.symbol = symbol or config.SYMBOL
        self.tz = pytz.timezone(config.TIMEZONE)
        
        # Session state
        self.daily_atr: Optional[float] = None
        self.box_high: Optional[float] = None
        self.box_low: Optional[float] = None
        self.signal_sent: bool = False
        
        # Data cache
        self._daily_data: Optional[pd.DataFrame] = None
        self._intraday_data: Optional[pd.DataFrame] = None
        
        # Initialize data provider based on config
        if config.DATA_PROVIDER == "alpaca":
            self.data_provider = AlpacaDataProvider(paper=config.ALPACA_PAPER)
            print(f"Using Alpaca data provider (paper={config.ALPACA_PAPER})")
        else:
            self.data_provider = None
            print("Using yfinance data provider")
        
        # Trading via Cloud Function
        if config.ALPACA_TRADING_ENABLED:
            print(f"Alpaca trading enabled via Cloud Function (size=${config.ALPACA_POSITION_SIZE_USD})")
        else:
            print("Alpaca trading disabled")
    
    def fetch_daily_data(self, days: int = 30) -> pd.DataFrame:
        """
        Fetch daily OHLCV data for ATR calculation.
        
        Args:
            days: Number of days to fetch (default 30 for 14-period ATR)
            
        Returns:
            DataFrame with daily OHLCV data
        """
        if self.data_provider:
            # Use Alpaca data provider
            self._daily_data = self.data_provider.fetch_daily_data(self.symbol, days)
        else:
            # Fallback to yfinance
            ticker = yf.Ticker(self.symbol)
            end_date = datetime.now(self.tz)
            start_date = end_date - timedelta(days=days)
            
            self._daily_data = ticker.history(
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                interval='1d'
            )
        
        return self._daily_data
    
    def fetch_intraday_data(self, interval: str = '15m') -> pd.DataFrame:
        """
        Fetch intraday OHLCV data.
        
        Args:
            interval: Candle interval ('15m', '5m', '1m')
            
        Returns:
            DataFrame with intraday OHLCV data
        """
        if self.data_provider:
            # Use Alpaca data provider
            self._intraday_data = self.data_provider.fetch_intraday_data(self.symbol, interval)
        else:
            # Fallback to yfinance
            ticker = yf.Ticker(self.symbol)
            
            # yfinance requires period for intraday data
            self._intraday_data = ticker.history(
                period='1d',
                interval=interval
            )
        
        return self._intraday_data
    
    def calculate_atr(self) -> float:
        """
        Calculate 14-period ATR on daily data.
        
        Returns:
            Latest ATR value
        """
        if self._daily_data is None or len(self._daily_data) < config.ATR_PERIOD:
            self.fetch_daily_data()
        
        # Use pandas_ta for ATR calculation
        atr = ta.atr(
            high=self._daily_data['High'],
            low=self._daily_data['Low'],
            close=self._daily_data['Close'],
            length=config.ATR_PERIOD
        )
        
        self.daily_atr = atr.iloc[-1]
        return self.daily_atr
    
    def initialize_box(self) -> Tuple[float, float]:
        """
        Initialize the box range from the first 15-minute candle.
        
        Returns:
            Tuple of (box_high, box_low)
        """
        intraday_15m = self.fetch_intraday_data(interval='15m')
        
        if len(intraday_15m) == 0:
            raise ValueError("No 15-minute data available")
        
        # Get the first candle of the session (09:30-09:45)
        first_candle = intraday_15m.iloc[0]
        
        self.box_high = first_candle['High']
        self.box_low = first_candle['Low']
        
        return (self.box_high, self.box_low)
    
    def validate_liquidity(self) -> bool:
        """
        Validate that the candle range meets liquidity threshold.
        
        Returns:
            True if range >= 25% of daily ATR, False otherwise
        """
        if self.box_high is None or self.box_low is None:
            raise ValueError("Box not initialized. Call initialize_box() first.")
        
        if self.daily_atr is None:
            self.calculate_atr()
        
        candle_range = self.box_high - self.box_low
        threshold = self.daily_atr * config.LIQUIDITY_THRESHOLD
        
        return candle_range >= threshold
    
    def is_hammer(self, candle: pd.Series) -> bool:
        """
        Detect Hammer candlestick pattern (bullish reversal).
        
        Criteria:
        - Small body (close near open)
        - Lower wick at least 2x body size
        - Little to no upper wick
        
        Args:
            candle: OHLCV candle data
            
        Returns:
            True if pattern detected
        """
        open_price = candle['Open']
        high = candle['High']
        low = candle['Low']
        close = candle['Close']
        
        body = abs(close - open_price)
        lower_wick = min(open_price, close) - low
        upper_wick = high - max(open_price, close)
        
        # Prevent division by zero
        if body == 0:
            body = 0.001
        
        # Hammer conditions:
        # 1. Lower wick >= 2x body
        # 2. Upper wick <= 0.5x body (small upper shadow)
        is_hammer = (
            lower_wick >= config.HAMMER_WICK_RATIO * body and
            upper_wick <= 0.5 * body
        )
        
        return is_hammer
    
    def is_inverted_hammer(self, candle: pd.Series) -> bool:
        """
        Detect Inverted Hammer candlestick pattern (bearish reversal at top).
        
        Criteria:
        - Small body
        - Upper wick at least 2x body size
        - Little to no lower wick
        
        Args:
            candle: OHLCV candle data
            
        Returns:
            True if pattern detected
        """
        open_price = candle['Open']
        high = candle['High']
        low = candle['Low']
        close = candle['Close']
        
        body = abs(close - open_price)
        lower_wick = min(open_price, close) - low
        upper_wick = high - max(open_price, close)
        
        # Prevent division by zero
        if body == 0:
            body = 0.001
        
        # Inverted Hammer conditions:
        # 1. Upper wick >= 2x body
        # 2. Lower wick <= 0.5x body
        is_inverted = (
            upper_wick >= config.HAMMER_WICK_RATIO * body and
            lower_wick <= 0.5 * body
        )
        
        return is_inverted
    
    def is_bullish_engulfing(self, current: pd.Series, previous: pd.Series) -> bool:
        """
        Detect Bullish Engulfing pattern.
        
        Criteria:
        - Previous candle is red (bearish)
        - Current candle is green (bullish)
        - Current body fully engulfs previous body
        
        Args:
            current: Current candle data
            previous: Previous candle data
            
        Returns:
            True if pattern detected
        """
        # Previous candle must be red (bearish)
        prev_is_red = previous['Close'] < previous['Open']
        
        # Current candle must be green (bullish)
        curr_is_green = current['Close'] > current['Open']
        
        if not (prev_is_red and curr_is_green):
            return False
        
        # Current body must fully engulf previous body
        engulfs = (
            current['Close'] > previous['Open'] and
            current['Open'] < previous['Close']
        )
        
        return engulfs
    
    def is_bearish_engulfing(self, current: pd.Series, previous: pd.Series) -> bool:
        """
        Detect Bearish Engulfing pattern.
        
        Criteria:
        - Previous candle is green (bullish)
        - Current candle is red (bearish)
        - Current body fully engulfs previous body
        
        Args:
            current: Current candle data
            previous: Previous candle data
            
        Returns:
            True if pattern detected
        """
        # Previous candle must be green (bullish)
        prev_is_green = previous['Close'] > previous['Open']
        
        # Current candle must be red (bearish)
        curr_is_red = current['Close'] < current['Open']
        
        if not (prev_is_green and curr_is_red):
            return False
        
        # Current body must fully engulf previous body
        engulfs = (
            current['Open'] > previous['Close'] and
            current['Close'] < previous['Open']
        )
        
        return engulfs
    
    def calculate_trade_params(
        self,
        pattern: str,
        direction: str,
        current: pd.Series,
        previous: Optional[pd.Series] = None
    ) -> Dict[str, float]:
        """
        Calculate entry, stop loss, and target prices.
        
        Args:
            pattern: Pattern type ('hammer', 'inverted_hammer', 'bullish_engulfing', 'bearish_engulfing')
            direction: 'LONG' or 'SHORT'
            current: Current candle data
            previous: Previous candle data (required for engulfing patterns)
            
        Returns:
            Dict with entry_price, stop_loss, target_price
        """
        if direction == 'LONG':
            if pattern == 'bullish_engulfing' and previous is not None:
                # Entry at previous candle high
                entry = previous['High']
                # Stop at minimum of both candles
                stop = min(current['Low'], previous['Low'])
            else:
                # Hammer: entry at candle high
                entry = current['High']
                stop = current['Low']
            
            # Target is box high
            target = self.box_high
            
        else:  # SHORT
            if pattern == 'bearish_engulfing' and previous is not None:
                # Entry at previous candle low
                entry = previous['Low']
                # Stop at maximum of both candles
                stop = max(current['High'], previous['High'])
            else:
                # Inverted Hammer: entry at candle low
                entry = current['Low']
                stop = current['High']
            
            # Target is box low
            target = self.box_low
        
        return {
            'entry_price': round(entry, 2),
            'stop_loss': round(stop, 2),
            'target_price': round(target, 2)
        }
    
    def send_signal(self, payload: Dict[str, Any]) -> bool:
        """
        Send trading signal via POST request and execute trade via Alpaca.
        
        Args:
            payload: Signal data dict
            
        Returns:
            True if signal sent successfully
        """
        telegram_success = False
        trade_success = False
        
        # 1. Send to Telegram (existing functionality)
        headers = {'Content-Type': 'application/json'}
        
        try:
            response = requests.post(
                config.ENDPOINT_URL,
                data=json.dumps(payload),
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"Telegram signal sent successfully")
                telegram_success = True
            else:
                print(f"Telegram signal failed with status {response.status_code}")
                
        except Exception as e:
            print(f"Error sending Telegram signal: {e}")
        
        # 2. Execute Alpaca trade via Cloud Function (with authentication)
        if config.ALPACA_TRADING_ENABLED:
            try:
                order_payload = {
                    'symbol': payload['asset_code'],
                    'side': payload['signal_type'],
                    'notional': config.ALPACA_POSITION_SIZE_USD,
                    'entry_price': payload['entry_price'],
                    'stop_loss_price': payload['stop_loss_price'],
                    'take_profit_price': payload['target_price']
                }
                
                # Get OIDC identity token for authenticated request
                auth_req = google.auth.transport.requests.Request()
                id_token = google.oauth2.id_token.fetch_id_token(
                    auth_req, 
                    config.ALPACA_ORDER_EXECUTOR_URL
                )
                
                auth_headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {id_token}'
                }
                
                response = requests.post(
                    config.ALPACA_ORDER_EXECUTOR_URL,
                    data=json.dumps(order_payload),
                    headers=auth_headers,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    trade_success = result.get('success', False)
                    print(f"Alpaca order executed: {result}")
                else:
                    print(f"Alpaca order failed with status {response.status_code}: {response.text}")
                    
            except Exception as e:
                print(f"Error executing Alpaca trade: {e}")
        
        # Mark signal as sent if either succeeded
        if telegram_success or trade_success:
            self.signal_sent = True
            return True
        
        return False
    
    def scan_for_signals(self) -> Optional[Dict[str, Any]]:
        """
        Scan completed 5-minute candles for trading signals.
        
        IMPORTANT: Uses the last COMPLETED candle (iloc[-2]) instead of 
        the current incomplete candle (iloc[-1]) to avoid false signals
        from mid-candle data that may change before the candle closes.
        
        Returns:
            Signal payload if pattern found, None otherwise
        """
        if self.box_high is None or self.box_low is None:
            raise ValueError("Box not initialized")
        
        # Fetch latest 5-minute data
        data_5m = self.fetch_intraday_data(interval='5m')
        
        # Need at least 3 candles: current (incomplete), previous (completed), and one before
        if len(data_5m) < 3:
            return None
        
        # Use the LAST COMPLETED candle (iloc[-2]), not the current incomplete one (iloc[-1])
        # This prevents false signals from mid-candle data
        current = data_5m.iloc[-2]   # Last completed candle
        previous = data_5m.iloc[-3]  # One before that (for engulfing patterns)
        
        current_close = current['Close']
        current_low = current['Low']
        current_high = current['High']
        
        signal = None
        
        # Check for LONG signals (price below box)
        if current_low < self.box_low:
            if self.is_hammer(current):
                params = self.calculate_trade_params('hammer', 'LONG', current)
                signal = self._create_signal_payload('LONG', params, 'hammer')
                
            elif self.is_bullish_engulfing(current, previous):
                params = self.calculate_trade_params('bullish_engulfing', 'LONG', current, previous)
                signal = self._create_signal_payload('LONG', params, 'bullish_engulfing')
        
        # Check for SHORT signals (price above box)
        elif current_high > self.box_high:
            if self.is_inverted_hammer(current):
                params = self.calculate_trade_params('inverted_hammer', 'SHORT', current)
                signal = self._create_signal_payload('SHORT', params, 'inverted_hammer')
                
            elif self.is_bearish_engulfing(current, previous):
                params = self.calculate_trade_params('bearish_engulfing', 'SHORT', current, previous)
                signal = self._create_signal_payload('SHORT', params, 'bearish_engulfing')
        
        return signal
    
    def _create_signal_payload(
        self,
        signal_type: str,
        params: Dict[str, float],
        pattern: str
    ) -> Dict[str, Any]:
        """
        Create signal payload for POST request.
        
        Args:
            signal_type: 'LONG' or 'SHORT'
            params: Trade parameters (entry, stop, target)
            pattern: Pattern name that triggered the signal
            
        Returns:
            Signal payload dict
        """
        now = datetime.now(self.tz)
        
        return {
            'asset_code': self.symbol,
            'signal_type': signal_type,
            'entry_price': params['entry_price'],
            'target_price': params['target_price'],
            'stop_loss_price': params['stop_loss'],
            'pattern': pattern,
            'box_high': round(self.box_high, 2),
            'box_low': round(self.box_low, 2),
            'daily_atr': round(self.daily_atr, 2),
            'timestamp': now.strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def is_within_trading_hours(self) -> bool:
        """
        Check if current time is within trading window (09:45 - 11:00 EST).
        
        Returns:
            True if within trading hours
        """
        now = datetime.now(self.tz)
        
        session_start = now.replace(
            hour=config.INIT_HOUR,
            minute=config.INIT_MINUTE,
            second=0,
            microsecond=0
        )
        session_end = now.replace(
            hour=config.SESSION_END_HOUR,
            minute=config.SESSION_END_MINUTE,
            second=0,
            microsecond=0
        )
        
        return session_start <= now <= session_end
    
    def run(self) -> Optional[Dict[str, Any]]:
        """
        Run the complete scanning cycle.
        
        This is the main entry point that:
        1. Initializes the box from 15m candle
        2. Validates liquidity
        3. Scans for signals if valid
        
        Returns:
            Signal payload if generated, None otherwise
        """
        print(f"[{datetime.now(self.tz)}] Starting Quick Flip Scalper for {self.symbol}")
        
        # Step 1: Calculate daily ATR
        print("Calculating daily ATR...")
        atr = self.calculate_atr()
        print(f"Daily ATR: {atr:.2f}")
        
        # Step 2: Initialize box from first 15m candle
        print("Initializing box from first 15m candle...")
        box_high, box_low = self.initialize_box()
        print(f"Box Range: High={box_high:.2f}, Low={box_low:.2f}")
        
        # Step 3: Validate liquidity
        print("Validating liquidity...")
        candle_range = box_high - box_low
        threshold = atr * config.LIQUIDITY_THRESHOLD
        
        if not self.validate_liquidity():
            print(f"SKIP: Insufficient liquidity. Range={candle_range:.2f} < Threshold={threshold:.2f}")
            return None
        
        print(f"OK: Liquidity validated. Range={candle_range:.2f} >= Threshold={threshold:.2f}")
        
        # Step 4: Scan for signals
        print("Scanning for signals...")
        signal = self.scan_for_signals()
        
        if signal:
            print(f"SIGNAL FOUND: {signal['signal_type']} via {signal['pattern']}")
            self.send_signal(signal)
            return signal
        else:
            print("No signal detected in current scan")
            return None
