"""
Monitor Diagnostic - Test each monitor individually
"""

import sys
import os
from datetime import datetime

sys.path.append('/Users/anu.juneja/Desktop/trading-platform/backend')

from dotenv import load_dotenv
load_dotenv()

print("=" * 80)
print("MONITOR DIAGNOSTIC TEST")
print("=" * 80)
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}")
print()

# Test 1: Volume Spike Monitor
print("TEST 1: Volume Spike Monitor")
print("-" * 80)
try:
    from monitors.volume_spike_monitor import VolumeSpikeMonitor
    
    polygon_key = os.getenv('POLYGON_API_KEY')
    discord_webhook = os.getenv('DISCORD_WEBHOOK_VOLUME_SPIKE')
    
    print(f"Polygon API Key: {'✓ Found' if polygon_key else '✗ Missing'}")
    print(f"Discord Webhook: {'✓ Found' if discord_webhook else '✗ Missing'}")
    
    if polygon_key:
        monitor = VolumeSpikeMonitor(polygon_api_key=polygon_key, discord_webhook=discord_webhook)
        print("✓ Monitor initialized")
        
        # Test TSLA
        print("\nTesting TSLA...")
        result = monitor.check_symbol('TSLA')
        print(f"Result: {result}")
    else:
        print("✗ Cannot initialize - missing API key")
        
except Exception as e:
    print(f"✗ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n")

# Test 2: Dark Pool Monitor
print("TEST 2: Dark Pool Monitor")
print("-" * 80)
try:
    from monitors.dark_pool_monitor import DarkPoolMonitor
    
    polygon_key = os.getenv('POLYGON_API_KEY')
    discord_webhook = os.getenv('DISCORD_WEBHOOK_DARK_POOL')
    
    print(f"Polygon API Key: {'✓ Found' if polygon_key else '✗ Missing'}")
    print(f"Discord Webhook: {'✓ Found' if discord_webhook else '✗ Missing'}")
    
    if polygon_key:
        monitor = DarkPoolMonitor(polygon_api_key=polygon_key, discord_webhook=discord_webhook)
        print("✓ Monitor initialized")
        
        # Test TSLA
        print("\nTesting TSLA...")
        result = monitor.check_symbol('TSLA')
        print(f"Result: {result}")
    else:
        print("✗ Cannot initialize - missing API key")
        
except Exception as e:
    print(f"✗ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n")

# Test 3: RVOL Monitor
print("TEST 3: Pre-Market RVOL Monitor")
print("-" * 80)
try:
    from monitors.premarket_rvol_monitor import PreMarketRVOLMonitor
    
    polygon_key = os.getenv('POLYGON_API_KEY')
    discord_webhook = os.getenv('DISCORD_WEBHOOK_PREMARKET')
    
    print(f"Polygon API Key: {'✓ Found' if polygon_key else '✗ Missing'}")
    print(f"Discord Webhook: {'✓ Found' if discord_webhook else '✗ Missing'}")
    
    if polygon_key:
        monitor = PreMarketRVOLMonitor(polygon_api_key=polygon_key, discord_webhook=discord_webhook)
        print("✓ Monitor initialized")
        
        # Test TSLA
        print("\nTesting TSLA...")
        result = monitor.check_symbol('TSLA')
        print(f"Result: {result}")
    else:
        print("✗ Cannot initialize - missing API key")
        
except Exception as e:
    print(f"✗ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n")

# Test 4: Check if monitors are running in app.py
print("TEST 4: Check Monitor Status in app.py")
print("-" * 80)
try:
    # Check running processes
    import subprocess
    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
    
    monitors_running = []
    for line in result.stdout.split('\n'):
        if 'python' in line.lower() and 'monitor' in line.lower():
            monitors_running.append(line)
    
    if monitors_running:
        print("✓ Found monitor processes:")
        for m in monitors_running:
            print(f"  {m}")
    else:
        print("⚠ No monitor processes found running separately")
        print("  (This is OK if monitors run as threads in app.py)")
        
except Exception as e:
    print(f"✗ ERROR: {e}")

print("\n")

# Test 5: Check watchlist
print("TEST 5: Check Watchlist")
print("-" * 80)
try:
    from watchlist_manager import WatchlistManager
    
    wm = WatchlistManager()
    symbols = wm.load_symbols()
    
    print(f"Total symbols: {len(symbols)}")
    print(f"Symbols: {', '.join(symbols)}")
    
    if 'TSLA' in symbols:
        print("✓ TSLA is in watchlist")
    else:
        print("✗ TSLA NOT in watchlist - this is why no alerts!")
        
except Exception as e:
    print(f"✗ ERROR: {e}")

print("\n")
print("=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
