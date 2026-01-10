"""
Quick Flip Scalper - Main Entry Point
CLI tool for running the Quick Flip Scalper trading bot.
"""

import argparse
import time
import schedule
from datetime import datetime
import pytz

from quick_flip_scalper import QuickFlipScalper
import config


def run_initialization(scalper: QuickFlipScalper) -> bool:
    """
    Run the initialization phase at 09:45 EST.
    
    Args:
        scalper: QuickFlipScalper instance
        
    Returns:
        True if initialization successful and liquidity validated
    """
    print("\n" + "="*50)
    print("INITIALIZATION PHASE")
    print("="*50)
    
    try:
        # Calculate daily ATR
        atr = scalper.calculate_atr()
        print(f"Daily ATR (14-period): {atr:.2f}")
        
        # Initialize box from first 15m candle
        box_high, box_low = scalper.initialize_box()
        print(f"Box High: {box_high:.2f}")
        print(f"Box Low: {box_low:.2f}")
        print(f"Box Range: {box_high - box_low:.2f}")
        
        # Validate liquidity
        if scalper.validate_liquidity():
            threshold = atr * config.LIQUIDITY_THRESHOLD
            print(f"✓ Liquidity validated (Range >= {threshold:.2f})")
            return True
        else:
            threshold = atr * config.LIQUIDITY_THRESHOLD
            print(f"✗ Insufficient liquidity (Range < {threshold:.2f})")
            print("No trading today - exiting.")
            return False
            
    except Exception as e:
        print(f"Error during initialization: {e}")
        return False


def run_scan(scalper: QuickFlipScalper):
    """
    Run a single scan iteration.
    
    Args:
        scalper: QuickFlipScalper instance
    """
    if scalper.signal_sent:
        print("Signal already sent this session - skipping scan")
        return
    
    tz = pytz.timezone(config.TIMEZONE)
    now = datetime.now(tz)
    print(f"\n[{now.strftime('%H:%M:%S')}] Scanning for signals...")
    
    try:
        signal = scalper.scan_for_signals()
        
        if signal:
            print(f"🎯 SIGNAL: {signal['signal_type']} {signal['asset_code']}")
            print(f"   Pattern: {signal['pattern']}")
            print(f"   Entry: ${signal['entry_price']}")
            print(f"   Target: ${signal['target_price']}")
            print(f"   Stop: ${signal['stop_loss_price']}")
            
            scalper.send_signal(signal)
        else:
            print("   No pattern detected")
            
    except Exception as e:
        print(f"Error during scan: {e}")


def run_scan_loop(scalper: QuickFlipScalper):
    """
    Run the main scanning loop from 09:45 to 11:00 EST.
    
    Args:
        scalper: QuickFlipScalper instance
    """
    print("\n" + "="*50)
    print("SCAN LOOP")
    print(f"Scanning every {config.SCAN_INTERVAL_MINUTES} minutes until 11:00 EST")
    print("="*50)
    
    tz = pytz.timezone(config.TIMEZONE)
    
    while True:
        now = datetime.now(tz)
        
        # Check if we're past the session end
        session_end = now.replace(
            hour=config.SESSION_END_HOUR,
            minute=config.SESSION_END_MINUTE,
            second=0,
            microsecond=0
        )
        
        if now >= session_end:
            print("\n" + "="*50)
            print("SESSION ENDED - 11:00 EST")
            print("="*50)
            break
        
        # Check if signal already sent
        if scalper.signal_sent:
            print("\nSignal sent - stopping scan loop")
            break
        
        # Run scan
        run_scan(scalper)
        
        # Wait for next interval
        sleep_seconds = config.SCAN_INTERVAL_MINUTES * 60
        print(f"   Sleeping for {config.SCAN_INTERVAL_MINUTES} minutes...")
        time.sleep(sleep_seconds)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Quick Flip Scalper - Intraday Trading Bot'
    )
    parser.add_argument(
        '--symbol',
        type=str,
        default=config.SYMBOL,
        help=f'Trading symbol (default: {config.SYMBOL})'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without sending signals to endpoint'
    )
    parser.add_argument(
        '--immediate',
        action='store_true',
        help='Run immediately without waiting for market hours'
    )
    
    args = parser.parse_args()
    
    print("="*50)
    print("QUICK FLIP SCALPER")
    print("="*50)
    print(f"Symbol: {args.symbol}")
    print(f"ATR Period: {config.ATR_PERIOD}")
    print(f"Liquidity Threshold: {config.LIQUIDITY_THRESHOLD * 100}%")
    print(f"Scan Interval: {config.SCAN_INTERVAL_MINUTES} minutes")
    print(f"Dry Run: {args.dry_run}")
    print(f"Immediate: {args.immediate}")
    
    # Create scalper instance
    scalper = QuickFlipScalper(symbol=args.symbol)
    
    if args.dry_run:
        # Override send_signal to just print
        original_send = scalper.send_signal
        def dry_send(payload):
            print(f"[DRY RUN] Would send signal: {payload}")
            scalper.signal_sent = True
            return True
        scalper.send_signal = dry_send
    
    if args.immediate:
        # Run immediately without time checks
        print("\n[IMMEDIATE MODE] Running now...")
        if run_initialization(scalper):
            run_scan_loop(scalper)
    else:
        # Wait for market hours
        tz = pytz.timezone(config.TIMEZONE)
        now = datetime.now(tz)
        
        init_time = now.replace(
            hour=config.INIT_HOUR,
            minute=config.INIT_MINUTE,
            second=0,
            microsecond=0
        )
        
        if now < init_time:
            wait_seconds = (init_time - now).total_seconds()
            print(f"\nWaiting for 09:45 EST... ({wait_seconds/60:.1f} minutes)")
            time.sleep(wait_seconds)
        
        if now >= init_time:
            if run_initialization(scalper):
                run_scan_loop(scalper)
        else:
            print("Market hours have passed for today. Run with --immediate for testing.")


if __name__ == '__main__':
    main()
