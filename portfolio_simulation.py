"""
Portfolio simulation: Trade ONCE per day across ANY of the 5 symbols.
If MSFT doesn't signal, check QQQ, then AMD, etc.
"""
from backtest import BacktestEngine
import pandas as pd
from datetime import datetime

# Run backtests for all symbols and collect trades
symbols = ['MSFT', 'QQQ', 'AMD', 'AAPL', 'META']
all_trades = []

print("Collecting trades from all symbols...")
for sym in symbols:
    engine = BacktestEngine(symbol=sym, days=60)
    engine.fetch_all_data()
    
    trading_dates = pd.Series(engine._data_5m.index.date).unique()
    
    from datetime import time
    for date in trading_dates:
        date_dt = datetime.combine(date, time(9, 30))
        date_dt = engine.tz.localize(date_dt)
        trade = engine.process_day(date_dt)
        if trade:
            trade['symbol'] = sym
            all_trades.append(trade)

# Create DataFrame
df = pd.DataFrame(all_trades)
df['date'] = pd.to_datetime(df['date'])

print(f"\nTotal trades across all symbols: {len(df)}")

# Group by date and pick FIRST trade per day (simulating one trade per day)
# Sort by entry_time to get the earliest signal each day
df['entry_dt'] = pd.to_datetime(df['entry_time'])
df = df.sort_values('entry_dt')

# Take first trade per date
portfolio_trades = df.groupby('date').first().reset_index()

print(f"Portfolio trades (one per day): {len(portfolio_trades)}")

# Calculate compounding
balance = 500.0
print("\n" + "="*70)
print("PORTFOLIO SIMULATION: One trade per day, first available signal")
print("="*70)

for _, trade in portfolio_trades.iterrows():
    shares = balance / trade['entry_price']
    pnl = shares * trade['pnl']
    balance += pnl
    outcome = "WIN" if trade['outcome'] == 'WIN' else "LOSS"
    print(f"{trade['date'].strftime('%Y-%m-%d')}: {trade['symbol']:4} {trade['direction']:5} ({trade['pattern']:18}) -> {outcome} ${pnl:+.2f} | Balance: ${balance:.2f}")

print("\n" + "="*70)
print("PORTFOLIO RESULTS")
print("="*70)

wins = len(portfolio_trades[portfolio_trades['outcome'] == 'WIN'])
losses = len(portfolio_trades[portfolio_trades['outcome'] == 'LOSS'])
total = len(portfolio_trades)
win_rate = (wins / total) * 100 if total > 0 else 0

total_profit = balance - 500
pct_return = (total_profit / 500) * 100

print(f"Total Trading Days: {total}")
print(f"Wins: {wins}")
print(f"Losses: {losses}")
print(f"Win Rate: {win_rate:.1f}%")
print(f"Starting Balance: $500.00")
print(f"Final Balance: ${balance:.2f}")
print(f"Total Profit: ${total_profit:.2f}")
print(f"Return: {pct_return:.1f}%")
print("="*70)

# Compare with single-symbol results
print("\nCOMPARISON:")
print(f"Portfolio (any symbol): ${total_profit:.2f} ({pct_return:.1f}%)")
print(f"MSFT only: ~$17.85 (3.6%)")
print(f"QQQ only: ~$10.97 (2.2%)")
print(f"AMD only: ~$24.49 (4.9%)")
