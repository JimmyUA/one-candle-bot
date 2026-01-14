"""
Alpaca Data Provider - Market Data via Alpaca API

Provides market data fetching using Alpaca's REST API.
Designed to be a drop-in replacement for yfinance data fetching.
"""

import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import pytz

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit


class AlpacaDataProvider:
    """
    Market data provider using Alpaca API.
    
    Provides the same interface as yfinance for fetching OHLCV data,
    allowing seamless switching between data sources.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        paper: bool = True
    ):
        """
        Initialize Alpaca data provider.
        
        Args:
            api_key: Alpaca API key. If None, reads from ALPACA_API_KEY env var.
            secret_key: Alpaca secret key. If None, reads from ALPACA_SECRET_KEY env var.
            paper: Use paper trading endpoint (default True for safety).
        """
        self.api_key = api_key or os.environ.get("ALPACA_API_KEY")
        self.secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY")
        self.paper = paper
        
        if not self.api_key or not self.secret_key:
            raise ValueError(
                "Alpaca API keys required. Set ALPACA_API_KEY and "
                "ALPACA_SECRET_KEY environment variables or pass them directly."
            )
        
        # Initialize the historical data client
        self.client = StockHistoricalDataClient(
            api_key=self.api_key,
            secret_key=self.secret_key
        )
        
        # Timezone for market hours
        self.tz = pytz.timezone("America/New_York")
    
    def _convert_interval_to_timeframe(self, interval: str) -> TimeFrame:
        """
        Convert interval string to Alpaca TimeFrame.
        
        Args:
            interval: Interval string ('1d', '15m', '5m', '1m')
            
        Returns:
            Alpaca TimeFrame object
        """
        interval_map = {
            '1d': TimeFrame.Day,
            '1D': TimeFrame.Day,
            '15m': TimeFrame(15, TimeFrameUnit.Minute),
            '15Min': TimeFrame(15, TimeFrameUnit.Minute),
            '5m': TimeFrame(5, TimeFrameUnit.Minute),
            '5Min': TimeFrame(5, TimeFrameUnit.Minute),
            '1m': TimeFrame.Minute,
            '1Min': TimeFrame.Minute,
        }
        
        if interval not in interval_map:
            raise ValueError(f"Unsupported interval: {interval}. Use '1d', '15m', '5m', or '1m'")
        
        return interval_map[interval]
    
    def _normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize Alpaca DataFrame to match yfinance column names.
        
        Alpaca returns lowercase column names, yfinance uses capitalized.
        This ensures compatibility with existing code.
        
        Args:
            df: Raw Alpaca DataFrame
            
        Returns:
            DataFrame with capitalized column names
        """
        # Alpaca columns: 'open', 'high', 'low', 'close', 'volume', 'trade_count', 'vwap'
        # yfinance columns: 'Open', 'High', 'Low', 'Close', 'Volume'
        
        column_map = {
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume',
        }
        
        # Rename columns to match yfinance format
        df = df.rename(columns=column_map)
        
        # Keep only the columns we need
        columns_to_keep = ['Open', 'High', 'Low', 'Close', 'Volume']
        df = df[[col for col in columns_to_keep if col in df.columns]]
        
        return df
    
    def fetch_daily_data(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """
        Fetch daily OHLCV data for ATR calculation.
        
        Args:
            symbol: Trading symbol (e.g., 'AAPL')
            days: Number of days to fetch (default 30 for 14-period ATR)
            
        Returns:
            DataFrame with daily OHLCV data (columns: Open, High, Low, Close, Volume)
        """
        end_date = datetime.now(self.tz)
        start_date = end_date - timedelta(days=days)
        
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start_date,
            end=end_date
        )
        
        bars = self.client.get_stock_bars(request)
        
        # Convert to DataFrame
        df = bars.df
        
        # Handle multi-index (symbol, timestamp) -> just timestamp
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(symbol, level='symbol')
        
        return self._normalize_dataframe(df)
    
    def fetch_intraday_data(
        self,
        symbol: str,
        interval: str = '15m',
        days: int = 1
    ) -> pd.DataFrame:
        """
        Fetch intraday OHLCV data.
        
        Args:
            symbol: Trading symbol (e.g., 'AAPL')
            interval: Candle interval ('15m', '5m', '1m')
            days: Number of days to fetch (default 1 for current day)
            
        Returns:
            DataFrame with intraday OHLCV data (columns: Open, High, Low, Close, Volume)
        """
        end_date = datetime.now(self.tz)
        start_date = end_date - timedelta(days=days)
        
        timeframe = self._convert_interval_to_timeframe(interval)
        
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=timeframe,
            start=start_date,
            end=end_date
        )
        
        bars = self.client.get_stock_bars(request)
        
        # Convert to DataFrame
        df = bars.df
        
        # Handle multi-index (symbol, timestamp) -> just timestamp
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(symbol, level='symbol')
        
        # Filter to today's data only for intraday
        if days == 1:
            today = datetime.now(self.tz).date()
            df = df[df.index.date == today]
        
        return self._normalize_dataframe(df)
