"""
Test Discord Alert for OpenAI Monitor
Run this to test if Discord webhook is working correctly
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add backend to path
backend_dir = Path(__file__).parent.parent if Path(__file__).parent.name == 'tests' else Path(__file__).parent
sys.path.insert(0, str(backend_dir))

load_dotenv()

def test_discord_webhook():
    """Test Discord webhook with fake OpenAI news alert"""
    
    webhook_url = os.getenv('DISCORD_OPENAI_NEWS')
    
    if not webhook_url:
        print("❌ Error: DISCORD_OPENAI_NEWS not found in .env")
        print("Please add your Discord webhook URL to .env")
        return False
    
    print("=" * 60)
    print("🧪 TESTING DISCORD WEBHOOK FOR OPENAI MONITOR")
    print("=" * 60)
    print(f"\n📡 Webhook: {webhook_url[:50]}...")
    print(f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create fake alert data - simulating a CRITICAL OpenAI news alert
    fake_article = {
        'title': 'Broadcom announces multi-year OpenAI partnership for custom AI chips',
        'publisher': {
            'name': 'Bloomberg'
        },
        'published_utc': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'article_url': 'https://example.com/test-article'
    }
    
    fake_tickers = ['NVDA', 'AVGO']
    
    fake_volume_confirmations = {
        'NVDA': {
            'rvol': 4.2,
            'classification': 'EXTREME',
            'confirmed': True,
            'critical': True
        },
        'AVGO': {
            'rvol': 3.1,
            'classification': 'HIGH',
            'confirmed': True,
            'critical': True
        }
    }
    
    fake_impact_score = 9.5
    
    fake_alert_data = {
        'article': fake_article,
        'tickers': fake_tickers,
        'volume_confirmations': fake_volume_confirmations,
        'impact_score': fake_impact_score
    }
    
    print("\n📊 Test Alert Details:")
    print(f"   • Tickers: {', '.join(fake_tickers)}")
    print(f"   • Impact Score: {fake_impact_score}/10")
    print(f"   • NVDA RVOL: {fake_volume_confirmations['NVDA']['rvol']}x")
    print(f"   • AVGO RVOL: {fake_volume_confirmations['AVGO']['rvol']}x")
    
    # Send to Discord
    print("\n🚀 Sending test alert to Discord...")
    
    try:
        from monitors.openai_news_monitor import OpenAINewsMonitor
        import yaml
        
        # Load config
        config_path = backend_dir / 'config' / 'config.yaml'
        with open(config_path, 'r') as f:
            config_yaml = yaml.safe_load(f)
        
        # Create monitor instance
        monitor = OpenAINewsMonitor(
            polygon_api_key=os.getenv('POLYGON_API_KEY'),
            config=config_yaml
        )
        
        monitor.set_discord_webhook(webhook_url)
        
        # Send the alert
        success = monitor.send_discord_alert(fake_alert_data)
        
        if success:
            print("\n✅ SUCCESS! Discord alert sent!")
            print("\n📱 Check your Discord channel 'open-ai-tracker' for the alert!")
            print("\nThe alert should show:")
            print("   🔴 CRITICAL OpenAI Alert - VOLUME CONFIRMED")
            print("   📰 Bloomberg - just now")
            print("   🏢 Tickers: NVDA, AVGO")
            print("   💥 Impact Score: 9.5/10")
            print("   📊 Volume confirmation for both tickers")
            return True
        else:
            print("\n❌ FAILED! Discord alert not sent")
            print("Check the error messages above")
            return False
            
    except ImportError as e:
        print(f"\n❌ Error: Could not import OpenAINewsMonitor")
        print(f"   {str(e)}")
        print("\nMake sure you've created the monitor file in backend/monitors/")
        return False
    
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_simple_webhook():
    """Simpler test using just requests library"""
    import requests
    
    webhook_url = os.getenv('DISCORD_OPENAI_NEWS')
    
    if not webhook_url:
        print("❌ DISCORD_OPENAI_NEWS not found in .env")
        return False
    
    print("\n" + "=" * 60)
    print("🧪 SIMPLE WEBHOOK TEST (Direct POST)")
    print("=" * 60)
    
    # Simple test message
    embed = {
        'title': '🧪 Test Alert - OpenAI Monitor',
        'description': 'This is a test message from your OpenAI News Monitor',
        'color': 0x00ff00,
        'fields': [
            {
                'name': 'Status',
                'value': '✅ Webhook is working correctly!',
                'inline': False
            },
            {
                'name': 'Test Time',
                'value': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'inline': False
            }
        ],
        'footer': {
            'text': 'OpenAI News Monitor - Test Message'
        }
    }
    
    try:
        response = requests.post(
            webhook_url,
            json={'embeds': [embed]},
            timeout=10
        )
        response.raise_for_status()
        
        print("\n✅ Simple test message sent successfully!")
        print("📱 Check your Discord channel!")
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to send test message: {str(e)}")
        return False


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Test OpenAI Monitor Discord Webhook')
    parser.add_argument('--simple', action='store_true', 
                       help='Run simple webhook test (no dependencies)')
    args = parser.parse_args()
    
    if args.simple:
        success = test_simple_webhook()
    else:
        success = test_discord_webhook()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ TEST PASSED - Discord webhook is working!")
    else:
        print("❌ TEST FAILED - Check errors above")
    print("=" * 60 + "\n")
    
    sys.exit(0 if success else 1)
