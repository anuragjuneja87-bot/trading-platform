#!/usr/bin/env python3
"""
Test Script for ThetaData v3 Integration
Tests the complete options data pipeline
"""

import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

print("=" * 70)
print("THETADATA V3 INTEGRATION TEST")
print("=" * 70)
print()

# Test 1: Import ThetaData v3 Client
print("TEST 1: Import ThetaData v3 Client")
print("-" * 70)
try:
    from analyzers.thetadata_client_v3 import ThetaDataClientV3
    print("✅ ThetaData v3 client imported successfully")
except Exception as e:
    print(f"❌ Failed to import: {e}")
    sys.exit(1)

print()

# Test 2: Initialize Client
print("TEST 2: Initialize Client")
print("-" * 70)
try:
    client = ThetaDataClientV3(cache_seconds=60)
    print("✅ Client initialized")
except Exception as e:
    print(f"❌ Failed to initialize: {e}")
    sys.exit(1)

print()

# Test 3: Get Expirations
print("TEST 3: Get Expirations for SPY")
print("-" * 70)
try:
    expirations = client.get_expirations('SPY')
    if expirations:
        print(f"✅ Got {len(expirations)} expirations")
        print(f"   Sample: {expirations[:5]}")
    else:
        print("⚠️  No expirations returned")
except Exception as e:
    print(f"❌ Error: {e}")

print()

# Test 4: Get Complete Options Chain
print("TEST 4: Get Complete Options Chain (SPY)")
print("-" * 70)
try:
    from datetime import datetime
    import pytz
    
    et_tz = pytz.timezone('America/New_York')
    today = datetime.now(et_tz).date().strftime('%Y-%m-%d')
    
    # Try today first (0DTE)
    exp_date = today if today in expirations else expirations[0] if expirations else today
    
    print(f"   Using expiration: {exp_date}")
    print(f"   Current SPY price: ~$580 (for filtering)")
    
    chain = client.get_complete_options_chain('SPY', exp_date, 580.0)
    
    print(f"\n✅ Retrieved options chain:")
    print(f"   • Strikes before filter: {chain['strikes_before_filter']}")
    print(f"   • Strikes after filter: {chain['strikes_after_filter']}")
    print(f"   • Call options: {len(chain['calls'])}")
    print(f"   • Put options: {len(chain['puts'])}")
    
    if chain['calls']:
        sample_call = chain['calls'][0]
        print(f"\n   Sample Call Strike ${sample_call['strike']}:")
        print(f"   • Delta: {sample_call.get('delta', 'N/A')}")
        print(f"   • Gamma: {sample_call.get('gamma', 'N/A')}")
        print(f"   • OI: {sample_call.get('open_interest', 'N/A')}")
        print(f"   • Volume: {sample_call.get('volume', 'N/A')}")
        print(f"   • Bid/Ask: ${sample_call.get('bid', 0):.2f} / ${sample_call.get('ask', 0):.2f}")
        print(f"   • IV: {sample_call.get('implied_vol', 0):.4f}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 5: Client Statistics
print("TEST 5: Client Statistics")
print("-" * 70)
try:
    stats = client.get_stats()
    print(f"✅ API Calls: {stats['api_calls']}")
    print(f"✅ Cache Hits: {stats['cache_hits']}")
    print(f"✅ Cache Hit Rate: {stats['cache_hit_rate']:.1f}%")
    print(f"✅ Cache Size: {stats['cache_size']} entries")
    print(f"✅ Errors: {stats['errors']}")
except Exception as e:
    print(f"❌ Error: {e}")

print()

# Test 6: Test Analyzer Integration
print("TEST 6: Test Analyzer Integration")
print("-" * 70)
try:
    from analyzers.enhanced_professional_analyzer import EnhancedProfessionalAnalyzer
    
    # Initialize with dummy keys (won't use Polygon)
    analyzer = EnhancedProfessionalAnalyzer(
        polygon_api_key='dummy_key_for_testing'
    )
    
    print("✅ Analyzer initialized")
    
    # Test get_options_chain
    print("\n   Testing analyzer.get_options_chain('SPY', 580.0)...")
    options = analyzer.get_options_chain('SPY', 580.0)
    
    if options:
        print(f"✅ Got {len(options)} options from analyzer")
        
        calls = [o for o in options if o['option_type'] == 'call']
        puts = [o for o in options if o['option_type'] == 'put']
        
        print(f"   • Calls: {len(calls)}")
        print(f"   • Puts: {len(puts)}")
        
        if calls:
            sample = calls[0]
            print(f"\n   Sample option data structure:")
            print(f"   • Strike: ${sample['strike']}")
            print(f"   • OI: {sample.get('open_interest', 'N/A')}")
            print(f"   • Volume: {sample.get('volume', 'N/A')}")
            print(f"   • Delta: {sample.get('delta', 'N/A')}")
            print(f"   • Gamma: {sample.get('gamma', 'N/A')}")
    else:
        print("⚠️  No options returned from analyzer")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 7: Performance Test
print("TEST 7: Performance Test (7 symbols)")
print("-" * 70)
try:
    import time
    
    symbols = ['SPY', 'QQQ', 'AAPL', 'NVDA', 'TSLA', 'PLTR', 'ORCL']
    
    start_time = time.time()
    
    for symbol in symbols:
        try:
            options = analyzer.get_options_chain(symbol, None)
            print(f"   • {symbol}: {len(options)} options")
        except Exception as e:
            print(f"   • {symbol}: Error - {str(e)[:50]}")
    
    elapsed = time.time() - start_time
    
    print(f"\n✅ Processed {len(symbols)} symbols in {elapsed:.2f} seconds")
    print(f"   • Average: {elapsed/len(symbols):.2f} seconds per symbol")
    
    # Show cache stats
    stats = client.get_stats()
    print(f"\n   Cache Performance:")
    print(f"   • API Calls: {stats['api_calls']}")
    print(f"   • Cache Hits: {stats['cache_hits']}")
    print(f"   • Hit Rate: {stats['cache_hit_rate']:.1f}%")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)
print()

# Summary
print("SUMMARY:")
print("-" * 70)
print("✅ If all tests passed, your ThetaData v3 integration is ready!")
print()
print("Next steps:")
print("  1. Copy files to backend/analyzers/:")
print("     • thetadata_client_v3.py")
print("     • enhanced_professional_analyzer.py (updated)")
print()
print("  2. Restart your Flask app:")
print("     python3 app.py")
print()
print("  3. Monitor logs for:")
print("     ✅ ThetaData v3 client initialized (60s cache)")
print("     ✅ Using IV-based strike filtering")
print()
print("  4. Test wall strength monitor:")
print("     Should see gamma walls with full OI/Volume data")
print()
print("=" * 70)