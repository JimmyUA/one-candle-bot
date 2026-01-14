"""
Test Alpaca Data Provider

Tests for the AlpacaDataProvider class.
Run with: python -m pytest test_alpaca_data_provider.py -v
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import datetime


class TestAlpacaDataProviderUnit:
    """Unit tests for AlpacaDataProvider (no API keys required)."""
    
    def test_init_without_keys_raises_error(self):
        """Test that initialization without API keys raises ValueError."""
        # Clear any environment variables
        with patch.dict(os.environ, {}, clear=True):
            # Remove keys if they exist
            env = os.environ.copy()
            env.pop('ALPACA_API_KEY', None)
            env.pop('ALPACA_SECRET_KEY', None)
            
            with patch.dict(os.environ, env, clear=True):
                from alpaca_data_provider import AlpacaDataProvider
                
                with pytest.raises(ValueError) as excinfo:
                    AlpacaDataProvider()
                
                assert "Alpaca API keys required" in str(excinfo.value)
    
    def test_interval_conversion(self):
        """Test interval string conversion to TimeFrame."""
        from alpaca_data_provider import AlpacaDataProvider
        from alpaca.data.timeframe import TimeFrame
        
        # Mock the client initialization
        with patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}):
            with patch('alpaca_data_provider.StockHistoricalDataClient'):
                provider = AlpacaDataProvider()
                
                # Test valid intervals
                assert provider._convert_interval_to_timeframe('1d') == TimeFrame.Day
                assert provider._convert_interval_to_timeframe('1D') == TimeFrame.Day
                assert provider._convert_interval_to_timeframe('1m') == TimeFrame.Minute
                
                # Test invalid interval
                with pytest.raises(ValueError):
                    provider._convert_interval_to_timeframe('invalid')
    
    def test_normalize_dataframe(self):
        """Test DataFrame column normalization from Alpaca to yfinance format."""
        from alpaca_data_provider import AlpacaDataProvider
        
        with patch.dict(os.environ, {'ALPACA_API_KEY': 'test', 'ALPACA_SECRET_KEY': 'test'}):
            with patch('alpaca_data_provider.StockHistoricalDataClient'):
                provider = AlpacaDataProvider()
                
                # Create mock Alpaca-style DataFrame
                mock_df = pd.DataFrame({
                    'open': [100.0, 101.0],
                    'high': [105.0, 106.0],
                    'low': [99.0, 100.0],
                    'close': [104.0, 105.0],
                    'volume': [1000000, 1100000],
                    'trade_count': [5000, 5500],
                    'vwap': [102.5, 103.0]
                })
                
                # Normalize
                result = provider._normalize_dataframe(mock_df)
                
                # Check column names are capitalized
                assert 'Open' in result.columns
                assert 'High' in result.columns
                assert 'Low' in result.columns
                assert 'Close' in result.columns
                assert 'Volume' in result.columns
                
                # Check extra columns are removed
                assert 'trade_count' not in result.columns
                assert 'vwap' not in result.columns
                
                # Check values
                assert result['Open'].iloc[0] == 100.0
                assert result['Close'].iloc[1] == 105.0


class TestAlpacaDataProviderIntegration:
    """Integration tests (require ALPACA_API_KEY and ALPACA_SECRET_KEY)."""
    
    @pytest.fixture
    def has_api_keys(self):
        """Check if API keys are available."""
        return (
            os.environ.get('ALPACA_API_KEY') and 
            os.environ.get('ALPACA_SECRET_KEY')
        )
    
    @pytest.mark.skipif(
        not os.environ.get('ALPACA_API_KEY'),
        reason="ALPACA_API_KEY not set"
    )
    def test_fetch_daily_data_live(self):
        """Test fetching daily data with real API keys."""
        from alpaca_data_provider import AlpacaDataProvider
        
        provider = AlpacaDataProvider(paper=True)
        df = provider.fetch_daily_data('AAPL', days=10)
        
        assert not df.empty
        assert 'Open' in df.columns
        assert 'High' in df.columns
        assert 'Low' in df.columns
        assert 'Close' in df.columns
        assert 'Volume' in df.columns
        assert len(df) > 0
    
    @pytest.mark.skipif(
        not os.environ.get('ALPACA_API_KEY'),
        reason="ALPACA_API_KEY not set"
    )
    def test_fetch_intraday_data_live(self):
        """Test fetching intraday data with real API keys."""
        from alpaca_data_provider import AlpacaDataProvider
        
        provider = AlpacaDataProvider(paper=True)
        df = provider.fetch_intraday_data('AAPL', interval='15m', days=2)
        
        assert 'Open' in df.columns
        assert 'High' in df.columns
        assert 'Low' in df.columns
        assert 'Close' in df.columns


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
