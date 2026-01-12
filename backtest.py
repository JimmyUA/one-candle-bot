"""
Quick Flip Scalper - Backtesting Script
Simulates the QuickFlipScalper strategy over historical data.
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, time
from typing import Optional, Dict, List, Tuple
import pytz
import csv

import config


class BacktestEngine:
    """
    Backtesting engine for QuickFlipScalper strategy.
    
    Simulates the strategy over 59 days of historical data,
    avoiding look-ahead bias by using only past data for calculations.
    """
    
    def __init__(self, symbol: str = None, days: int = 59):
        """
        Initialize the backtesting engine.
        
        Args:
            symbol: Trading symbol (e.g., 'NVDA')
            days: Number of days to backtest (default 59 - yfinance limit for 5m data)
        """
        self.symbol = symbol or config.SYMBOL
        self.days = days
        self.tz = pytz.timezone(config.TIMEZONE)
        
        # Results storage
        self.trades: List[Dict] = []
        self.daily_results: List[Dict] = []
        
        # Data cache
        self._daily_data: Optional[pd.DataFrame] = None
        self._data_15m: Optional[pd.DataFrame] = None
        self._data_5m: Optional[pd.DataFrame] = None
    
    def fetch_all_data(self) -> None:
        """
        Fetch all required historical data from yfinance.
        """
        print(f"Fetching historical data for {self.symbol}...")
        
        ticker = yf.Ticker(self.symbol)
        
        # Fetch daily data for ATR (need extra days for ATR calculation)
        end_date = datetime.now(self.tz)
        start_date = end_date - timedelta(days=self.days + 30)
        
        self._daily_data = ticker.history(
            start=start_date.strftime('%Y-%m-%d'),
            end=end_date.strftime('%Y-%m-%d'),
            interval='1d'
        )
        print(f"  Daily data: {len(self._daily_data)} bars")
        
        # Fetch 15m data for box setup
        self._data_15m = ticker.history(
            period=f'{self.days}d',
            interval='15m'
        )
        print(f"  15m data: {len(self._data_15m)} bars")
        
        # Fetch 5m data for trade triggers
        self._data_5m = ticker.history(
            period=f'{self.days}d',
            interval='5m'
        )
        print(f"  5m data: {len(self._data_5m)} bars")
        
        # Convert timezone-aware indices
        if self._data_15m.index.tz is None:
            self._data_15m.index = self._data_15m.index.tz_localize('UTC').tz_convert(self.tz)
        else:
            self._data_15m.index = self._data_15m.index.tz_convert(self.tz)
            
        if self._data_5m.index.tz is None:
            self._data_5m.index = self._data_5m.index.tz_localize('UTC').tz_convert(self.tz)
        else:
            self._data_5m.index = self._data_5m.index.tz_convert(self.tz)
    
    def calculate_atr_for_date(self, target_date: datetime) -> Optional[float]:
        """
        Calculate 14-period ATR using data up to (and including) the previous day.
        This avoids look-ahead bias.
        
        Uses manual ATR calculation (no pandas_ta dependency):
        TR = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
        ATR = EMA of TR over 14 periods
        
        Args:
            target_date: The trading day for which we need ATR
            
        Returns:
            ATR value or None if insufficient data
        """
        # Filter daily data up to the previous day (before target_date)
        prev_day = target_date.date() - timedelta(days=1)
        
        # Get daily data with date-only index for comparison
        daily_data_filtered = self._daily_data[
            self._daily_data.index.date <= prev_day
        ].tail(config.ATR_PERIOD + 5)  # Get a bit extra for safety
        
        if len(daily_data_filtered) < config.ATR_PERIOD:
            return None
        
        # Manual ATR calculation
        df = daily_data_filtered.copy()
        df['prev_close'] = df['Close'].shift(1)
        df['tr1'] = df['High'] - df['Low']
        df['tr2'] = abs(df['High'] - df['prev_close'])
        df['tr3'] = abs(df['Low'] - df['prev_close'])
        df['TR'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        
        # Calculate ATR using simple moving average for stability
        atr_series = df['TR'].rolling(window=config.ATR_PERIOD).mean()
        
        if atr_series.isna().all():
            return None
        
        return atr_series.iloc[-1]
    
    def get_box_for_date(self, date: datetime) -> Optional[Tuple[float, float]]:
        """
        Get the box (high/low) from the first 15m candle of a trading day.
        The first 15m candle is 09:30-09:45 EST.
        
        Args:
            date: The trading date
            
        Returns:
            Tuple of (box_high, box_low) or None if no data
        """
        # Get 15m candles for this date
        day_data = self._data_15m[self._data_15m.index.date == date.date()]
        
        if len(day_data) == 0:
            return None
        
        # Find the 09:30 candle (first candle of session)
        session_start = time(9, 30)
        first_candle_mask = day_data.index.time == session_start
        
        if not first_candle_mask.any():
            # Try to get the first available candle of the day
            first_candle = day_data.iloc[0]
        else:
            first_candle = day_data[first_candle_mask].iloc[0]
        
        return (first_candle['High'], first_candle['Low'])
    
    def is_hammer(self, candle: pd.Series) -> bool:
        """Detect Hammer pattern (bullish reversal)."""
        open_price = candle['Open']
        high = candle['High']
        low = candle['Low']
        close = candle['Close']
        
        body = abs(close - open_price)
        lower_wick = min(open_price, close) - low
        upper_wick = high - max(open_price, close)
        
        if body == 0:
            body = 0.001
        
        return (
            lower_wick >= config.HAMMER_WICK_RATIO * body and
            upper_wick <= 0.5 * body
        )
    
    def is_inverted_hammer(self, candle: pd.Series) -> bool:
        """Detect Inverted Hammer pattern (bearish reversal at top)."""
        open_price = candle['Open']
        high = candle['High']
        low = candle['Low']
        close = candle['Close']
        
        body = abs(close - open_price)
        lower_wick = min(open_price, close) - low
        upper_wick = high - max(open_price, close)
        
        if body == 0:
            body = 0.001
        
        return (
            upper_wick >= config.HAMMER_WICK_RATIO * body and
            lower_wick <= 0.5 * body
        )
    
    def is_bullish_engulfing(self, current: pd.Series, previous: pd.Series) -> bool:
        """Detect Bullish Engulfing pattern."""
        prev_is_red = previous['Close'] < previous['Open']
        curr_is_green = current['Close'] > current['Open']
        
        if not (prev_is_red and curr_is_green):
            return False
        
        return (
            current['Close'] > previous['Open'] and
            current['Open'] < previous['Close']
        )
    
    def is_bearish_engulfing(self, current: pd.Series, previous: pd.Series) -> bool:
        """Detect Bearish Engulfing pattern."""
        prev_is_green = previous['Close'] > previous['Open']
        curr_is_red = current['Close'] < current['Open']
        
        if not (prev_is_green and curr_is_red):
            return False
        
        return (
            current['Open'] > previous['Close'] and
            current['Close'] < previous['Open']
        )
    
    def simulate_trade(
        self,
        entry_time: datetime,
        direction: str,
        entry_price: float,
        stop_loss: float,
        target: float,
        pattern: str,
        date: datetime
    ) -> Dict:
        """
        Simulate a trade by checking future 5m candles for SL or TP hit.
        
        Args:
            entry_time: Time of entry signal
            direction: 'LONG' or 'SHORT'
            entry_price: Entry price
            stop_loss: Stop loss price
            target: Target price
            pattern: Pattern name
            date: Trading date
            
        Returns:
            Trade result dict
        """
        # Get 5m candles after entry time for this day
        day_data = self._data_5m[self._data_5m.index.date == date.date()]
        future_candles = day_data[day_data.index > entry_time]
        
        outcome = 'OPEN'
        exit_price = None
        exit_time = None
        pnl = 0.0
        
        for idx, candle in future_candles.iterrows():
            if direction == 'LONG':
                # Check if stop loss hit
                if candle['Low'] <= stop_loss:
                    outcome = 'LOSS'
                    exit_price = stop_loss
                    exit_time = idx
                    pnl = stop_loss - entry_price
                    break
                # Check if target hit
                if candle['High'] >= target:
                    outcome = 'WIN'
                    exit_price = target
                    exit_time = idx
                    pnl = target - entry_price
                    break
            else:  # SHORT
                # Check if stop loss hit
                if candle['High'] >= stop_loss:
                    outcome = 'LOSS'
                    exit_price = stop_loss
                    exit_time = idx
                    pnl = entry_price - stop_loss
                    break
                # Check if target hit
                if candle['Low'] <= target:
                    outcome = 'WIN'
                    exit_price = target
                    exit_time = idx
                    pnl = entry_price - target
                    break
        
        # If trade didn't close by end of scanning window, mark as timeout
        if outcome == 'OPEN':
            # Use last candle's close as exit
            if len(future_candles) > 0:
                last_candle = future_candles.iloc[-1]
                exit_price = last_candle['Close']
                exit_time = future_candles.index[-1]
                pnl = (exit_price - entry_price) if direction == 'LONG' else (entry_price - exit_price)
                outcome = 'WIN' if pnl > 0 else 'LOSS'
        
        return {
            'date': date.strftime('%Y-%m-%d'),
            'entry_time': entry_time.strftime('%Y-%m-%d %H:%M:%S'),
            'exit_time': exit_time.strftime('%Y-%m-%d %H:%M:%S') if exit_time else None,
            'direction': direction,
            'pattern': pattern,
            'entry_price': round(entry_price, 2),
            'stop_loss': round(stop_loss, 2),
            'target': round(target, 2),
            'exit_price': round(exit_price, 2) if exit_price else None,
            'outcome': outcome,
            'pnl': round(pnl, 2)
        }
    
    def process_day(self, date: datetime) -> Optional[Dict]:
        """
        Process a single trading day.
        
        Args:
            date: The trading date
            
        Returns:
            Trade result if a trade was taken, None otherwise
        """
        # Step 1: Calculate ATR using previous day's data
        atr = self.calculate_atr_for_date(date)
        if atr is None:
            return None
        
        # Step 2: Get box from first 15m candle
        box = self.get_box_for_date(date)
        if box is None:
            return None
        
        box_high, box_low = box
        candle_range = box_high - box_low
        
        # Step 3: Validate liquidity (>= 25% of ATR)
        threshold = atr * config.LIQUIDITY_THRESHOLD
        if candle_range < threshold:
            self.daily_results.append({
                'date': date.strftime('%Y-%m-%d'),
                'atr': round(atr, 2),
                'box_high': round(box_high, 2),
                'box_low': round(box_low, 2),
                'range': round(candle_range, 2),
                'threshold': round(threshold, 2),
                'valid': False,
                'trade_taken': False
            })
            return None
        
        self.daily_results.append({
            'date': date.strftime('%Y-%m-%d'),
            'atr': round(atr, 2),
            'box_high': round(box_high, 2),
            'box_low': round(box_low, 2),
            'range': round(candle_range, 2),
            'threshold': round(threshold, 2),
            'valid': True,
            'trade_taken': False
        })
        
        # Step 4: Get 5m candles for scanning window (09:45 - 11:00)
        day_data = self._data_5m[self._data_5m.index.date == date.date()]
        
        scan_start = time(9, 45)
        scan_end = time(11, 0)
        
        scan_window = day_data[
            (day_data.index.time > scan_start) &
            (day_data.index.time <= scan_end)
        ]
        
        if len(scan_window) < 2:
            return None
        
        # Step 5: Iterate through candles looking for signals
        for i in range(1, len(scan_window)):
            current = scan_window.iloc[i]
            previous = scan_window.iloc[i - 1]
            current_time = scan_window.index[i]
            
            current_low = current['Low']
            current_high = current['High']
            
            signal = None
            direction = None
            pattern = None
            entry_price = None
            stop_loss = None
            target = None
            
            # Check for LONG signals (price below box)
            if current_low < box_low:
                if self.is_hammer(current):
                    signal = True
                    direction = 'LONG'
                    pattern = 'hammer'
                    entry_price = current['Close']
                    stop_loss = current['Low']
                    target = box_high
                elif self.is_bullish_engulfing(current, previous):
                    signal = True
                    direction = 'LONG'
                    pattern = 'bullish_engulfing'
                    entry_price = current['Close']
                    stop_loss = min(current['Low'], previous['Low'])
                    target = box_high
            
            # Check for SHORT signals (price above box)
            elif current_high > box_high:
                if self.is_inverted_hammer(current):
                    signal = True
                    direction = 'SHORT'
                    pattern = 'inverted_hammer'
                    entry_price = current['Close']
                    stop_loss = current['High']
                    target = box_low
                elif self.is_bearish_engulfing(current, previous):
                    signal = True
                    direction = 'SHORT'
                    pattern = 'bearish_engulfing'
                    entry_price = current['Close']
                    stop_loss = max(current['High'], previous['High'])
                    target = box_low
            
            # If signal found, simulate the trade and break (one trade per day)
            if signal:
                trade = self.simulate_trade(
                    entry_time=current_time,
                    direction=direction,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    target=target,
                    pattern=pattern,
                    date=date
                )
                trade['box_high'] = round(box_high, 2)
                trade['box_low'] = round(box_low, 2)
                trade['atr'] = round(atr, 2)
                
                # Update daily result
                self.daily_results[-1]['trade_taken'] = True
                
                return trade
        
        return None
    
    def run(self) -> None:
        """
        Run the complete backtest.
        """
        print(f"\n{'='*60}")
        print(f"Quick Flip Scalper Backtest")
        print(f"Symbol: {self.symbol}")
        print(f"Period: Last {self.days} days")
        print(f"{'='*60}\n")
        
        # Fetch all data
        self.fetch_all_data()
        
        # Get unique trading dates from 5m data
        trading_dates = pd.Series(self._data_5m.index.date).unique()
        
        print(f"\nProcessing {len(trading_dates)} trading days...\n")
        
        for date in trading_dates:
            date_dt = datetime.combine(date, time(9, 30))
            date_dt = self.tz.localize(date_dt)
            
            trade = self.process_day(date_dt)
            if trade:
                self.trades.append(trade)
                print(f"  {trade['date']}: {trade['direction']} ({trade['pattern']}) -> {trade['outcome']} (${trade['pnl']:.2f})")
        
        # Generate report
        self.generate_report()
        self.save_trade_log()
    
    def generate_report(self) -> None:
        """
        Generate and print the backtest summary report.
        """
        total_days = len(self.daily_results)
        valid_days = sum(1 for d in self.daily_results if d['valid'])
        total_trades = len(self.trades)
        wins = sum(1 for t in self.trades if t['outcome'] == 'WIN')
        losses = sum(1 for t in self.trades if t['outcome'] == 'LOSS')
        
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        # Calculate profit factor
        total_wins = sum(t['pnl'] for t in self.trades if t['pnl'] > 0)
        total_losses = abs(sum(t['pnl'] for t in self.trades if t['pnl'] < 0))
        profit_factor = (total_wins / total_losses) if total_losses > 0 else float('inf')
        
        # Calculate averages
        avg_win = (total_wins / wins) if wins > 0 else 0
        avg_loss = (total_losses / losses) if losses > 0 else 0
        
        print(f"\n{'='*60}")
        print(f"--- Backtest Results (Last {self.days} Days) ---")
        print(f"{'='*60}")
        print(f"Total Days Scanned: {total_days}")
        print(f"Valid Setup Days (>25% ATR): {valid_days}")
        print(f"Trades Taken: {total_trades}")
        print(f"Wins: {wins}")
        print(f"Losses: {losses}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Profit Factor: {profit_factor:.2f}")
        print(f"Average Win: ${avg_win:.2f}")
        print(f"Average Loss: ${avg_loss:.2f}")
        print(f"{'='*60}\n")
    
    def save_trade_log(self, filename: str = 'trade_log.csv') -> None:
        """
        Save all trades to a CSV file.
        
        Args:
            filename: Output filename
        """
        if not self.trades:
            print("No trades to save.")
            return
        
        fieldnames = [
            'date', 'entry_time', 'exit_time', 'direction', 'pattern',
            'entry_price', 'stop_loss', 'target', 'exit_price',
            'box_high', 'box_low', 'atr', 'outcome', 'pnl'
        ]
        
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.trades)
        
        print(f"Trade log saved to: {filename}")


def main():
    """Main entry point for backtesting."""
    engine = BacktestEngine(symbol=config.SYMBOL, days=59)
    engine.run()


if __name__ == '__main__':
    main()
