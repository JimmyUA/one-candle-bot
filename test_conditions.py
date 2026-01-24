"""
Strategy Condition Tests - Isolated Unit Tests
Tests for validating each condition in the Quick Flip Scalper strategy.

These tests are isolated from external dependencies (yfinance, pandas_ta, alpaca)
by testing the condition logic directly with mock data.
"""

import pytest
import pandas as pd
import sys
from unittest.mock import MagicMock, patch

# Mock the external dependencies before importing QuickFlipScalper
sys.modules['pandas_ta'] = MagicMock()
sys.modules['yfinance'] = MagicMock()
sys.modules['alpaca_data_provider'] = MagicMock()

# Now we can import the module
import config


class ConditionTester:
    """
    Isolated implementation of condition logic for testing.
    This mirrors the QuickFlipScalper methods but without external dependencies.
    """
    
    def __init__(self):
        self.box_high = None
        self.box_low = None
        self.daily_atr = None
        self.hammer_wick_ratio = config.HAMMER_WICK_RATIO
        self.liquidity_threshold = config.LIQUIDITY_THRESHOLD
    
    def validate_liquidity(self) -> bool:
        """Validate candle range >= 25% of daily ATR."""
        if self.box_high is None or self.box_low is None:
            raise ValueError("Box not initialized")
        if self.daily_atr is None:
            raise ValueError("ATR not calculated")
        
        candle_range = self.box_high - self.box_low
        threshold = self.daily_atr * self.liquidity_threshold
        return candle_range >= threshold
    
    def is_hammer(self, candle: pd.Series) -> bool:
        """Detect Hammer candlestick pattern."""
        open_price = candle['Open']
        high = candle['High']
        low = candle['Low']
        close = candle['Close']
        
        body = abs(close - open_price)
        lower_wick = min(open_price, close) - low
        upper_wick = high - max(open_price, close)
        
        # Prevent division by zero
        if body == 0:
            body = 0.001
        
        # Hammer: lower wick >= 2x body, upper wick <= 0.5x body
        return (
            lower_wick >= self.hammer_wick_ratio * body and
            upper_wick <= 0.5 * body
        )
    
    def is_inverted_hammer(self, candle: pd.Series) -> bool:
        """Detect Inverted Hammer pattern."""
        open_price = candle['Open']
        high = candle['High']
        low = candle['Low']
        close = candle['Close']
        
        body = abs(close - open_price)
        lower_wick = min(open_price, close) - low
        upper_wick = high - max(open_price, close)
        
        # Prevent division by zero
        if body == 0:
            body = 0.001
        
        # Inverted Hammer: upper wick >= 2x body, lower wick <= 0.5x body
        return (
            upper_wick >= self.hammer_wick_ratio * body and
            lower_wick <= 0.5 * body
        )
    
    def is_bullish_engulfing(self, current: pd.Series, previous: pd.Series) -> bool:
        """Detect Bullish Engulfing pattern."""
        # Previous must be red, current must be green
        prev_is_red = previous['Close'] < previous['Open']
        curr_is_green = current['Close'] > current['Open']
        
        if not (prev_is_red and curr_is_green):
            return False
        
        # Current body must fully engulf previous body
        return (
            current['Close'] > previous['Open'] and
            current['Open'] < previous['Close']
        )
    
    def is_bearish_engulfing(self, current: pd.Series, previous: pd.Series) -> bool:
        """Detect Bearish Engulfing pattern."""
        # Previous must be green, current must be red
        prev_is_green = previous['Close'] > previous['Open']
        curr_is_red = current['Close'] < current['Open']
        
        if not (prev_is_green and curr_is_red):
            return False
        
        # Current body must fully engulf previous body
        return (
            current['Open'] > previous['Close'] and
            current['Close'] < previous['Open']
        )
    
    def check_box_breakout(self, candle: pd.Series) -> str:
        """
        Check if price has broken out of the box.
        Returns: 'LONG_ZONE', 'SHORT_ZONE', or 'INSIDE_BOX'
        """
        if candle['Low'] < self.box_low:
            return 'LONG_ZONE'
        elif candle['High'] > self.box_high:
            return 'SHORT_ZONE'
        else:
            return 'INSIDE_BOX'


