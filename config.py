"""
Quick Flip Scalper - Configuration
Trading bot configuration and constants.
"""

# Data Provider Selection
# Options: "alpaca" or "yfinance"
DATA_PROVIDER = "yfinance"

# Alpaca Configuration
ALPACA_PAPER = True  # Use paper trading endpoint (recommended for testing)
ALPACA_TRADING_ENABLED = True  # Enable/disable automated trading
ALPACA_POSITION_SIZE_USD = 100  # Dollar amount per trade (e.g., $100)

# Trading Symbols
# Top 10 profitable stocks (Profit Factor > 1.5)
# Based on 60-day backtest leaderboard analysis
SYMBOLS = [
    "AAPL",  # PF: 3.15
    "MSFT",  # PF: 2.89
    "CVX",   # PF: 2.66
    "MRK",   # PF: 2.55
    "WFC",   # PF: 2.51
    "MCD",   # PF: 2.23
    "VZ",    # PF: 1.83
    "QQQ",   # PF: 1.81
    "UNH",   # PF: 1.70
    "AMD",   # PF: 1.67
]
SYMBOL = "AAPL"  # Default for single-symbol mode

# ATR Configuration
ATR_PERIOD = 14
LIQUIDITY_THRESHOLD = 0.25  # 25% of daily ATR

# POST Endpoint for signals
# After deploying, set this to your Cloud Function URL:
# https://REGION-PROJECT_ID.cloudfunctions.net/telegram-publisher
ENDPOINT_URL = "https://us-central1-task-managment-481c5.cloudfunctions.net/telegram-publisher"

# Alpaca Order Executor Cloud Function URL
ALPACA_ORDER_EXECUTOR_URL = "https://us-central1-task-managment-481c5.cloudfunctions.net/alpaca-order-executor"

# Trading Hours (EST)
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
INIT_HOUR = 9
INIT_MINUTE = 45
SESSION_END_HOUR = 10      # Changed from 11 - trades after 10:45 have poor win rate
SESSION_END_MINUTE = 45    # Changed from 0

# Scan Interval (minutes)
SCAN_INTERVAL_MINUTES = 5

# Timezone
TIMEZONE = "America/New_York"

# Pattern Recognition Thresholds
HAMMER_WICK_RATIO = 2.0  # Lower wick must be at least 2x body size
ENGULFING_BODY_OVERLAP = 1.0  # Current body must fully cover previous

# Gap Fill Strategy Configuration
GAP_THRESHOLD = 0.01  # 1% gap required to trigger trade
GAP_STOP_LOSS_RATIO = 0.5  # Risk 0.5 to make 1.0 (Stop is 50% of gap size)
