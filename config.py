"""
Quick Flip Scalper - Configuration
Trading bot configuration and constants.
"""

# Trading Symbol
SYMBOL = "NVDA"

# ATR Configuration
ATR_PERIOD = 14
LIQUIDITY_THRESHOLD = 0.25  # 25% of daily ATR

# POST Endpoint for signals
ENDPOINT_URL = "YOUR_ENDPOINT_URL"

# Trading Hours (EST)
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
INIT_HOUR = 9
INIT_MINUTE = 45
SESSION_END_HOUR = 11
SESSION_END_MINUTE = 0

# Scan Interval (minutes)
SCAN_INTERVAL_MINUTES = 5

# Timezone
TIMEZONE = "America/New_York"

# Pattern Recognition Thresholds
HAMMER_WICK_RATIO = 2.0  # Lower wick must be at least 2x body size
ENGULFING_BODY_OVERLAP = 1.0  # Current body must fully cover previous
