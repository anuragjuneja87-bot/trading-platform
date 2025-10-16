"""
Test Real-Time Earnings Alert System
Simulates an earnings event to test Discord notifications
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from dotenv import load_dotenv
import requests
from datetime import datetime

load_dotenv()


def send_test_earnings_alert(symbol='TSLA', beat_or_miss='BEAT'):
    """
    Send a test earnings alert to Discord
    Simulates what happens when real earnings are detected
    """
    
    webhook_url = os.getenv('DISCORD_EARNINGS_REALTIME')
    
    if not webhook_url:
        print("\n❌ ERROR: DISCORD_EARNINGS_REALTIME webhook not found in .env")
        print("Add this to your .env file:")
        print("DISCORD_EARNINGS_REALTIME=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL")
        return False
    
    print("\n" + "=" * 80)
    print("🧪 TESTING REAL-TIME EARNINGS ALERT SYSTEM")
    print("=" * 80)
    
    # Simulate earnings data
    if beat_or_miss == 'BEAT':
        eps_actual = 1.85
        eps_estimate = 1.72
        revenue_actual = 25.2
        revenue_estimate = 24.8
        color = 0x00ff00  # Green
        title_emoji = "🚀"
        reaction = "BEAT ESTIMATES"
    else:
        eps_actual = 1.55
        eps_estimate = 1.72
        revenue_actual = 24.1
        revenue_estimate = 24.8
        color = 0xff0000  # Red
        title_emoji = "⚠️"
        reaction = "MISSED ESTIMATES"
    
    # Build Discord embed (exactly like real alerts)
    embed = {
        'title': f'{title_emoji} EARNINGS ALERT: {symbol}',
        'description': f'**{symbol} {reaction}**',
        'color': color,
        'timestamp': datetime.utcnow().isoformat(),
        'fields': [
            {
                'name': '📊 EPS (Earnings Per Share)',
                'value': f'**Actual:** ${eps_actual}\n**Estimate:** ${eps_estimate}\n**Difference:** ${eps_actual - eps_estimate:+.2f}',
                'inline': True
            },
            {
                'name': '💰 Revenue (Billions)',
                'value': f'**Actual:** ${revenue_actual}B\n**Estimate:** ${revenue_estimate}B\n**Difference:** ${revenue_actual - revenue_estimate:+.1f}B',
                'inline': True
            },
            {
                'name': '🎯 Trading Action',
                'value': 'Check pre-market/after-hours price action\nWatch for gap up/down at open\nMonitor volume and momentum' if beat_or_miss == 'BEAT' else 'Watch for gap down at open\nLook for support levels\nMonitor selling pressure',
                'inline': False
            }
        ],
        'footer': {
            'text': f'Test Alert | Real earnings will trigger automatically'
        }
    }
    
    # Send to Discord
    try:
        print(f"\n📤 Sending test {beat_or_miss} alert for {symbol}...")
        print(f"   Webhook: {webhook_url[:50]}...")
        
        payload = {'embeds': [embed]}
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        
        print("\n" + "=" * 80)
        print("✅ SUCCESS! Test earnings alert sent to Discord!")
        print("=" * 80)
        print(f"\n📱 Check your Discord #earnings-realtime channel")
        print(f"🎯 Alert Type: {symbol} {beat_or_miss}")
        print(f"💬 This is how real earnings alerts will look")
        print("\n" + "=" * 80)
        
        return True
        
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        print(f"Response: {e.response.text if hasattr(e, 'response') else 'No response'}")
        return False
    except Exception as e:
        print(f"\n❌ Failed to send test alert: {str(e)}")
        return False


def check_todays_earnings():
    """
    Check if any of your watchlist stocks have earnings TODAY
    """
    print("\n" + "=" * 80)
    print("📅 CHECKING TODAY'S ACTUAL EARNINGS")
    print("=" * 80)
    
    # Known earnings for this week (from our calendar)
    october_earnings = {
        'Oct 11': ['JPM', 'WFC', 'BLK'],
        'Oct 15': ['UNH', 'GS', 'BAC', 'C', 'JNJ'],
        'Oct 16': ['NVDA'],  # Example - check actual dates
        'Oct 17': ['NFLX'],
        'Oct 18': ['PG'],
        'Oct 23': ['TSLA', 'IBM', 'T', 'KO'],
        'Oct 29': ['GOOGL'],
        'Oct 30': ['MSFT', 'META'],
        'Oct 31': ['AAPL', 'AMZN'],
    }
    
    today = datetime.now()
    today_str = today.strftime('Oct %d')
    
    print(f"\nToday: {today.strftime('%A, %B %d, %Y')}")
    
    if today_str in october_earnings:
        companies = october_earnings[today_str]
        print(f"\n🎯 EARNINGS TODAY: {len(companies)} companies")
        for symbol in companies:
            print(f"   • {symbol}")
        print(f"\n💡 Your alert system will automatically detect these when they report!")
        print(f"📢 Alerts typically come 5-30 minutes after market close")
    else:
        print(f"\n📭 No major earnings scheduled for today")
        print(f"\n🔍 Next earnings days:")
        for date, symbols in october_earnings.items():
            print(f"   {date}: {', '.join(symbols)}")
    
    print("=" * 80)


def test_alert_manager_connection():
    """
    Test if alert manager is running and can detect earnings
    """
    print("\n" + "=" * 80)
    print("🔍 TESTING ALERT MANAGER CONNECTION")
    print("=" * 80)
    
    try:
        # Check if server is running
        response = requests.get('http://localhost:5001/api/health', timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print("\n✅ Dashboard server is running!")
            print(f"   Alerts enabled: {data.get('alerts_enabled')}")
            print(f"   Version: {data.get('version')}")
            
            # Check alert stats
            stats_response = requests.get('http://localhost:5001/api/alerts/stats', timeout=5)
            if stats_response.status_code == 200:
                stats = stats_response.json()
                print(f"\n📊 Alert Stats:")
                print(f"   Total scans: {stats.get('stats', {}).get('total_scans', 0)}")
                print(f"   Alerts sent: {stats.get('stats', {}).get('alerts_sent', 0)}")
                print(f"   Market state: {stats.get('market_state', 'unknown')}")
            
            return True
        else:
            print(f"\n⚠️  Server returned status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("\n❌ Dashboard server is NOT running!")
        print("\n💡 Start it with:")
        print("   cd ~/Desktop/trading-platform/backend")
        print("   python3 app.py")
        return False
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False


def main():
    """
    Main test function
    """
    print("\n" + "=" * 80)
    print("🚀 REAL-TIME EARNINGS ALERT TEST SUITE")
    print("=" * 80)
    
    # Menu
    print("\nWhat would you like to test?")
    print("1. Send test BEAT earnings alert (bullish)")
    print("2. Send test MISS earnings alert (bearish)")
    print("3. Check today's actual earnings schedule")
    print("4. Test alert manager connection")
    print("5. Run all tests")
    print("6. Exit")
    
    choice = input("\nEnter choice (1-6): ").strip()
    
    if choice == '1':
        send_test_earnings_alert('TSLA', 'BEAT')
    
    elif choice == '2':
        send_test_earnings_alert('AAPL', 'MISS')
    
    elif choice == '3':
        check_todays_earnings()
    
    elif choice == '4':
        test_alert_manager_connection()
    
    elif choice == '5':
        print("\n" + "=" * 80)
        print("🔄 RUNNING ALL TESTS")
        print("=" * 80)
        
        # Test 1: Connection
        test_alert_manager_connection()
        
        # Test 2: Today's earnings
        check_todays_earnings()
        
        # Test 3: Send test alert
        print("\n")
        send_test_earnings_alert('TSLA', 'BEAT')
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS COMPLETE")
        print("=" * 80)
    
    elif choice == '6':
        print("\n👋 Exiting...")
        return
    
    else:
        print("\n❌ Invalid choice")
        return
    
    # Final instructions
    print("\n" + "=" * 80)
    print("💡 NEXT STEPS FOR REAL EARNINGS:")
    print("=" * 80)
    print("\n1. Keep your server running: python3 app.py")
    print("2. Wait for earnings to be released (typically after market close)")
    print("3. Your alert_manager.py will detect them within 5-15 minutes")
    print("4. You'll get Discord notification in #earnings-realtime")
    print("5. Use the info to plan trades for next day's open")
    
    print("\n📅 To see which stocks report when:")
    print("   python3 weekly_earnings_full_market.py")
    
    print("\n🔔 To manually trigger a scan:")
    print("   python3 alert_manager.py scan")
    
    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