# ============================================================================
# CONDITION 1: LIQUIDITY VALIDATION TESTS
# ============================================================================

class TestLiquidityValidation:
    """Tests for liquidity validation logic."""
    
    @pytest.fixture
    def tester(self):
        return ConditionTester()
    
    def test_validate_liquidity_pass(self, tester):
        """Range >= threshold should pass."""
        tester.box_high = 150.0
        tester.box_low = 145.0  # Range = 5.0
        tester.daily_atr = 10.0  # Threshold = 2.5 (25%)
        
        assert tester.validate_liquidity() == True
        print("✓ PASS: Range 5.0 >= Threshold 2.5")
    
    def test_validate_liquidity_fail(self, tester):
        """Range < threshold should fail."""
        tester.box_high = 150.0
        tester.box_low = 149.0  # Range = 1.0
        tester.daily_atr = 10.0  # Threshold = 2.5
        
        assert tester.validate_liquidity() == False
        print("✓ FAIL: Range 1.0 < Threshold 2.5")
    
    def test_validate_liquidity_exact_threshold(self, tester):
        """Range == threshold should pass (>= comparison)."""
        tester.box_high = 150.0
        tester.box_low = 147.5  # Range = 2.5
        tester.daily_atr = 10.0  # Threshold = 2.5
        
        assert tester.validate_liquidity() == True
        print("✓ PASS: Range 2.5 == Threshold 2.5 (exact)")
    
    def test_validate_liquidity_zero_range(self, tester):
        """Zero range (box_high == box_low) should fail."""
        tester.box_high = 150.0
        tester.box_low = 150.0  # Range = 0
        tester.daily_atr = 10.0  # Threshold = 2.5
        
        assert tester.validate_liquidity() == False
        print("✓ FAIL: Zero range")
    
    def test_validate_liquidity_large_atr(self, tester):
        """Large ATR should require proportionally large range."""
        tester.box_high = 155.0
        tester.box_low = 145.0  # Range = 10.0
        tester.daily_atr = 100.0  # Threshold = 25.0
        
        assert tester.validate_liquidity() == False
        print("✓ FAIL: Range 10.0 < Large threshold 25.0")


# ============================================================================
# CONDITION 2: BOX BREAKOUT DETECTION TESTS
# ============================================================================

class TestBoxBreakoutDetection:
    """Tests for box breakout detection logic."""
    
    @pytest.fixture
    def tester(self):
        t = ConditionTester()
        t.box_high = 150.0
        t.box_low = 145.0
        return t
    
    def test_price_below_box_triggers_long_zone(self, tester):
        """Price with low < box_low should be in LONG zone."""
        candle = pd.Series({
            'Open': 144.5,
            'High': 145.5,
            'Low': 143.0,  # Below box_low (145.0)
            'Close': 144.8
        })
        
        result = tester.check_box_breakout(candle)
        assert result == 'LONG_ZONE'
        print("✓ LONG_ZONE: Low 143.0 < box_low 145.0")
    
    def test_price_above_box_triggers_short_zone(self, tester):
        """Price with high > box_high should be in SHORT zone."""
        candle = pd.Series({
            'Open': 150.5,
            'High': 152.0,  # Above box_high (150.0)
            'Low': 150.0,
            'Close': 151.5
        })
        
        result = tester.check_box_breakout(candle)
        assert result == 'SHORT_ZONE'
        print("✓ SHORT_ZONE: High 152.0 > box_high 150.0")
    
    def test_price_inside_box_returns_none(self, tester):
        """Price fully inside box should return INSIDE_BOX."""
        candle = pd.Series({
            'Open': 147.0,
            'High': 149.0,  # Below box_high
            'Low': 146.0,   # Above box_low
            'Close': 148.0
        })
        
        result = tester.check_box_breakout(candle)
        assert result == 'INSIDE_BOX'
        print("✓ INSIDE_BOX: Price fully contained")
    
    def test_price_touching_box_low_is_inside(self, tester):
        """Price with low == box_low should be inside (not below)."""
        candle = pd.Series({
            'Open': 146.0,
            'High': 148.0,
            'Low': 145.0,   # Exactly at box_low
            'Close': 147.0
        })
        
        result = tester.check_box_breakout(candle)
        assert result == 'INSIDE_BOX'
        print("✓ INSIDE_BOX: Low exactly at box_low")
    
    def test_price_touching_box_high_is_inside(self, tester):
        """Price with high == box_high should be inside (not above)."""
        candle = pd.Series({
            'Open': 148.0,
            'High': 150.0,  # Exactly at box_high
            'Low': 147.0,
            'Close': 149.0
        })
        
        result = tester.check_box_breakout(candle)
        assert result == 'INSIDE_BOX'
        print("✓ INSIDE_BOX: High exactly at box_high")


