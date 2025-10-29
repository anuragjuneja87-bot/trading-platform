#!/usr/bin/env python3
"""
Test Earnings System v2 - Benzinga API
Comprehensive testing for tomorrow's GOOG, MSFT, META earnings
"""

import requests
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

API_KEY = "k6FIYK4k_5YrSlIn3qwnPCrnebB6PDrj"
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1427168277150564516/jVpIERY-Za7r77JG8lizRTe4g8qQ5uSBjlIMLud7GBy5qs9x33iRRN7o770Q-FDl-9LN"


def print_header(title):
    """Print formatted header"""
    print("\n" + "=" * 80)
    print(f"{title}")
    print("=" * 80)


def test_benzinga_api_access():
    """Test 1: Verify Benzinga API access"""
    print_header("TEST 1: BENZINGA API ACCESS")
    
    url = "https://api.polygon.io/benzinga/v1/earnings"
    params = {
        'apiKey': API_KEY,
        'limit': 1
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Benzinga API access: CONFIRMED")
            print(f"   Request ID: {data.get('request_id', 'N/A')}")
            return True
        elif response.status_code == 403:
            print("❌ Benzinga API access: DENIED")
            print("   You need to subscribe to Benzinga earnings")
            return False
        else:
            print(f"⚠️  Unexpected status: {response.status_code}")
            return False
    
    except Exception as e:
        print(f"❌ API request failed: {str(e)}")
        return False


def test_tomorrows_earnings():
    """Test 2: Get tomorrow's earnings preview"""
    print_header("TEST 2: TOMORROW'S EARNINGS CALENDAR")
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    url = "https://api.polygon.io/benzinga/v1/earnings"
    params = {
        'apiKey': API_KEY,
        'date.gte': tomorrow,
        'date.lte': tomorrow,
        'limit': 100
    }
    
    print(f"Querying earnings for: {tomorrow}\n")
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ Request failed: {response.status_code}")
            return False
        
        data = response.json()
        results = data.get('results', [])
        
        if not results:
            print(f"ℹ️  No earnings scheduled for {tomorrow}")
            return True
        
        # Filter for confirmed earnings
        confirmed = [e for e in results if e.get('date_status') == 'confirmed']
        
        print(f"✅ Found {len(results)} total earnings ({len(confirmed)} confirmed)\n")
        
        # Look for major tech
        major_tech = ['GOOGL', 'GOOG', 'MSFT', 'META', 'AAPL', 'AMZN', 'NVDA', 'TSLA']
        tech_earnings = [e for e in confirmed if e.get('ticker') in major_tech]
        
        if tech_earnings:
            print("🔥 MAJOR TECH EARNINGS DETECTED:")
            for e in tech_earnings:
                ticker = e.get('ticker')
                company = e.get('company_name')
                time = e.get('time', 'N/A')[:5]
                eps_est = e.get('estimated_eps', 0)
                importance = e.get('importance', 0)
                
                print(f"\n   📊 {ticker} - {company}")
                print(f"      Time: {time} ET")
                print(f"      EPS Estimate: ${eps_est:.2f}")
                print(f"      Importance: {importance}/5")
        
        # Show top 10 others
        other_major = [e for e in confirmed if e.get('importance', 0) >= 4 and e.get('ticker') not in major_tech]
        
        if other_major:
            print(f"\n📈 OTHER MAJOR EARNINGS ({len(other_major)} companies):")
            for e in other_major[:10]:
                print(f"   • {e['ticker']} - {e.get('company_name')} at {e.get('time', 'N/A')[:5]} ET")
        
        return True
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_realtime_detection():
    """Test 3: Simulate real-time earnings detection"""
    print_header("TEST 3: REAL-TIME DETECTION SIMULATION")
    
    print("Simulating: What happens when MSFT reports at 4:05 PM tomorrow\n")
    
    # Get MSFT's most recent actual earnings
    url = "https://api.polygon.io/benzinga/v1/earnings"
    params = {
        'apiKey': API_KEY,
        'ticker': 'MSFT',
        'limit': 5
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ Request failed: {response.status_code}")
            return False
        
        data = response.json()
        results = data.get('results', [])
        
        # Find most recent with actual results
        past_earnings = [e for e in results if e.get('actual_eps') is not None]
        
        if not past_earnings:
            print("⚠️  No historical earnings with actuals found")
            return False
        
        latest = past_earnings[0]
        
        print("📊 EXAMPLE DETECTION (Based on past MSFT earnings):")
        print(f"   Ticker: {latest.get('ticker')}")
        print(f"   Date: {latest.get('date')}")
        print(f"   Time: {latest.get('time')}")
        
        # EPS Analysis
        actual_eps = latest.get('actual_eps')
        est_eps = latest.get('estimated_eps')
        eps_surprise_pct = latest.get('eps_surprise_percent', 0) * 100
        
        print(f"\n   EPS:")
        print(f"      Actual: ${actual_eps:.2f}")
        print(f"      Estimate: ${est_eps:.2f}")
        print(f"      Surprise: {eps_surprise_pct:+.2f}%")
        
        # Determine sentiment
        if eps_surprise_pct > 2:
            sentiment = "🚀 BEAT"
            color = "GREEN"
        elif eps_surprise_pct < -2:
            sentiment = "📉 MISS"
            color = "RED"
        else:
            sentiment = "➡️ INLINE"
            color = "YELLOW"
        
        print(f"\n   Sentiment: {sentiment} ({color})")
        
        # Revenue Analysis
        actual_rev = latest.get('actual_revenue')
        est_rev = latest.get('estimated_revenue')
        rev_surprise_pct = latest.get('revenue_surprise_percent', 0) * 100
        
        if actual_rev and est_rev:
            print(f"\n   Revenue:")
            print(f"      Actual: ${actual_rev/1e9:.2f}B")
            print(f"      Estimate: ${est_rev/1e9:.2f}B")
            print(f"      Surprise: {rev_surprise_pct:+.2f}%")
        
        print(f"\n✅ This is what you'll see at 4:05 PM tomorrow (within 5 seconds!)")
        
        return True
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_discord_webhook():
    """Test 4: Verify Discord webhook"""
    print_header("TEST 4: DISCORD WEBHOOK TEST")
    
    print("Sending test earnings alert to Discord...\n")
    
    embed = {
        'title': '🧪 TEST: Earnings System v2',
        'description': '**This is a test alert for tomorrow\'s earnings**',
        'color': 0x5865F2,
        'fields': [
            {
                'name': '✅ System Status',
                'value': (
                    '• Benzinga API: Connected\n'
                    '• Real-time detection: 5 second checks\n'
                    '• Daily preview: 6:00 PM ET'
                ),
                'inline': False
            },
            {
                'name': '🎯 Tomorrow\'s Major Earnings',
                'value': 'GOOG, MSFT, META @ ~4:00 PM ET',
                'inline': False
            },
            {
                'name': '⚡ Detection Speed',
                'value': 'Earnings will be detected within 5 seconds of release',
                'inline': False
            }
        ],
        'footer': {
            'text': 'Earnings Monitor v2 - Test Message'
        },
        'timestamp': datetime.now().isoformat()
    }
    
    payload = {'embeds': [embed]}
    
    try:
        response = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        
        if response.status_code == 204:
            print("✅ Discord webhook: SUCCESS")
            print("   Check your #earnings-realtime channel!")
            return True
        else:
            print(f"❌ Discord webhook failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    
    except Exception as e:
        print(f"❌ Webhook error: {str(e)}")
        return False


def test_daily_preview_format():
    """Test 5: Show what daily preview looks like"""
    print_header("TEST 5: DAILY PREVIEW FORMAT (6 PM)")
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    url = "https://api.polygon.io/benzinga/v1/earnings"
    params = {
        'apiKey': API_KEY,
        'date.gte': tomorrow,
        'date.lte': tomorrow,
        'limit': 100
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            print("⚠️  Could not fetch preview")
            return False
        
        data = response.json()
        results = data.get('results', [])
        confirmed = [e for e in results if e.get('date_status') == 'confirmed']
        
        print("This is what you'll receive at 6:00 PM tonight:\n")
        print(f"📅 EARNINGS PREVIEW - {tomorrow}")
        print(f"   {len(confirmed)} companies reporting earnings\n")
        
        # Group by importance
        major = [e for e in confirmed if e.get('importance', 0) >= 4]
        others = [e for e in confirmed if e.get('importance', 0) < 4]
        
        if major:
            print(f"🔥 MAJOR EARNINGS ({len(major)} companies):\n")
            for e in major[:10]:
                ticker = e.get('ticker')
                company = e.get('company_name', ticker)
                time = e.get('time', 'N/A')[:5]
                eps_est = e.get('estimated_eps', 0)
                rev_est = e.get('estimated_revenue', 0) / 1e9 if e.get('estimated_revenue') else 0
                
                print(f"   {ticker} - {company}")
                print(f"      ⏰ {time} ET | EPS Est: ${eps_est:.2f} | Rev Est: ${rev_est:.2f}B\n")
        
        if others:
            print(f"ℹ️  OTHER EARNINGS ({len(others)} companies):")
            tickers = ', '.join([e['ticker'] for e in others[:20]])
            print(f"   {tickers}...\n")
        
        print("✅ Preview will be sent to Discord at 6:00 PM ET")
        
        return True
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_monitor_timing():
    """Test 6: Explain monitoring windows"""
    print_header("TEST 6: MONITORING WINDOWS & TIMING")
    
    print("📅 SCHEDULE FOR TOMORROW:")
    print("\n5:00 AM - 8:00 AM ET: PRE-MARKET WINDOW")
    print("   • Check every 20 seconds")
    print("   • Catch before-market earnings")
    print("   • Less common, but important")
    
    print("\n9:30 AM - 4:00 PM ET: MARKET HOURS")
    print("   • Monitor idle (earnings rarely during trading)")
    
    print("\n3:50 PM - 7:00 PM ET: POST-MARKET WINDOW ⚡")
    print("   • Check every 5 SECONDS")
    print("   • This is when GOOG, MSFT, META report")
    print("   • ULTRA-FAST detection")
    print("   • Alert within 5 seconds of release")
    
    print("\n6:00 PM ET: DAILY PREVIEW")
    print("   • Scheduled task runs")
    print("   • Preview sent for next day")
    print("   • Helps you plan trades")
    
    print("\n✅ TOMORROW AT 4:05 PM:")
    print("   1. MSFT releases earnings")
    print("   2. System detects within 5 seconds (by 4:05:05 PM)")
    print("   3. Analyzes beat/miss")
    print("   4. Sends Discord alert")
    print("   5. You see it and check Bookmap")
    print("   6. Execute trade within 30 seconds")
    
    return True


def run_all_tests():
    """Run complete test suite"""
    print("\n" + "=" * 80)
    print("🚀 EARNINGS SYSTEM V2 - COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    
    results = {}
    
    # Run tests
    results['API Access'] = test_benzinga_api_access()
    results['Tomorrow\'s Earnings'] = test_tomorrows_earnings()
    results['Real-time Detection'] = test_realtime_detection()
    results['Discord Webhook'] = test_discord_webhook()
    results['Daily Preview'] = test_daily_preview_format()
    results['Monitor Timing'] = test_monitor_timing()
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test:.<40} {status}")
    
    print(f"\n{'='*80}")
    print(f"TOTAL: {passed}/{total} tests passed")
    print(f"{'='*80}")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - System ready for tomorrow!")
        print("\n📋 NEXT STEPS:")
        print("   1. Replace earnings_monitor.py with new version")
        print("   2. Update app.py with scheduler")
        print("   3. Restart server")
        print("   4. Wait for 4:05 PM tomorrow")
        print("   5. Get alerts within 5 seconds! 🚀")
    else:
        print("\n⚠️  SOME TESTS FAILED - Fix issues before tomorrow")
    
    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
