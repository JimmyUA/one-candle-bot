"""
Quick Flip Scalper - Unit Tests
Tests for pattern recognition and trade calculation logic.
"""

import pytest
import pandas as pd
from quick_flip_scalper import QuickFlipScalper
import config


class TestPatternRecognition:
    """Tests for candlestick pattern recognition."""
    
    @pytest.fixture
    def scalper(self):
        """Create a scalper instance with mock box values."""
        s = QuickFlipScalper(symbol='TEST')
        s.box_high = 150.0
        s.box_low = 145.0
        s.daily_atr = 5.0
        return s
    
    def test_is_hammer_valid(self, scalper):
        """Test hammer pattern detection with valid hammer candle."""
        # Hammer: small body, long lower wick, little upper wick
        candle = pd.Series({
            'Open': 100.0,
            'High': 100.5,
            'Low': 97.0,      # Long lower wick (3.0)
            'Close': 100.2,   # Small body (0.2)
            'Volume': 1000
        })
        
        assert scalper.is_hammer(candle) is True
    
    def test_is_hammer_invalid_no_wick(self, scalper):
        """Test hammer detection rejects candle without lower wick."""
        candle = pd.Series({
            'Open': 100.0,
            'High': 102.0,
            'Low': 100.0,     # No lower wick
            'Close': 101.5,
            'Volume': 1000
        })
        
        assert scalper.is_hammer(candle) is False
    
    def test_is_hammer_invalid_large_upper_wick(self, scalper):
        """Test hammer detection rejects candle with large upper wick."""
        candle = pd.Series({
            'Open': 100.0,
            'High': 105.0,    # Large upper wick (4.5)
            'Low': 97.0,
            'Close': 100.5,
            'Volume': 1000
        })
        
        assert scalper.is_hammer(candle) is False
    
    def test_is_inverted_hammer_valid(self, scalper):
        """Test inverted hammer pattern detection."""
        candle = pd.Series({
            'Open': 100.0,
            'High': 103.0,    # Long upper wick (2.8)
            'Low': 99.9,      # Little lower wick (0.1)
            'Close': 100.2,   # Small body (0.2)
            'Volume': 1000
        })
        
        assert scalper.is_inverted_hammer(candle) is True
    
    def test_is_inverted_hammer_invalid(self, scalper):
        """Test inverted hammer rejects normal candle."""
        candle = pd.Series({
            'Open': 100.0,
            'High': 101.0,
            'Low': 99.0,
            'Close': 100.5,
            'Volume': 1000
        })
        
        assert scalper.is_inverted_hammer(candle) is False
    
    def test_is_bullish_engulfing_valid(self, scalper):
        """Test bullish engulfing pattern detection."""
        previous = pd.Series({
            'Open': 102.0,
            'High': 102.5,
            'Low': 100.0,
            'Close': 100.5,   # Red candle (Close < Open)
            'Volume': 1000
        })
        
        current = pd.Series({
            'Open': 100.0,    # Opens below previous close
            'High': 103.0,
            'Low': 99.5,
            'Close': 102.5,   # Closes above previous open
            'Volume': 1500
        })
        
        assert scalper.is_bullish_engulfing(current, previous) is True
    
    def test_is_bullish_engulfing_invalid_both_green(self, scalper):
        """Test bullish engulfing rejects when previous is green."""
        previous = pd.Series({
            'Open': 100.0,
            'High': 102.0,
            'Low': 99.5,
            'Close': 101.5,   # Green candle (Close > Open)
            'Volume': 1000
        })
        
        current = pd.Series({
            'Open': 101.0,
            'High': 103.0,
            'Low': 100.5,
            'Close': 102.5,
            'Volume': 1500
        })
        
        assert scalper.is_bullish_engulfing(current, previous) is False
    
    def test_is_bearish_engulfing_valid(self, scalper):
        """Test bearish engulfing pattern detection."""
        previous = pd.Series({
            'Open': 100.0,
            'High': 102.5,
            'Low': 99.5,
            'Close': 102.0,   # Green candle (Close > Open)
            'Volume': 1000
        })
        
        current = pd.Series({
            'Open': 102.5,    # Opens above previous close
            'High': 103.0,
            'Low': 99.0,
            'Close': 99.5,    # Closes below previous open
            'Volume': 1500
        })
        
        assert scalper.is_bearish_engulfing(current, previous) is True
    
    def test_is_bearish_engulfing_invalid(self, scalper):
        """Test bearish engulfing rejects when previous is red."""
        previous = pd.Series({
            'Open': 102.0,
            'High': 102.5,
            'Low': 99.5,
            'Close': 100.0,   # Red candle
            'Volume': 1000
        })
        
        current = pd.Series({
            'Open': 101.0,
            'High': 101.5,
            'Low': 99.0,
            'Close': 99.5,
            'Volume': 1500
        })
        
        assert scalper.is_bearish_engulfing(current, previous) is False