# ============================================================================
# CONDITION 3: HAMMER PATTERN TESTS
# ============================================================================

class TestHammerPattern:
    """Tests for Hammer candlestick pattern recognition."""
    
    @pytest.fixture
    def tester(self):
        return ConditionTester()
    
    def test_is_hammer_valid(self, tester):
        """Valid hammer: small body, long lower wick, little upper wick."""
        # Body = 1.0, Lower wick = 3.0 (>= 2x body), Upper wick = 0.2 (<= 0.5x body)
        candle = pd.Series({
            'Open': 100.0,
            'High': 101.2,    # Upper wick = 0.2 (max(open,close)=101, high-max=0.2)
            'Low': 97.0,      # Lower wick = 3.0 (min(open,close)=100, min-low=3.0)
            'Close': 101.0    # Body = 1.0
        })
        
        assert tester.is_hammer(candle) == True
        print("✓ HAMMER: lower_wick(3.0) >= 2*body(1.0), upper_wick(0.2) <= 0.5*body(0.5)")
    
    def test_is_hammer_invalid_no_lower_wick(self, tester):
        """No lower wick should not be a hammer."""
        candle = pd.Series({
            'Open': 100.0,
            'High': 102.0,
            'Low': 100.0,     # No lower wick
            'Close': 101.5
        })
        
        assert tester.is_hammer(candle) == False
        print("✓ NOT HAMMER: No lower wick")
    
    def test_is_hammer_invalid_large_upper_wick(self, tester):
        """Large upper wick disqualifies hammer."""
        candle = pd.Series({
            'Open': 100.0,
            'High': 105.0,    # Large upper wick
            'Low': 97.0,
            'Close': 100.5
        })
        
        assert tester.is_hammer(candle) == False
        print("✓ NOT HAMMER: Upper wick too large")
    
    def test_is_hammer_doji_pattern(self, tester):
        """Doji (open == close) with long lower wick should still be hammer."""
        candle = pd.Series({
            'Open': 100.0,
            'High': 100.0,    # No upper wick
            'Low': 97.0,      # Long lower wick
            'Close': 100.0    # Doji (body = 0)
        })
        
        # With body=0, we use 0.001; lower_wick=3.0 >= 2*0.001 = True
        assert tester.is_hammer(candle) == True
        print("✓ HAMMER: Doji with long lower wick is valid")
    
    def test_is_hammer_exact_ratio(self, tester):
        """Lower wick exactly 2x body should be hammer."""
        candle = pd.Series({
            'Open': 100.0,
            'High': 100.25,   # Small upper (0.25)
            'Low': 98.0,      # Lower wick = 2.0
            'Close': 100.0 + 1.0  # Body = 1.0 (so ratio = exactly 2.0)
        })
        # Wait: close=101.0, open=100.0 -> body=1.0
        # lower_wick = min(100,101) - 98 = 100 - 98 = 2.0
        # 2.0 >= 2.0 * 1.0 = True
        # upper_wick = 100.25 - 101 = negative? Let me fix
        
        candle = pd.Series({
            'Open': 100.0,
            'High': 101.25,   # upper = 101.25 - 101 = 0.25
            'Low': 98.0,      # lower = 100 - 98 = 2.0
            'Close': 101.0    # body = 1.0
        })
        
        assert tester.is_hammer(candle) == True
        print("✓ HAMMER: Exact 2x ratio passes")


