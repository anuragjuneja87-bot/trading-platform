#!/usr/bin/env python3
"""
Quick Config & System Test
Tests your updated config in one command
"""

import os
import sys
import yaml
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}{text:^80}{RESET}")
    print(f"{BLUE}{'='*80}{RESET}\n")

def print_status(text, status):
    if status == "PASS":
        print(f"{GREEN}✅ {text}{RESET}")
    elif status == "FAIL":
        print(f"{RED}❌ {text}{RESET}")
    elif status == "WARN":
        print(f"{YELLOW}⚠️  {text}{RESET}")
    else:
        print(f"ℹ️  {text}")

def test_config_file():
    """Test if config has all required monitors"""
    print_header("TEST 1: CONFIG FILE VALIDATION")
    
    config_paths = [
        'config/config.yaml',
        'backend/config/config.yaml',
        '../config/config.yaml'
    ]
    
    config = None
    config_path = None
    
    for path in config_paths:
        if os.path.exists(path):
            config_path = path
            break
    
    if not config_path:
        print_status("config.yaml not found", "FAIL")
        return False, None
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        print_status(f"Config loaded: {config_path}", "PASS")
    except Exception as e:
        print_status(f"Error loading config: {str(e)}", "FAIL")
        return False, None
    
    # Check for required monitors
    required_monitors = {
        'unusual_activity_monitor': {
            'thresholds': ['min_oi_change_pct', 'min_volume_ratio', 'min_score']
        },
        'momentum_signal_monitor': {
            'thresholds': ['min_rvol', 'min_dark_pool_strength', 'min_confluence']
        },
        'wall_strength_monitor': {
            'thresholds': ['min_oi_change_pct', 'strong_change_pct']
        }
    }
    
    all_good = True
    results = {}
    
    for monitor_name, sections in required_monitors.items():
        print(f"\n{monitor_name}:")
        
        if monitor_name not in config:
            print_status(f"  NOT FOUND IN CONFIG", "FAIL")
            all_good = False
            results[monitor_name] = False
            continue
        
        print_status(f"  Found in config", "PASS")
        
        monitor_config = config[monitor_name]
        
        # Check enabled
        enabled = monitor_config.get('enabled', False)
        if enabled:
            print_status(f"  Enabled: True", "PASS")
        else:
            print_status(f"  Enabled: False (monitor won't run!)", "WARN")
        
        # Check thresholds
        thresholds = monitor_config.get('thresholds', {})
        for threshold_key in sections['thresholds']:
            if threshold_key in thresholds:
                value = thresholds[threshold_key]
                print_status(f"  {threshold_key}: {value}", "PASS")
            else:
                print_status(f"  {threshold_key}: NOT FOUND", "FAIL")
                all_good = False
        
        results[monitor_name] = True
    
    return all_good, results

def test_webhooks():
    """Test Discord webhooks"""
    print_header("TEST 2: DISCORD WEBHOOK CONNECTIVITY")
    
    load_dotenv()
    
    webhooks = {
        'DISCORD_UNUSUAL_ACTIVITY': 'Unusual Activity',
        'DISCORD_MOMENTUM_SIGNALS': 'Momentum Signals',
        'DISCORD_ODTE_LEVELS': 'ODTE Gamma Walls'
    }
    
    all_good = True
    
    for env_var, channel_name in webhooks.items():
        webhook_url = os.getenv(env_var)
        
        if not webhook_url:
            print_status(f"{channel_name}: Webhook not in .env", "FAIL")
            all_good = False
            continue
        
        # Send test message
        embed = {
            'title': f'🧪 Quick Test - {channel_name}',
            'description': 'Config updated! System test in progress...',
            'color': 0x00ff00,
            'timestamp': datetime.utcnow().isoformat(),
            'fields': [
                {
                    'name': '✅ Status',
                    'value': 'Monitors configured with aggressive thresholds',
                    'inline': False
                }
            ],
            'footer': {'text': 'Quick System Test'}
        }
        
        try:
            response = requests.post(webhook_url, json={'embeds': [embed]}, timeout=10)
            response.raise_for_status()
            print_status(f"{channel_name}: Test message sent", "PASS")
        except Exception as e:
            print_status(f"{channel_name}: Failed - {str(e)}", "FAIL")
            all_good = False
    
    return all_good

