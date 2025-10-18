"""
test_discord_alerts.py
Quick test script for Discord alert functionality
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_discord_webhook():
    """Test if Discord webhook is configured and working"""
    import requests
    
    # Check all webhook environment variables
    webhooks = {
        'TRADING_SIGNALS': os.getenv('DISCORD_TRADING_SIGNALS'),
        'NEWS_ALERTS': os.getenv('DISCORD_NEWS_ALERTS'),
        'VOLUME_SPIKE': os.getenv('DISCORD_VOLUME_SPIKE'),
        'MOMENTUM_SIGNALS': os.getenv('DISCORD_MOMENTUM_SIGNALS'),
        'OPENAI_NEWS': os.getenv('DISCORD_OPENAI_NEWS'),
        'WEEKLY_EARNINGS': os.getenv('DISCORD_WEEKLY_EARNINGS')
    }
    
    print("\n" + "=" * 60)
    print("DISCORD WEBHOOK CONFIGURATION CHECK")
    print("=" * 60)
    
    configured_count = 0
    for name, webhook in webhooks.items():
        if webhook:
            print(f"✅ {name}: Configured")
            configured_count += 1
        else:
            print(f"❌ {name}: NOT configured")
    
    print(f"\nTotal: {configured_count}/{len(webhooks)} webhooks configured")
    print("=" * 60)
    
    if configured_count == 0:
        print("\n⚠️  WARNING: No Discord webhooks configured!")
        print("\nTo configure webhooks:")
        print("1. Go to your Discord server")
        print("2. Right-click channel → Edit Channel → Integrations → Webhooks")
        print("3. Create webhook and copy URL")
        print("4. Add to your .env file:")
        print("   DISCORD_TRADING_SIGNALS=https://discord.com/api/webhooks/...")
        return False
    
    # Test first available webhook
    test_webhook = None
    test_name = None
    for name, webhook in webhooks.items():
        if webhook:
            test_webhook = webhook
            test_name = name
            break
    
    if test_webhook:
        print(f"\n🧪 Testing webhook: {test_name}")
        print("Sending test message...")
        
        try:
            response = requests.post(
                test_webhook,
                json={
                    'content': f'🧪 **Test Message from Trading Dashboard**\n\nThis is a test of the `{test_name}` webhook.\n\nIf you see this, your Discord alerts are working! ✅',
                    'username': 'Trading Dashboard Test'
                },
                timeout=10
            )
            
            if response.status_code == 204:
                print("✅ SUCCESS! Test message sent to Discord!")
                print(f"   Check your Discord channel for the test message.")
                return True
            else:
                print(f"❌ FAILED! Status code: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            return False
    
    return False


def test_alert_manager():
    """Test AlertManager with a real symbol"""
    from alerts.alert_manager import AlertManager
    
    print("\n" + "=" * 60)
    print("🔍 TESTING ALERT MANAGER")
    print("=" * 60)
    
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        print("❌ POLYGON_API_KEY not found in .env")
        return False
    
    try:
        print("\nInitializing Alert Manager...")
        manager = AlertManager(polygon_api_key=api_key)
        
        print("✅ Alert Manager initialized successfully")
        print(f"   Discord enabled: {manager.discord is not None}")
        print(f"   Volume spike alerts: ENABLED")
        print(f"   Signal metrics: {'ENABLED' if manager.metrics_tracker else 'DISABLED'}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_live_scan():
    """Run a live scan and check for alerts"""
    from alerts.alert_manager import AlertManager
    
    print("\n" + "=" * 60)
    print("🔍 RUNNING LIVE SCAN TEST")
    print("=" * 60)
    
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        print("❌ POLYGON_API_KEY not found")
        return False
    
    try:
        manager = AlertManager(polygon_api_key=api_key)
        
        print("\n📊 Running single scan...")
        print("This will:")
        print("  1. Analyze all watchlist symbols")
        print("  2. Send alerts to Discord if signals detected")
        print("  3. Check for volume spikes")
        print("\nStarting scan...\n")
        
        results = manager.run_scan()
        
        print("\n" + "=" * 60)
        print("SCAN RESULTS")
        print("=" * 60)
        
        signals = [r for r in results if r.get('alert_type') != 'MONITOR']
        volume_spikes = [r for r in results if r.get('volume_analysis', {}).get('volume_spike', {}).get('spike_detected')]
        
        print(f"Symbols analyzed: {len(results)}")
        print(f"Signals detected: {len(signals)}")
        print(f"Volume spikes: {len(volume_spikes)}")
        
        if signals:
            print("\n📢 SIGNALS FOUND:")
            for signal in signals:
                print(f"  • {signal['symbol']}: {signal['alert_type']} ({signal.get('confidence', 0):.1f}%)")
        
        if volume_spikes:
            print("\n🔥 VOLUME SPIKES FOUND:")
            for spike in volume_spikes:
                spike_data = spike['volume_analysis']['volume_spike']
                print(f"  • {spike['symbol']}: {spike_data['spike_ratio']:.2f}x ({spike_data['classification']})")
        
        manager.print_stats()
        
        if not signals and not volume_spikes:
            print("\n⚠️  No signals or volume spikes detected in this scan.")
            print("This is normal if market is quiet or outside trading hours.")
            print("\nTo force a test alert, try during market hours when there's activity.")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_manual_alert():
    """Send a manual test alert to Discord"""
    from alerts.discord_alerter import DiscordAlerter
    import yaml
    
    print("\n" + "=" * 60)
    print("🔍 MANUAL ALERT TEST")
    print("=" * 60)
    
    # Load config
    try:
        config_path = backend_dir / 'config' / 'config.yaml'
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        discord_config = config.get('discord', {})
        
        if not discord_config.get('enabled'):
            print("❌ Discord is disabled in config.yaml")
            return False
        
        alerter = DiscordAlerter(config=discord_config)
        
        # Create fake trading signal
        fake_signal = {
            'symbol': 'TEST',
            'alert_type': 'TEST ALERT',
            'confidence': 95.0,
            'current_price': 100.50,
            'signal': 'BUY',
            'bias_1h': 'BULLISH',
            'bias_daily': 'BULLISH',
            'entry_targets': {
                'entry': 100.00,
                'tp1': 105.00,
                'stop_loss': 98.00,
                'risk_reward': 2.5
            },
            'volume_analysis': {
                'rvol': {
                    'rvol': 3.5,
                    'classification': 'HIGH'
                }
            },
            'news_sentiment': 'POSITIVE'
        }
        
        print("\n📤 Sending test trading signal...")
        success = alerter.send_trading_signal(fake_signal)
        
        if success:
            print("✅ Test alert sent! Check your Discord channel.")
        else:
            print("❌ Failed to send test alert")
        
        # Test volume spike alert
        print("\n📤 Sending test volume spike alert...")
        fake_volume_spike = {
            'spike_ratio': 5.2,
            'classification': 'EXTREME',
            'direction': 'BREAKOUT',
            'alert_urgency': 'CRITICAL',
            'current_bar_volume': 1000000,
            'avg_previous_volume': 192000
        }
        
        success = alerter.send_volume_spike_alert(
            symbol='TEST',
            volume_data=fake_volume_spike,
            session='REGULAR'
        )
        
        if success:
            print("✅ Volume spike alert sent! Check your Discord channel.")
        else:
            print("❌ Failed to send volume spike alert")
        
        return success
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("🧪 DISCORD ALERT TESTING SUITE")
    print("=" * 80)
    
    print("\n1️⃣  Testing webhook configuration...")
    webhook_ok = test_discord_webhook()
    
    if not webhook_ok:
        print("\n⚠️  Skipping further tests - fix webhooks first")
        return
    
    print("\n2️⃣  Testing Alert Manager initialization...")
    manager_ok = test_alert_manager()
    
    if not manager_ok:
        print("\n⚠️  Alert Manager test failed")
        return
    
    print("\n3️⃣  Sending manual test alerts...")
    manual_ok = test_manual_alert()
    
    # Ask user if they want to run live scan
    print("\n" + "=" * 80)
    print("4️⃣  Live Scan Test (Optional)")
    print("=" * 80)
    print("\nThis will analyze real market data and send real alerts.")
    print("Only do this during market hours for best results.")
    
    response = input("\nRun live scan? (y/n): ").strip().lower()
    
    if response == 'y':
        test_live_scan()
    else:
        print("\nSkipping live scan test.")
    
    print("\n" + "=" * 80)
    print("🎉 TESTING COMPLETE")
    print("=" * 80)
    print("\nIf you received test messages in Discord, your alerts are working!")
    print("\nNext steps:")
    print("  1. Check your Discord channels")
    print("  2. Run: python app.py (to start full dashboard)")
    print("  3. Run: python alert_manager.py run (for continuous scanning)")
    print("\n")


if __name__ == '__main__':
    main()