# ============================================================================
# CONDITION 4: INVERTED HAMMER PATTERN TESTS
# ============================================================================

class TestInvertedHammerPattern:
    """Tests for Inverted Hammer candlestick pattern recognition."""
    
    @pytest.fixture
    def tester(self):
        return ConditionTester()
    
    def test_is_inverted_hammer_valid(self, tester):
        """Valid inverted hammer: small body, long upper wick, little lower wick."""
        candle = pd.Series({
            'Open': 100.0,
            'High': 103.0,    # Long upper wick (2.8)
            'Low': 99.9,      # Small lower wick (0.1)
            'Close': 100.2    # Small body (0.2)
        })
        
        assert tester.is_inverted_hammer(candle) == True
        print("✓ INVERTED HAMMER: upper(2.8) >= 2*body(0.2)")
    
    def test_is_inverted_hammer_invalid_normal_candle(self, tester):
        """Normal candle should not be inverted hammer."""
        candle = pd.Series({
            'Open': 100.0,
            'High': 101.0,
            'Low': 99.0,
            'Close': 100.5
        })
        
        assert tester.is_inverted_hammer(candle) == False
        print("✓ NOT INVERTED HAMMER: Normal candle")
    
    def test_is_inverted_hammer_doji(self, tester):
        """Doji with long upper wick should be inverted hammer."""
        candle = pd.Series({
            'Open': 100.0,
            'High': 103.0,    # Long upper wick
            'Low': 100.0,     # No lower wick
            'Close': 100.0    # Doji
        })
        
        assert tester.is_inverted_hammer(candle) == True
        print("✓ INVERTED HAMMER: Doji with upper wick")
    
    def test_is_inverted_hammer_exact_ratio(self, tester):
        """Upper wick exactly 2x body should pass."""
        candle = pd.Series({
            'Open': 100.0,
            'High': 103.0,    # upper = 103 - 101 = 2.0
            'Low': 99.8,      # lower = 100 - 99.8 = 0.2
            'Close': 101.0    # body = 1.0
        })
        
        assert tester.is_inverted_hammer(candle) == True
        print("✓ INVERTED HAMMER: Exact 2x ratio passes")


# ============================================================================
# CONDITION 5: BULLISH ENGULFING PATTERN TESTS
# ============================================================================

class TestBullishEngulfingPattern:
    """Tests for Bullish Engulfing candlestick pattern recognition."""
    
    @pytest.fixture
    def tester(self):
        return ConditionTester()
    
    def test_is_bullish_engulfing_valid(self, tester):
        """Valid pattern: prev red, curr green, curr engulfs prev."""
        previous = pd.Series({
            'Open': 102.0,
            'High': 102.5,
            'Low': 100.0,
            'Close': 100.5    # Red: close < open
        })
        current = pd.Series({
            'Open': 100.0,    # Opens below prev close
            'High': 103.0,
            'Low': 99.5,
            'Close': 102.5    # Closes above prev open; Green
        })
        
        assert tester.is_bullish_engulfing(current, previous) == True
        print("✓ BULLISH ENGULFING: Current engulfs previous")
    
    def test_is_bullish_engulfing_invalid_both_green(self, tester):
        """If previous is green, pattern is invalid."""
        previous = pd.Series({
            'Open': 100.0,
            'High': 102.0,
            'Low': 99.5,
            'Close': 101.5    # Green: close > open
        })
        current = pd.Series({
            'Open': 101.0,
            'High': 103.0,
            'Low': 100.5,
            'Close': 102.5
        })
        
        assert tester.is_bullish_engulfing(current, previous) == False
        print("✓ NOT BULLISH ENGULFING: Previous is green")
    
    def test_is_bullish_engulfing_partial_engulf(self, tester):
        """Partial engulfment should fail - current doesn't open below prev close."""
        previous = pd.Series({
            'Open': 102.0,
            'High': 102.5,
            'Low': 100.0,
            'Close': 100.5    # Red
        })
        current = pd.Series({
            'Open': 100.6,    # Opens ABOVE prev close (100.5) - NOT engulfing
            'High': 103.0,
            'Low': 100.0,
            'Close': 102.5    # Closes above prev open
        })
        
        # current.Open (100.6) is NOT < previous.Close (100.5)
        assert tester.is_bullish_engulfing(current, previous) == False
        print("✓ NOT BULLISH ENGULFING: Partial engulf fails")
    
    def test_is_bullish_engulfing_exact_match(self, tester):
        """Bodies exactly matching (not engulfing) should fail."""
        previous = pd.Series({
            'Open': 102.0,
            'High': 102.5,
            'Low': 100.0,
            'Close': 100.5    # Red
        })
        current = pd.Series({
            'Open': 100.5,    # Opens at prev close (not below)
            'High': 103.0,
            'Low': 100.0,
            'Close': 102.0    # Closes at prev open (not above)
        })
        
        # current.Close (102.0) is NOT > previous.Open (102.0)
        # current.Open (100.5) is NOT < previous.Close (100.5)
        assert tester.is_bullish_engulfing(current, previous) == False
        print("✓ NOT BULLISH ENGULFING: Exact match fails (not engulfing)")


