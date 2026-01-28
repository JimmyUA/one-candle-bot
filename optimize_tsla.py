"""
TSLA Strategy Optimizer
Backtests Quick Flip Scalper on TSLA with 5x leverage and parameter grid search.
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, time
import pytz
import itertools
from typing import Dict, List, Tuple, Optional

# Constants
SYMBOL = 'TSLA'
DAYS_BACK = 59  # yfinance limit for 5m data
LEVERAGE = 5.0
CAPITAL_PER_TRADE = 1000.0  # Base capital
POSITION_SIZE = CAPITAL_PER_TRADE * LEVERAGE  # $5000 buying power
TIMEZONE = "America/New_York"
ATR_PERIOD = 14

class StrategyOptimizer:
    def __init__(self):
        self.tz = pytz.timezone(TIMEZONE)
        self.data_5m = None
        self.data_daily = None
        
    def fetch_data(self):
        print(f"Fetching {DAYS_BACK} days of data for {SYMBOL}...")
        ticker = yf.Ticker(SYMBOL)
        
        # 5m intraday data
        self.data_5m = ticker.history(period=f"{DAYS_BACK}d", interval="5m")
        if self.data_5m.index.tz is None:
            self.data_5m.index = self.data_5m.index.tz_localize('UTC').tz_convert(self.tz)
        else:
            self.data_5m.index = self.data_5m.index.tz_convert(self.tz)
            
        # Daily data for ATR
        end_date = datetime.now(self.tz)
        start_date = end_date - timedelta(days=DAYS_BACK + 30)
        self.data_daily = ticker.history(start=start_date.strftime('%Y-%m-%d'), interval="1d")
        
        print(f"Loaded {len(self.data_5m)} 5m bars and {len(self.data_daily)} daily bars.")

    def calculate_atr(self, target_date: datetime) -> float:
        # Get data up to previous day
        mask = self.data_daily.index.date < target_date.date()
        df = self.data_daily[mask].tail(ATR_PERIOD + 1).copy()
        
        if len(df) < ATR_PERIOD:
            return 0.0
            
        df['prev_close'] = df['Close'].shift(1)
        df['tr'] = pd.concat([
            df['High'] - df['Low'],
            abs(df['High'] - df['prev_close']),
            abs(df['Low'] - df['prev_close'])
        ], axis=1).max(axis=1)
        
        return df['tr'].rolling(window=ATR_PERIOD).mean().iloc[-1]

    def get_session_box(self, date_data: pd.DataFrame) -> Optional[Tuple[float, float]]:
        # First 15m (09:30-09:45) high/low
        # Assuming 5m candles: 09:30, 09:35, 09:40
        session_start = time(9, 30)
        first_3_candles = date_data[
            (date_data.index.time >= session_start) & 
            (date_data.index.time < time(9, 45))
        ]
        
        if len(first_3_candles) < 3:
            return None
            
        box_high = first_3_candles['High'].max()
        box_low = first_3_candles['Low'].min()
        return box_high, box_low

    def backtest_strategy(self, params: Dict) -> Dict:
        """
        Run backtest with specific parameters.
        params: {
            'liquidity_threshold': float (ATR multiplier),
            'profit_target_type': str ('box', '1:1', '1:2'),
            'stop_loss_type': str ('tight', 'wide'),
            'session_end_hour': int
        }
        """
        trades = []
        equity = 0.0
        
        grouped = self.data_5m.groupby(self.data_5m.index.date)
        
        for date, day_data in grouped:
            date_dt = datetime.combine(date, time(9, 30))
            atr = self.calculate_atr(pd.Timestamp(date_dt))
            
            if atr == 0: continue
            
            box = self.get_session_box(day_data)
            if not box: continue
            
            box_high, box_low = box
            box_range = box_high - box_low
            
            # Liquidity Filter
            if box_range < (atr * params['liquidity_threshold']):
                continue
                
            # Scan for trades
            scan_start = time(9, 45)
            scan_end = time(params['session_end_hour'], 45)
            
            scan_data = day_data[
                (day_data.index.time >= scan_start) & 
                (day_data.index.time <= scan_end)
            ]
            
            for i in range(1, len(scan_data)):
                curr = scan_data.iloc[i]
                prev = scan_data.iloc[i-1]
                
                signal = None
                direction = None
                entry = 0.0
                stop = 0.0
                target = 0.0
                
                # Logic: Box Breakout Reversal
                # LONG: Price dips below box low and shows bullish pattern
                if curr['Low'] < box_low:
                    # Simple Hammer logic
                    body = abs(curr['Close'] - curr['Open'])
                    lower_wick = min(curr['Open'], curr['Close']) - curr['Low']
                    if lower_wick > (2 * body):
                        direction = 'LONG'
                        entry = curr['Close']
                        stop = curr['Low'] if params['stop_loss_type'] == 'tight' else (curr['Low'] - (0.1 * box_range))
                        
                        risk = entry - stop
                        if params['profit_target_type'] == 'box':
                            target = box_high
                        elif params['profit_target_type'] == '1:1':
                            target = entry + risk
                        elif params['profit_target_type'] == '1:2':
                            target = entry + (2 * risk)

                # SHORT: Price pops above box high and shows bearish pattern
                elif curr['High'] > box_high:
                    # Simple Shooting Star logic
                    body = abs(curr['Close'] - curr['Open'])
                    upper_wick = curr['High'] - max(curr['Open'], curr['Close'])
                    if upper_wick > (2 * body):
                        direction = 'SHORT'
                        entry = curr['Close']
                        stop = curr['High'] if params['stop_loss_type'] == 'tight' else (curr['High'] + (0.1 * box_range))
                        
                        risk = stop - entry
                        if params['profit_target_type'] == 'box':
                            target = box_low
                        elif params['profit_target_type'] == '1:1':
                            target = entry - risk
                        elif params['profit_target_type'] == '1:2':
                            target = entry - (2 * risk)

                if direction:
                    # Simulate Trade Result
                    # Check subsequent candles in the same day
                    future_candles = day_data[day_data.index > curr.name]
                    pnl = 0
                    outcome = 'OPEN'
                    
                    for _, candle in future_candles.iterrows():
                        if direction == 'LONG':
                            if candle['Low'] <= stop:
                                pnl = - (entry - stop)
                                outcome = 'LOSS'
                                break
                            elif candle['High'] >= target:
                                pnl = (target - entry)
                                outcome = 'WIN'
                                break
                        else: # SHORT
                            if candle['High'] >= stop:
                                pnl = - (stop - entry)
                                outcome = 'LOSS'
                                break
                            elif candle['Low'] <= target:
                                pnl = (entry - target)
                                outcome = 'WIN'
                                break
                    
                    # Force close at end of day
                    if outcome == 'OPEN' and len(future_candles) > 0:
                        last = future_candles.iloc[-1]['Close']
                        if direction == 'LONG':
                            pnl = last - entry
                        else:
                            pnl = entry - last
                    
                    # Calculate leveraged PnL
                    # Position size is fixed $5000 (5x of $1000)
                    # Number of shares = $5000 / Entry Price
                    shares = POSITION_SIZE / entry
                    net_pnl = pnl * shares
                    
                    trades.append(net_pnl)
                    equity += net_pnl
                    break # One trade per day limit
        
        return {
            'trades': len(trades),
            'wins': len([p for p in trades if p > 0]),
            'total_pnl': equity,
            'avg_trade': equity / len(trades) if trades else 0
        }

    def run_optimization(self):
        self.fetch_data()
        
        # Parameter Grid
        liquidity_thresholds = [0.15, 0.25, 0.35]
        profit_targets = ['box', '1:1', '1:2']
        stop_losses = ['tight', 'wide']
        session_ends = [10, 11, 12] # Hour
        
        best_pnl = -float('inf')
        best_params = {}
        best_stats = {}
        
        print(f"\nScanning parameters for {SYMBOL}...")
        
        combinations = list(itertools.product(liquidity_thresholds, profit_targets, stop_losses, session_ends))
        
        for liq, pt, sl, end in combinations:
            params = {
                'liquidity_threshold': liq,
                'profit_target_type': pt,
                'stop_loss_type': sl,
                'session_end_hour': end
            }
            
            stats = self.backtest_strategy(params)
            
            if stats['total_pnl'] > best_pnl:
                best_pnl = stats['total_pnl']
                best_params = params
                best_stats = stats
                print(f"New Best: ${best_pnl:.2f} | Params: {params}")

        print("\n" + "="*50)
        print("OPTIMIZATION RESULTS (Last 60 Days)")
        print("="*50)
        print(f"Best Strategy Configuration:")
        print(f"  Liquidity Threshold: {best_params['liquidity_threshold']} * ATR")
        print(f"  Profit Target: {best_params['profit_target_type']}")
        print(f"  Stop Loss: {best_params['stop_loss_type']}")
        print(f"  Trading Until: {best_params['session_end_hour']}:45")
        print("-" * 30)
        print(f"Performance (5x Leverage on $1000 Base):")
        print(f"  Total Net Profit: ${best_stats['total_pnl']:.2f}")
        print(f"  Total Trades: {best_stats['trades']}")
        print(f"  Win Rate: {(best_stats['wins']/best_stats['trades']*100 if best_stats['trades'] else 0):.1f}%")
        print(f"  Avg PnL per Trade: ${best_stats['avg_trade']:.2f}")
        print("="*50)

if __name__ == "__main__":
    optimizer = StrategyOptimizer()
    optimizer.run_optimization()
