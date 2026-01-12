"""
Extended backtest for top 3 symbols by win rate.
"""
from backtest import BacktestEngine

symbols = ['MSFT', 'QQQ', 'AMD']

for sym in symbols:
    print()
    print("=" * 60)
    print(f"Testing {sym} with MAXIMUM available data (60 days)")
    print("=" * 60)
    
    engine = BacktestEngine(symbol=sym, days=60)
    engine.run()
    
    # Calculate $500 compounding
    balance = 500.0
    for trade in engine.trades:
        shares = balance / trade['entry_price']
        pnl = shares * trade['pnl']
        balance += pnl
    
    profit = balance - 500
    pct = (profit / 500) * 100
    print(f"\n$500 Compounding: ${balance:.2f} (Profit: ${profit:.2f}, {pct:.1f}%)")