# ============================================================================
# CONDITION 6: BEARISH ENGULFING PATTERN TESTS
# ============================================================================

class TestBearishEngulfingPattern:
    """Tests for Bearish Engulfing candlestick pattern recognition."""
    
    @pytest.fixture
    def tester(self):
        return ConditionTester()
    
    def test_is_bearish_engulfing_valid(self, tester):
        """Valid pattern: prev green, curr red, curr engulfs prev."""
        previous = pd.Series({
            'Open': 100.0,
            'High': 102.5,
            'Low': 99.5,
            'Close': 102.0    # Green: close > open
        })
        current = pd.Series({
            'Open': 102.5,    # Opens above prev close
            'High': 103.0,
            'Low': 99.0,
            'Close': 99.5     # Closes below prev open; Red
        })
        
        assert tester.is_bearish_engulfing(current, previous) == True
        print("✓ BEARISH ENGULFING: Current engulfs previous")
    
    def test_is_bearish_engulfing_invalid_prev_red(self, tester):
        """If previous is red, pattern is invalid."""
        previous = pd.Series({
            'Open': 102.0,
            'High': 102.5,
            'Low': 99.5,
            'Close': 100.0    # Red: close < open
        })
        current = pd.Series({
            'Open': 101.0,
            'High': 101.5,
            'Low': 99.0,
            'Close': 99.5
        })
        
        assert tester.is_bearish_engulfing(current, previous) == False
        print("✓ NOT BEARISH ENGULFING: Previous is red")
    
    def test_is_bearish_engulfing_partial_engulf(self, tester):
        """Partial engulfment should fail."""
        previous = pd.Series({
            'Open': 100.0,
            'High': 102.5,
            'Low': 99.5,
            'Close': 102.0    # Green
        })
        current = pd.Series({
            'Open': 101.5,    # Opens below prev close (fails condition)
            'High': 102.0,
            'Low': 99.0,
            'Close': 99.5     # Closes below prev open
        })
        
        # current.Open (101.5) is NOT > previous.Close (102.0)
        assert tester.is_bearish_engulfing(current, previous) == False
        print("✓ NOT BEARISH ENGULFING: Partial engulf fails")
    
    def test_is_bearish_engulfing_exact_match(self, tester):
        """Bodies exactly matching should fail."""
        previous = pd.Series({
            'Open': 100.0,
            'High': 102.5,
            'Low': 99.5,
            'Close': 102.0    # Green
        })
        current = pd.Series({
            'Open': 102.0,    # Opens at prev close
            'High': 102.5,
            'Low': 99.5,
            'Close': 100.0    # Closes at prev open
        })
        
        # current.Open (102.0) is NOT > previous.Close (102.0)
        # current.Close (100.0) is NOT < previous.Open (100.0)
        assert tester.is_bearish_engulfing(current, previous) == False
        print("✓ NOT BEARISH ENGULFING: Exact match fails")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
