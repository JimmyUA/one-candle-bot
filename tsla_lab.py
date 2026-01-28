"""
TSLA Pattern Lab
Comparative backtesting of multiple strategy archetypes to find high win-rate patterns.
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, time
import pytz
import numpy as np

# Constants
SYMBOL = 'TSLA'
DAYS_BACK = 59
TIMEZONE = "America/New_York"

class StrategyLab:
    def __init__(self):
        self.tz = pytz.timezone(TIMEZONE)
        self.data_5m = None
        self.data_daily = None
        self.results = []
        
    def fetch_data(self):
        print(f"Fetching data for {SYMBOL}...")
        ticker = yf.Ticker(SYMBOL)
        
        # 5m intraday data
        self.data_5m = ticker.history(period=f"{DAYS_BACK}d", interval="5m")
        if self.data_5m.index.tz is None:
            self.data_5m.index = self.data_5m.index.tz_localize('UTC').tz_convert(self.tz)
        else:
            self.data_5m.index = self.data_5m.index.tz_convert(self.tz)
            
        # Daily data
        end_date = datetime.now(self.tz)
        start_date = end_date - timedelta(days=DAYS_BACK + 30)
        self.data_daily = ticker.history(start=start_date.strftime('%Y-%m-%d'), interval="1d")
        
    def calculate_vwap(self, df):
        v = df['Volume'].values
        tp = (df['High'] + df['Low'] + df['Close']).values / 3
        return df.assign(vwap=(tp * v).cumsum() / v.cumsum())

    def simulate_trade(self, entry, target, stop, direction, day_data, entry_time_idx):
        future_candles = day_data[day_data.index > entry_time_idx]
        
        for idx, candle in future_candles.iterrows():
            if direction == 'LONG':
                if candle['Low'] <= stop:
                    return 'LOSS'
                if candle['High'] >= target:
                    return 'WIN'
            else: # SHORT
                if candle['High'] >= stop:
                    return 'LOSS'
                if candle['Low'] <= target:
                    return 'WIN'
        
        # End of day exit
        if len(future_candles) > 0:
            last = future_candles.iloc[-1]['Close']
            if direction == 'LONG':
                return 'WIN' if last > entry else 'LOSS'
            else:
                return 'WIN' if last < entry else 'LOSS'
        return 'OPEN'

    def run_gap_fill_strategy(self):
        """
        Strategy: Gap Fill
        If Open is significantly away from Prev Close, trade towards Prev Close.
        Gap > 1%
        Target: Prev Close
        Stop: Open +/- 50% of Gap
        """
        stats = {'name': 'Gap Fill', 'wins': 0, 'losses': 0, 'trades': 0}
        
        grouped = self.data_5m.groupby(self.data_5m.index.date)
        
        for date, day_data in grouped:
            # Need previous close
            prev_day_date = date - timedelta(days=1)
            # Simple lookup in daily data
            # Note: This is approximate if daily index is not exact date match, 
            # but for 'history' call it usually works or we search.
            
            # Using daily df to get prev close is safer
            daily_loc = self.data_daily.index.date
            # Find index of current date
            try:
                # Find the location where date matches
                idx = np.where(daily_loc == date)[0][0]
                if idx == 0: continue
                prev_close = self.data_daily.iloc[idx-1]['Close']
            except IndexError:
                continue
                
            open_price = day_data.iloc[0]['Open']
            gap_percent = (open_price - prev_close) / prev_close
            
            if abs(gap_percent) < 0.01: # 1% gap threshold
                continue
                
            entry = open_price
            target = prev_close
            direction = 'SHORT' if gap_percent > 0 else 'LONG'
            gap_size = abs(open_price - prev_close)
            stop = open_price + (gap_size * 0.5) if direction == 'SHORT' else open_price - (gap_size * 0.5)
            
            outcome = self.simulate_trade(entry, target, stop, direction, day_data, day_data.index[0])
            
            if outcome == 'WIN': stats['wins'] += 1
            if outcome == 'LOSS': stats['losses'] += 1
            stats['trades'] += 1
            
        self.results.append(stats)

    def run_orb_trend_strategy(self):
        """
        Strategy: ORB Trend (Momentum)
        Breakout of first 15m range.
        Entry: Break of High/Low
        Target: 1:1 Risk/Reward
        Stop: Midpoint of Range
        """
        stats = {'name': 'ORB Momentum (15m)', 'wins': 0, 'losses': 0, 'trades': 0}
        
        grouped = self.data_5m.groupby(self.data_5m.index.date)
        
        for date, day_data in grouped:
            if len(day_data) < 4: continue
            
            # First 15m (3 candles)
            first_3 = day_data.iloc[:3]
            orb_high = first_3['High'].max()
            orb_low = first_3['Low'].min()
            orb_mid = (orb_high + orb_low) / 2
            
            # Scan rest of day
            rest_of_day = day_data.iloc[3:]
            
            for idx, candle in rest_of_day.iterrows():
                # One trade per day
                direction = None
                
                if candle['Close'] > orb_high:
                    direction = 'LONG'
                    entry = candle['Close']
                    stop = orb_mid
                    target = entry + (entry - stop) # 1:1
                elif candle['Close'] < orb_low:
                    direction = 'SHORT'
                    entry = candle['Close']
                    stop = orb_mid
                    target = entry - (stop - entry) # 1:1
                    
                if direction:
                    outcome = self.simulate_trade(entry, target, stop, direction, day_data, idx)
                    if outcome == 'WIN': stats['wins'] += 1
                    if outcome == 'LOSS': stats['losses'] += 1
                    stats['trades'] += 1
                    break
        
        self.results.append(stats)

    def run_vwap_bounce_strategy(self):
        """
        Strategy: VWAP Bounce (Pullback)
        Trend established (price > VWAP for 30 mins), then pulls back to touch VWAP.
        Entry: Touch of VWAP
        Target: High of day so far
        Stop: VWAP - 0.5%
        """
        stats = {'name': 'VWAP Bounce', 'wins': 0, 'losses': 0, 'trades': 0}
        
        grouped = self.data_5m.groupby(self.data_5m.index.date)
        
        for date, day_data in grouped:
            if len(day_data) < 10: continue
            
            # Calculate VWAP
            day_data = self.calculate_vwap(day_data.copy())
            
            # Need to establish trend first (e.g., first hour)
            # Scan starting 10:30
            scan_start_idx = 12 # approx 1 hour in 5m bars
            
            trade_taken = False
            for i in range(scan_start_idx, len(day_data)):
                candle = day_data.iloc[i]
                vwap = candle['vwap']
                
                # Check for Pullback to VWAP in Uptrend
                # Condition 1: Price was above VWAP significantly recently
                # (Simplified: Look at 1 hour ago)
                prev_hour = day_data.iloc[i-12:i]
                if (prev_hour['Close'] > prev_hour['vwap']).all():
                    # Condition 2: Current Low touches or dips below VWAP
                    if candle['Low'] <= vwap and candle['Close'] > vwap: # Bounce logic
                        entry = candle['Close']
                        stop = vwap * 0.995 # 0.5% stop
                        target = day_data.iloc[:i]['High'].max() # Test earlier high
                        
                        outcome = self.simulate_trade(entry, target, stop, 'LONG', day_data, candle.name)
                        if outcome == 'WIN': stats['wins'] += 1
                        if outcome == 'LOSS': stats['losses'] += 1
                        stats['trades'] += 1
                        trade_taken = True
                        break
            
        self.results.append(stats)

    def run(self):
        self.fetch_data()
        
        print("\nRunning Gap Fill Strategy...")
        self.run_gap_fill_strategy()
        
        print("Running ORB Momentum Strategy...")
        self.run_orb_trend_strategy()
        
        print("Running VWAP Bounce Strategy...")
        self.run_vwap_bounce_strategy()
        
        print("\n" + "="*60)
        print("TSLA PATTERN LAB RESULTS (Last 60 Days)")
        print("="*60)
        print(f"{'STRATEGY':<25} | {'WIN RATE':<10} | {'TRADES':<8} | {'WINS':<6} | {'LOSSES':<6}")
        print("-" * 65)
        
        for res in self.results:
            total = res['trades']
            wr = (res['wins'] / total * 100) if total > 0 else 0
            print(f"{res['name']:<25} | {wr:<9.1f}% | {total:<8} | {res['wins']:<6} | {res['losses']:<6}")
        print("="*60)

if __name__ == "__main__":
    lab = StrategyLab()
    lab.run()