def test_api_keys():
    """Test API keys are present"""
    print_header("TEST 3: API KEYS")
    
    load_dotenv()
    
    required_keys = {
        'POLYGON_API_KEY': 'Polygon.io API Key',
        'TRADIER_API_KEY': 'Tradier API Key (optional but recommended)'
    }
    
    all_good = True
    
    for key, description in required_keys.items():
        value = os.getenv(key)
        if value:
            masked = value[:8] + '...' + value[-4:] if len(value) > 12 else '***'
            print_status(f"{description}: {masked}", "PASS")
        else:
            if key == 'TRADIER_API_KEY':
                print_status(f"{description}: Not set (optional)", "WARN")
            else:
                print_status(f"{description}: Not set", "FAIL")
                all_good = False
    
    return all_good

def check_market_hours():
    """Check if we're in market hours"""
    print_header("TEST 4: MARKET HOURS CHECK")
    
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    day_of_week = now.weekday()
    
    is_weekday = day_of_week < 5
    current_minutes = hour * 60 + minute
    market_open = 9 * 60 + 30  # 9:30 AM
    market_close = 16 * 60  # 4:00 PM
    premarket_start = 7 * 60  # 7:00 AM
    
    in_premarket = premarket_start <= current_minutes < market_open
    in_regular_hours = market_open <= current_minutes < market_close
    
    print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')} ({now.strftime('%A')})")
    
    if not is_weekday:
        print_status("Weekend - Markets closed", "WARN")
        print("  💡 Test using: market_hours_only: false")
    elif in_regular_hours:
        print_status("Regular trading hours - Perfect for testing!", "PASS")
        remaining = (market_close - current_minutes) / 60
        print(f"  ⏰ {remaining:.1f} hours remaining until close")
    elif in_premarket:
        print_status("Pre-market hours - Some monitors active", "PASS")
    else:
        print_status("After hours - Most monitors inactive", "WARN")
        print("  💡 Test using: market_hours_only: false")
    
    return in_regular_hours or in_premarket

def print_summary(config_ok, webhooks_ok, api_keys_ok, market_open):
    """Print test summary"""
    print_header("TEST SUMMARY")
    
    tests = [
        ("Config File", config_ok),
        ("Discord Webhooks", webhooks_ok),
        ("API Keys", api_keys_ok),
        ("Market Hours", market_open)
    ]
    
    passed = sum(1 for _, result in tests if result)
    total = len(tests)
    
    for test_name, result in tests:
        status = "PASS" if result else "FAIL"
        print_status(f"{test_name}: {status}", status)
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print(f"\n{GREEN}{'='*80}")
        print("✅ ALL TESTS PASSED - System ready to go!")
        print("="*80 + RESET)
        print("\n📋 NEXT STEPS:")
        print("1. Restart your app: pkill -f app.py && python3 app.py")
        print("2. Watch logs: tail -f logs/always_on_trader.log")
        print("3. Check Discord channels for test messages")
        print("4. Wait for first real alert (5-15 minutes)")
    else:
        print(f"\n{RED}{'='*80}")
        print("❌ SOME TESTS FAILED - Fix these issues first")
        print("="*80 + RESET)
        print("\n🔧 FIXES:")
        
        if not config_ok:
            print("• Config: Make sure you copied config_UPDATED.yaml to config/config.yaml")
        if not webhooks_ok:
            print("• Webhooks: Check Discord webhook URLs in .env file")
        if not api_keys_ok:
            print("• API Keys: Add POLYGON_API_KEY to .env file")
        if not market_open:
            print("• Market Hours: Set market_hours_only: false to test outside hours")

def main():
    print(f"\n{BLUE}{'='*80}")
    print(f"QUICK CONFIG & SYSTEM TEST")
    print(f"{'='*80}{RESET}")
    print(f"Testing your updated configuration...")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Run tests
    config_ok, _ = test_config_file()
    webhooks_ok = test_webhooks()
    api_keys_ok = test_api_keys()
    market_open = check_market_hours()
    
    # Summary
    print_summary(config_ok, webhooks_ok, api_keys_ok, market_open)
    
    print(f"\n{BLUE}{'='*80}")
    print(f"Test complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}{RESET}\n")
    
    # Exit code
    sys.exit(0 if config_ok and webhooks_ok and api_keys_ok else 1)

if __name__ == '__main__':
    main()