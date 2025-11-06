#!/usr/bin/env python3
"""
Auto-Fix Discord 400 Errors
Applies all necessary changes to fix Discord alerter issues
"""

import os
import sys
import shutil
from datetime import datetime

# Configuration
BASE_DIR = "/Users/anu.juneja/Desktop/trading-platform/backend"
DISCORD_ALERTER_PATH = os.path.join(BASE_DIR, "alerts/discord_alerter.py")
CONFIG_PATH = os.path.join(BASE_DIR, "config/config.yaml")


def backup_file(filepath):
    """Create timestamped backup of file"""
    if not os.path.exists(filepath):
        print(f"⚠️  File not found: {filepath}")
        return False
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{filepath}.backup_{timestamp}"
    shutil.copy2(filepath, backup_path)
    print(f"✅ Backed up: {backup_path}")
    return True


def fix_discord_alerter():
    """Add missing public send_webhook method and channels to DiscordAlerter"""
    
    if not os.path.exists(DISCORD_ALERTER_PATH):
        print(f"❌ File not found: {DISCORD_ALERTER_PATH}")
        return False
    
    # Backup first
    backup_file(DISCORD_ALERTER_PATH)
    
    with open(DISCORD_ALERTER_PATH, 'r') as f:
        content = f.read()
    
    # Fix 1: Add channels to __init__
    # Find the webhooks dict and add new channels
    if "'unusual_activity':" not in content:
        # Add new channels after 'openai_news' line
        old_init = """            'openai_news': self._expand_env_var(config.get('webhook_openai_news'))
            }"""
        
        new_init = """            'openai_news': self._expand_env_var(config.get('webhook_openai_news')),
            
            # Monitor-specific channels
            'unusual_activity': self._expand_env_var(config.get('webhook_unusual_activity')),
            'momentum_signals': self._expand_env_var(config.get('webhook_momentum_signals')),
            'wall_strength': self._expand_env_var(config.get('webhook_odte_levels'))
            }"""
        
        if old_init in content:
            content = content.replace(old_init, new_init)
            print("✅ Added missing channels to __init__")
        else:
            print("⚠️  Could not find exact __init__ pattern, may need manual update")
    else:
        print("ℹ️  Channels already present in __init__")
    
    # Fix 2: Add public send_webhook method
    if "def send_webhook(self, channel: str, payload: Dict)" not in content:
        # Find _send_webhook method and add public wrapper after it
        public_method = """
    def send_webhook(self, channel: str, payload: Dict) -> bool:
        \"\"\"
        PUBLIC method to send webhook to specific channel
        Wrapper for _send_webhook with channel name normalization
        
        Args:
            channel: Channel name (case-insensitive)
            payload: Discord payload dict (must include 'embeds' wrapper)
        
        Returns:
            True if sent successfully, False otherwise
        \"\"\"
        # Normalize channel name to lowercase
        channel_lower = channel.lower()
        
        # Channel name mapping
        channel_map = {
            'momentum_signals': 'momentum_signals',
            'unusual_activity': 'unusual_activity',
            'volume_spike': 'volume_spike',
            'odte_levels': 'odte_levels',
            'wall_strength': 'odte_levels',  # Shares ODTE channel
            'news_alerts': 'news_alerts',
            'market_impact': 'market_impact',
            'trading': 'trading',
            'news': 'news',
            'earnings_weekly': 'earnings_weekly',
            'earnings_realtime': 'earnings_realtime',
            'openai_news': 'openai_news'
        }
        
        # Get mapped channel name
        mapped_channel = channel_map.get(channel_lower, channel_lower)
        
        # Use the private _send_webhook method
        return self._send_webhook(mapped_channel, payload)
"""
        
        # Find where to insert (after _send_webhook method)
        insert_marker = "    def send_volume_spike_alert"
        if insert_marker in content:
            content = content.replace(insert_marker, public_method + "\n" + insert_marker)
            print("✅ Added public send_webhook method")
        else:
            print("⚠️  Could not find insertion point, may need manual update")
    else:
        print("ℹ️  Public send_webhook method already exists")
    
    # Write updated content
    with open(DISCORD_ALERTER_PATH, 'w') as f:
        f.write(content)
    
    print(f"✅ Updated: {DISCORD_ALERTER_PATH}")
    return True