class TestTradeCalculation:
    """Tests for trade parameter calculation."""
    
    @pytest.fixture
    def scalper(self):
        """Create a scalper instance with mock box values."""
        s = QuickFlipScalper(symbol='TEST')
        s.box_high = 150.0
        s.box_low = 145.0
        s.daily_atr = 5.0
        return s
    
    def test_calculate_trade_params_long_hammer(self, scalper):
        """Test trade params calculation for LONG hammer entry."""
        current = pd.Series({
            'Open': 144.0,
            'High': 144.5,
            'Low': 143.0,
            'Close': 144.2,
            'Volume': 1000
        })
        
        params = scalper.calculate_trade_params('hammer', 'LONG', current)
        
        assert params['entry_price'] == 144.5   # Current high
        assert params['stop_loss'] == 143.0      # Current low
        assert params['target_price'] == 150.0   # Box high
    
    def test_calculate_trade_params_long_engulfing(self, scalper):
        """Test trade params calculation for LONG bullish engulfing."""
        previous = pd.Series({
            'Open': 144.5,
            'High': 145.0,
            'Low': 143.5,
            'Close': 143.8,
            'Volume': 1000
        })
        
        current = pd.Series({
            'Open': 143.5,
            'High': 145.5,
            'Low': 143.0,
            'Close': 145.2,
            'Volume': 1500
        })
        
        params = scalper.calculate_trade_params('bullish_engulfing', 'LONG', current, previous)
        
        assert params['entry_price'] == 145.0   # Previous high
        assert params['stop_loss'] == 143.0      # Min of both lows
        assert params['target_price'] == 150.0   # Box high
    
    def test_calculate_trade_params_short_inverted_hammer(self, scalper):
        """Test trade params calculation for SHORT inverted hammer."""
        current = pd.Series({
            'Open': 151.0,
            'High': 152.5,
            'Low': 150.8,
            'Close': 151.2,
            'Volume': 1000
        })
        
        params = scalper.calculate_trade_params('inverted_hammer', 'SHORT', current)
        
        assert params['entry_price'] == 150.8   # Current low
        assert params['stop_loss'] == 152.5      # Current high
        assert params['target_price'] == 145.0   # Box low
    
    def test_calculate_trade_params_short_engulfing(self, scalper):
        """Test trade params calculation for SHORT bearish engulfing."""
        previous = pd.Series({
            'Open': 150.5,
            'High': 151.5,
            'Low': 150.0,
            'Close': 151.2,
            'Volume': 1000
        })
        
        current = pd.Series({
            'Open': 151.5,
            'High': 152.0,
            'Low': 150.0,
            'Close': 150.2,
            'Volume': 1500
        })
        
        params = scalper.calculate_trade_params('bearish_engulfing', 'SHORT', current, previous)
        
        assert params['entry_price'] == 150.0   # Previous low
        assert params['stop_loss'] == 152.0      # Max of both highs
        assert params['target_price'] == 145.0   # Box low


class TestLiquidityValidation:
    """Tests for liquidity validation logic."""
    
    def test_validate_liquidity_pass(self):
        """Test liquidity validation passes when range >= threshold."""
        s = QuickFlipScalper(symbol='TEST')
        s.box_high = 150.0
        s.box_low = 145.0  # Range = 5.0
        s.daily_atr = 10.0  # Threshold = 2.5 (25%)
        
        assert s.validate_liquidity() is True
    
    def test_validate_liquidity_fail(self):
        """Test liquidity validation fails when range < threshold."""
        s = QuickFlipScalper(symbol='TEST')
        s.box_high = 150.0
        s.box_low = 149.0  # Range = 1.0
        s.daily_atr = 10.0  # Threshold = 2.5 (25%)
        
        assert s.validate_liquidity() is False
    
    def test_validate_liquidity_exact_threshold(self):
        """Test liquidity validation passes at exact threshold."""
        s = QuickFlipScalper(symbol='TEST')
        s.box_high = 150.0
        s.box_low = 147.5  # Range = 2.5
        s.daily_atr = 10.0  # Threshold = 2.5 (25%)
        
        assert s.validate_liquidity() is True


class TestSignalPayload:
    """Tests for signal payload creation."""
    
    def test_create_signal_payload_long(self):
        """Test signal payload creation for LONG signal."""
        s = QuickFlipScalper(symbol='NVDA')
        s.box_high = 150.0
        s.box_low = 145.0
        s.daily_atr = 5.0
        
        params = {
            'entry_price': 144.5,
            'stop_loss': 143.0,
            'target_price': 150.0
        }
        
        payload = s._create_signal_payload('LONG', params, 'hammer')
        
        assert payload['asset_code'] == 'NVDA'
        assert payload['signal_type'] == 'LONG'
        assert payload['entry_price'] == 144.5
        assert payload['target_price'] == 150.0
        assert payload['stop_loss_price'] == 143.0
        assert payload['pattern'] == 'hammer'
        assert payload['box_high'] == 150.0
        assert payload['box_low'] == 145.0
        assert 'timestamp' in payload


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
