"""
Backtest for a specific date.
"""
from backtest import BacktestEngine
import pandas as pd
from datetime import datetime, time
import pytz

# Top 10 stocks from config
SYMBOLS = ['AAPL', 'MSFT', 'CVX', 'MRK', 'WFC', 'MCD', 'VZ', 'QQQ', 'UNH', 'AMD']
TARGET_DATE = '2026-01-14'

print(f'Backtesting {len(SYMBOLS)} stocks for {TARGET_DATE}')
print('='*60)

trades_today = []
tz = pytz.timezone('America/New_York')

for sym in SYMBOLS:
    print(f'{sym}...', end=' ', flush=True)
    engine = BacktestEngine(symbol=sym, days=5)
    engine.fetch_all_data()
    
    # Find today's date in data
    target = datetime.strptime(TARGET_DATE, '%Y-%m-%d').date()
    date_dt = datetime.combine(target, time(9, 30))
    date_dt = tz.localize(date_dt)
    
    trade = engine.process_day(date_dt)
    if trade:
        trade['symbol'] = sym
        trades_today.append(trade)
        print(f"{trade['direction']} ({trade['pattern']}) -> {trade['outcome']} (${trade['pnl']:+.2f})")
    else:
        print('No trade')

print()
print('='*60)
print(f'RESULTS FOR {TARGET_DATE}')
print('='*60)

if trades_today:
    wins = sum(1 for t in trades_today if t['outcome'] == 'WIN')
    losses = len(trades_today) - wins
    total_pnl = sum(t['pnl'] for t in trades_today)
    
    print(f'Trades: {len(trades_today)}')
    print(f'Wins: {wins}, Losses: {losses}')
    print(f'Total P&L (per share): ${total_pnl:.2f}')
    
    # $500 per trade
    dollar_pnl = 0
    for t in trades_today:
        shares = 500 / t['entry_price']
        dollar_pnl += shares * t['pnl']
    print(f'Total P&L ($500/trade): ${dollar_pnl:.2f}')
else:
    print('No trades today')
