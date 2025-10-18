import sys
sys.path.insert(0, 'backend')

from monitors.odte_gamma_monitor import ODTEGammaMonitor
from utils.watchlist_manager import WatchlistManager
from dotenv import load_dotenv
import os
import yaml

load_dotenv()

# Load config
with open('backend/config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Get API keys
polygon_key = os.getenv('POLYGON_API_KEY')
tradier_key = os.getenv('TRADIER_API_KEY')
odte_webhook = os.getenv('DISCORD_ODTE_LEVELS')

# Add Tradier to config if available
if tradier_key:
    config['tradier_api_key'] = tradier_key
    config['tradier_account_type'] = os.getenv('TRADIER_ACCOUNT_TYPE', 'sandbox')

# Initialize watchlist
watchlist_manager = WatchlistManager('backend/watchlist.txt')

# Create monitor
monitor = ODTEGammaMonitor(
    polygon_api_key=polygon_key,
    config=config,
    watchlist_manager=watchlist_manager
)

# Set Discord webhook
if odte_webhook:
    monitor.set_discord_webhook(odte_webhook)

print("=" * 60)
print("0DTE GAMMA MONITOR - FORCE RUN TEST")
print("=" * 60)
print(f"📋 Watchlist: {watchlist_manager.load_symbols()}")
print(f"📏 Proximity: {monitor.min_proximity_pct}%-{monitor.max_proximity_pct}%")
print(f"🕐 Alert time: {monitor.alert_time}")
print(f"🔗 Discord: {'✅ Configured' if odte_webhook else '❌ Not configured'}")
print()

# BYPASS time check for testing
print("⚠️  BYPASSING time/weekday checks for FORCE RUN...")
monitor.weekdays_only = False  # Allow any day
monitor.enabled = True

# Manually override the is_alert_time method to return True
original_is_alert_time = monitor.is_alert_time
monitor.is_alert_time = lambda: True

print("🔍 Running 0DTE check NOW...\n")

# Run the check
alerts_sent = monitor.run_single_check()

# Restore original method
monitor.is_alert_time = original_is_alert_time

print()
print("=" * 60)
print(f"✅ Test complete: {alerts_sent} alerts sent")
print("=" * 60)
monitor.print_stats()
