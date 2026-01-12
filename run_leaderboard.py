"""
Leaderboard: Backtest all major US large-cap stocks.
"""
from backtest import BacktestEngine
import pandas as pd

# Major US Large-Cap Stocks
SYMBOLS = [
    # Tech
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'AMD', 'INTC', 'CRM', 
    'ORCL', 'ADBE', 'NFLX', 'AVGO', 'CSCO',
    # Finance
    'JPM', 'BAC', 'WFC', 'GS', 'V', 'MA',
    # Healthcare
    'JNJ', 'UNH', 'PFE', 'MRK', 'ABBV', 'LLY',
    # Consumer
    'WMT', 'HD', 'MCD', 'KO', 'PEP', 'NKE', 'DIS', 'SBUX', 'TGT', 'COST',
    # Energy
    'XOM', 'CVX',
    # Industrial
    'CAT', 'BA', 'GE', 'HON', 'UPS',
    # Telecom
    'VZ', 'T',
    # ETFs
    'SPY', 'QQQ', 'DIA', 'IWM'
]

results = []

print(f"Running backtest on {len(SYMBOLS)} stocks...")
print("="*70)

for i, sym in enumerate(SYMBOLS):
    try:
        print(f"[{i+1}/{len(SYMBOLS)}] {sym}...", end=" ", flush=True)
        
        # Create fresh engine and run properly
        engine = BacktestEngine(symbol=sym, days=60)
        engine.fetch_all_data()
        
        # Get unique trading dates from 5m data
        trading_dates = pd.Series(engine._data_5m.index.date).unique()
        
        from datetime import datetime, time
        for date in trading_dates:
            date_dt = datetime.combine(date, time(9, 30))
            date_dt = engine.tz.localize(date_dt)
            trade = engine.process_day(date_dt)
            if trade:
                engine.trades.append(trade)
        
        trades = engine.trades
        if len(trades) == 0:
            print("No trades")
            results.append({
                'Symbol': sym,
                'Trades': 0,
                'Wins': 0,
                'Losses': 0,
                'WinRate': 0,
                'ProfitFactor': 0,
                'AvgWin': 0,
                'AvgLoss': 0,
                'Profit_500': 0,
                'Return%': 0
            })
            continue
        
        wins = sum(1 for t in trades if t['outcome'] == 'WIN')
        losses = sum(1 for t in trades if t['outcome'] == 'LOSS')
        total = len(trades)
        win_rate = (wins / total * 100) if total > 0 else 0
        
        total_wins = sum(t['pnl'] for t in trades if t['pnl'] > 0)
        total_losses = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
        profit_factor = (total_wins / total_losses) if total_losses > 0 else 999
        
        avg_win = total_wins / wins if wins > 0 else 0
        avg_loss = total_losses / losses if losses > 0 else 0
        
        # Simulate $500 compounding
        balance = 500.0
        for trade in trades:
            shares = balance / trade['entry_price']
            pnl = shares * trade['pnl']
            balance += pnl
        
        profit = balance - 500
        
        results.append({
            'Symbol': sym,
            'Trades': total,
            'Wins': wins,
            'Losses': losses,
            'WinRate': round(win_rate, 1),
            'ProfitFactor': round(profit_factor, 2),
            'AvgWin': round(avg_win, 2),
            'AvgLoss': round(avg_loss, 2),
            'Profit_500': round(profit, 2),
            'Return%': round((profit/500)*100, 1)
        })
        
        print(f"Trades:{total}, WR:{win_rate:.0f}%, PF:{profit_factor:.2f}")
        
    except Exception as e:
        print(f"Error: {e}")
        results.append({
            'Symbol': sym,
            'Trades': 0,
            'Wins': 0,
            'Losses': 0,
            'WinRate': 0,
            'ProfitFactor': 0,
            'AvgWin': 0,
            'AvgLoss': 0,
            'Profit_500': 0,
            'Return%': 0
        })

# Create leaderboard
df = pd.DataFrame(results)
df = df.sort_values('ProfitFactor', ascending=False)

print("\n" + "="*70)
print("LEADERBOARD - Sorted by Profit Factor")
print("="*70)
print(df.to_string(index=False))

# Save to CSV
df.to_csv('leaderboard.csv', index=False)
print("\nSaved to: leaderboard.csv")

# Top performers
print("\n" + "="*70)
print("TOP 10 STOCKS (Profit Factor > 1.0 = Profitable)")
print("="*70)
profitable = df[df['ProfitFactor'] >= 1.0].head(10)
print(profitable.to_string(index=False))

print("\n" + "="*70)
print("AVOID (Profit Factor < 1.0)")
print("="*70)
avoid = df[df['ProfitFactor'] < 1.0]
print(avoid.to_string(index=False))