def fix_config_yaml():
    """Add missing webhook configurations to config.yaml"""
    
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ File not found: {CONFIG_PATH}")
        return False
    
    # Backup first
    backup_file(CONFIG_PATH)
    
    with open(CONFIG_PATH, 'r') as f:
        content = f.read()
    
    # Check if webhooks already exist
    if 'webhook_unusual_activity' not in content:
        # Add new webhooks after webhook_openai_news
        old_webhooks = "  webhook_openai_news: ${DISCORD_OPENAI_NEWS}"
        new_webhooks = """  webhook_openai_news: ${DISCORD_OPENAI_NEWS}
  
  # Monitor-specific webhooks
  webhook_unusual_activity: ${DISCORD_UNUSUAL_ACTIVITY}
  webhook_momentum_signals: ${DISCORD_MOMENTUM_SIGNALS}
  webhook_wall_strength: ${DISCORD_ODTE_LEVELS}"""
        
        if old_webhooks in content:
            content = content.replace(old_webhooks, new_webhooks)
            print("✅ Added missing webhooks to config.yaml")
        else:
            print("⚠️  Could not find exact webhook pattern, may need manual update")
    else:
        print("ℹ️  Webhooks already present in config.yaml")
    
    # Write updated content
    with open(CONFIG_PATH, 'w') as f:
        f.write(content)
    
    print(f"✅ Updated: {CONFIG_PATH}")
    return True


def verify_env_vars():
    """Check if required Discord webhook env vars are set"""
    print("\n📋 Checking environment variables...")
    
    required_vars = [
        'DISCORD_UNUSUAL_ACTIVITY',
        'DISCORD_MOMENTUM_SIGNALS',
        'DISCORD_VOLUME_SPIKE',
        'DISCORD_ODTE_LEVELS'
    ]
    
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if value and value.startswith('http'):
            print(f"✅ {var}: Set")
        else:
            print(f"❌ {var}: Not set or invalid")
            missing.append(var)
    
    if missing:
        print(f"\n⚠️  Missing environment variables: {', '.join(missing)}")
        print("   Make sure these are set in your .env file")
        return False
    
    return True


def main():
    """Main fix execution"""
    print("=" * 70)
    print("🔧 DISCORD 400 ERROR AUTO-FIX")
    print("=" * 70)
    print()
    
    if not os.path.exists(BASE_DIR):
        print(f"❌ Base directory not found: {BASE_DIR}")
        print("   Update BASE_DIR in this script to match your setup")
        sys.exit(1)
    
    print("📁 Working directory:", BASE_DIR)
    print()
    
    # Step 1: Fix discord_alerter.py
    print("=" * 70)
    print("STEP 1: Fixing discord_alerter.py")
    print("=" * 70)
    if fix_discord_alerter():
        print("✅ discord_alerter.py fixed successfully")
    else:
        print("❌ Failed to fix discord_alerter.py")
        sys.exit(1)
    
    print()
    
    # Step 2: Fix config.yaml
    print("=" * 70)
    print("STEP 2: Fixing config.yaml")
    print("=" * 70)
    if fix_config_yaml():
        print("✅ config.yaml fixed successfully")
    else:
        print("❌ Failed to fix config.yaml")
        sys.exit(1)
    
    print()
    
    # Step 3: Verify env vars
    print("=" * 70)
    print("STEP 3: Verifying environment variables")
    print("=" * 70)
    env_ok = verify_env_vars()
    
    print()
    print("=" * 70)
    print("🎯 FIX COMPLETE!")
    print("=" * 70)
    print()
    
    if env_ok:
        print("✅ All fixes applied successfully")
        print()
        print("Next steps:")
        print("1. Restart your trading platform:")
        print(f"   cd {BASE_DIR}")
        print("   pkill -f app.py")
        print("   python app.py")
        print()
        print("2. Monitor logs for successful alerts:")
        print("   tail -f logs/always_on_trader.log | grep 'Alert sent\\|Discord'")
        print()
        print("Expected: Alerts should start appearing in Discord within 5 minutes")
    else:
        print("⚠️  Fixes applied, but environment variables need attention")
        print("   Update your .env file with missing Discord webhook URLs")
        print("   Then restart the app")
    
    print()


if __name__ == "__main__":
    main()
