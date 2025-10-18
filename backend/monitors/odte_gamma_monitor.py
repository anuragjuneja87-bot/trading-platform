"""
backend/monitors/odte_gamma_monitor.py
0DTE Gamma Level Monitor - Market Open Alert System

Triggers at 9:00 AM EST sharp when price is within 1-2% of 0DTE gamma walls
Only alerts if 0DTE options exist for that symbol
5-minute alert window (9:00-9:05 AM)
Routes to: DISCORD_ODTE_LEVELS webhook
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pytz
from collections import defaultdict

from analyzers.enhanced_professional_analyzer import EnhancedProfessionalAnalyzer


class ODTEGammaMonitor:
    def __init__(self, polygon_api_key: str, config: dict, watchlist_manager):
        """
        Initialize 0DTE Gamma Level Monitor
        
        Args:
            polygon_api_key: Polygon API key
            config: Configuration dict from config.yaml
            watchlist_manager: Watchlist manager instance
        """
        self.logger = logging.getLogger(__name__)
        self.polygon_api_key = polygon_api_key
        self.config = config
        self.watchlist_manager = watchlist_manager
        
        # Initialize analyzer (with Tradier if available)
        tradier_api_key = config.get('tradier_api_key')
        tradier_account_type = config.get('tradier_account_type', 'sandbox')
        
        self.analyzer = EnhancedProfessionalAnalyzer(
            polygon_api_key=polygon_api_key,
            tradier_api_key=tradier_api_key,
            tradier_account_type=tradier_account_type,
            debug_mode=False
        )
        
        # Get 0DTE config
        odte_config = config.get('odte_gamma_monitor', {})
        
        # Alert timing
        self.alert_time = odte_config.get('alert_time', '09:00')  # 9:00 AM EST
        self.alert_window_minutes = odte_config.get('alert_window_minutes', 5)  # 5 min window
        
        # Proximity thresholds (1-2%)
        self.min_proximity_pct = odte_config.get('min_proximity_pct', 1.0)
        self.max_proximity_pct = odte_config.get('max_proximity_pct', 2.0)
        
        # Only weekdays
        self.weekdays_only = odte_config.get('weekdays_only', True)
        
        # Watchlist only
        self.watchlist_only = odte_config.get('watchlist_only', True)
        
        # Discord webhook
        self.discord_webhook = None
        
        # Tracking
        self.alerted_today = set()  # Track which symbols we've alerted today
        self.last_alert_date = None
        
        # Stats
        self.stats = {
            'alerts_sent': 0,
            'symbols_checked': 0,
            'odte_found': 0,
            'proximity_matches': 0,
            'errors': 0
        }
        
        self.enabled = odte_config.get('enabled', True)
        
        self.logger.info("✅ 0DTE Gamma Monitor initialized")
        self.logger.info(f"   🕐 Alert time: {self.alert_time} EST")
        self.logger.info(f"   📏 Proximity: {self.min_proximity_pct}%-{self.max_proximity_pct}%")
        self.logger.info(f"   ⏱️ Alert window: {self.alert_window_minutes} minutes")
        self.logger.info(f"   📅 Weekdays only: {self.weekdays_only}")
    
    def set_discord_webhook(self, webhook_url: str):
        """Set Discord webhook URL"""
        self.discord_webhook = webhook_url
        self.logger.info("✅ Discord webhook configured for 0DTE alerts")
    
    def is_weekday(self) -> bool:
        """Check if today is a weekday"""
        et_tz = pytz.timezone('America/New_York')
        now = datetime.now(et_tz)
        return now.weekday() < 5  # Monday=0, Friday=4
    
    def is_alert_time(self) -> bool:
        """
        Check if current time is within alert window
        Returns True between 9:00-9:05 AM EST
        """
        et_tz = pytz.timezone('America/New_York')
        now = datetime.now(et_tz)
        
        # Parse alert time (e.g., "09:00")
        hour, minute = map(int, self.alert_time.split(':'))
        
        # Create alert time for today
        alert_start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        alert_end = alert_start + timedelta(minutes=self.alert_window_minutes)
        
        return alert_start <= now <= alert_end
    
    def reset_daily_tracking(self):
        """Reset tracking at start of new day"""
        et_tz = pytz.timezone('America/New_York')
        today = datetime.now(et_tz).date()
        
        if self.last_alert_date != today:
            self.alerted_today.clear()
            self.last_alert_date = today
            self.logger.info(f"🔄 Daily tracking reset for {today}")
    
    def check_odte_exists(self, symbol: str) -> tuple[bool, Optional[Dict]]:
        """
        Check if 0DTE options exist for this symbol today
        
        Returns:
            (exists, gamma_data) - gamma_data includes expiration info
        """
        try:
            # Get current price
            quote = self.analyzer.get_real_time_quote(symbol)
            current_price = quote['price']
            
            if current_price == 0:
                return False, None
            
            # Get gamma wall analysis (uses Tradier if available)
            gamma_data = self.analyzer.analyze_open_interest(symbol, current_price)
            
            if not gamma_data.get('available'):
                return False, None
            
            # Check if options expire TODAY (0DTE)
            expires_today = gamma_data.get('expires_today', False)
            
            if not expires_today:
                self.logger.debug(f"{symbol}: No 0DTE options (expires: {gamma_data.get('expiration', 'unknown')})")
                return False, None
            
            self.stats['odte_found'] += 1
            return True, gamma_data
            
        except Exception as e:
            self.logger.error(f"Error checking 0DTE for {symbol}: {str(e)}")
            self.stats['errors'] += 1
            return False, None
    
    def check_proximity_to_gamma_walls(self, symbol: str, current_price: float, 
                                      gamma_data: Dict) -> Optional[Dict]:
        """
        Check if current price is within 1-2% of any gamma wall
        
        Returns:
            Alert data dict if within proximity, None otherwise
        """
        try:
            gamma_levels = gamma_data.get('gamma_levels', [])
            
            if not gamma_levels:
                return None
            
            proximity_alerts = []
            
            for level in gamma_levels:
                strike = level['strike']
                distance_pct = abs(level['distance_pct'])
                
                # Check if within 1-2% proximity
                if self.min_proximity_pct <= distance_pct <= self.max_proximity_pct:
                    proximity_alerts.append({
                        'strike': strike,
                        'distance_pct': distance_pct,
                        'distance_dollars': level['distance_dollars'],
                        'type': level['type'],  # SUPPORT or RESISTANCE
                        'strength': level['strength'],
                        'total_oi': level['total_oi'],
                        'call_oi': level['call_oi'],
                        'put_oi': level['put_oi'],
                        'gamma_exposure': level['gamma_exposure'],
                        'direction': level['direction']
                    })
            
            if not proximity_alerts:
                return None
            
            # Sort by distance (closest first)
            proximity_alerts.sort(key=lambda x: abs(x['distance_pct']))
            
            self.stats['proximity_matches'] += 1
            
            return {
                'symbol': symbol,
                'current_price': current_price,
                'proximity_levels': proximity_alerts,
                'expiration': gamma_data.get('expiration'),
                'hours_until_expiry': gamma_data.get('hours_until_expiry', 0),
                'pinning_effect': gamma_data.get('analysis', {}).get('pinning_effect', 'UNKNOWN'),
                'expected_range': gamma_data.get('expected_range', {}),
                'data_source': gamma_data.get('data_source', 'unknown')
            }
            
        except Exception as e:
            self.logger.error(f"Error checking proximity for {symbol}: {str(e)}")
            return None
    
    def send_alert(self, alert_data: Dict) -> bool:
        """Send 0DTE gamma proximity alert to Discord"""
        if not self.discord_webhook:
            self.logger.warning("Discord webhook not configured")
            return False
        
        try:
            import requests
            
            symbol = alert_data['symbol']
            current_price = alert_data['current_price']
            proximity_levels = alert_data['proximity_levels']
            hours_until_expiry = alert_data['hours_until_expiry']
            pinning_effect = alert_data['pinning_effect']
            expected_range = alert_data['expected_range']
            
            # Get closest level
            closest = proximity_levels[0]
            
            # Determine urgency based on proximity and pinning
            if closest['distance_pct'] <= 1.2:
                urgency = 'CRITICAL'
                emoji = '🔴'
                color = 0xff0000
            elif closest['distance_pct'] <= 1.5:
                urgency = 'HIGH'
                emoji = '🟠'
                color = 0xff9900
            else:
                urgency = 'MEDIUM'
                emoji = '🟡'
                color = 0xffcc00
            
            # Direction emoji
            dir_emoji = '⬆️' if closest['type'] == 'RESISTANCE' else '⬇️'
            
            # Build embed
            embed = {
                'title': f"{emoji} 0DTE GAMMA ALERT - {symbol} {dir_emoji}",
                'description': f"Price within {closest['distance_pct']:.1f}% of **{closest['type']}** gamma wall",
                'color': color,
                'timestamp': datetime.utcnow().isoformat(),
                'fields': []
            }
            
            # Price and proximity
            embed['fields'].append({
                'name': '💰 Current Price',
                'value': f"**${current_price:.2f}**",
                'inline': True
            })
            
            embed['fields'].append({
                'name': f'{dir_emoji} Nearest Gamma Wall',
                'value': (
                    f"**${closest['strike']:.2f}** ({closest['type']})\n"
                    f"Distance: {closest['distance_pct']:.1f}% (${abs(closest['distance_dollars']):.2f})"
                ),
                'inline': True
            })
            
            # Time urgency
            embed['fields'].append({
                'name': '⏰ Time to Expiry',
                'value': f"**{hours_until_expiry:.1f} hours** until 4:00 PM ET",
                'inline': True
            })
            
            # Gamma wall details
            wall_details = (
                f"**Open Interest:** {closest['total_oi']:,}\n"
                f"**Calls:** {closest['call_oi']:,} | **Puts:** {closest['put_oi']:,}\n"
                f"**Gamma Exposure:** {closest['gamma_exposure']:,}\n"
                f"**Strength:** {closest['strength']}"
            )
            
            embed['fields'].append({
                'name': '🎯 Gamma Wall Details',
                'value': wall_details,
                'inline': False
            })
            
            # Expected range (if available)
            if expected_range:
                range_low = expected_range.get('low', 0)
                range_high = expected_range.get('high', 0)
                range_mid = expected_range.get('midpoint', 0)
                
                embed['fields'].append({
                    'name': '📊 Expected Range (0DTE)',
                    'value': (
                        f"**Low:** ${range_low:.2f}\n"
                        f"**Mid:** ${range_mid:.2f}\n"
                        f"**High:** ${range_high:.2f}"
                    ),
                    'inline': True
                })
            
            # Pinning effect
            pinning_emoji = '🧲' if pinning_effect in ['HIGH', 'EXTREME'] else '📍'
            embed['fields'].append({
                'name': f'{pinning_emoji} Pinning Effect',
                'value': f"**{pinning_effect}**",
                'inline': True
            })
            
            # Additional gamma walls (if any)
            if len(proximity_levels) > 1:
                other_walls = []
                for level in proximity_levels[1:3]:  # Show up to 2 more
                    other_walls.append(
                        f"• **${level['strike']:.2f}** ({level['type']}): "
                        f"{level['distance_pct']:.1f}% away"
                    )
                
                if other_walls:
                    embed['fields'].append({
                        'name': '🎯 Other Nearby Walls',
                        'value': '\n'.join(other_walls),
                        'inline': False
                    })
            
            # Trading action based on setup
            if closest['type'] == 'RESISTANCE':
                if hours_until_expiry < 2:
                    action = (
                        "🔴 **RESISTANCE NEAR EXPIRY**\n"
                        "✅ Watch for rejection and fade\n"
                        "✅ Price likely pinned below this level\n"
                        "✅ Consider short if confirmed"
                    )
                else:
                    action = (
                        "⚠️ **APPROACHING RESISTANCE**\n"
                        "✅ Monitor for breakout or rejection\n"
                        "✅ Watch order flow in Bookmap\n"
                        "✅ Wait for confirmation"
                    )
            else:  # SUPPORT
                if hours_until_expiry < 2:
                    action = (
                        "🟢 **SUPPORT NEAR EXPIRY**\n"
                        "✅ Watch for bounce and continuation\n"
                        "✅ Price likely pinned above this level\n"
                        "✅ Consider long if confirmed"
                    )
                else:
                    action = (
                        "⚠️ **APPROACHING SUPPORT**\n"
                        "✅ Monitor for breakdown or bounce\n"
                        "✅ Watch order flow in Bookmap\n"
                        "✅ Wait for confirmation"
                    )
            
            embed['fields'].append({
                'name': '🎯 Trading Action',
                'value': action,
                'inline': False
            })
            
            # Data source note
            data_source = alert_data.get('data_source', 'unknown')
            source_note = 'Real-time Tradier data' if data_source == 'tradier' else 'Polygon contract data'
            
            embed['footer'] = {
                'text': f"0DTE Gamma Monitor • {source_note} • {datetime.now().strftime('%H:%M:%S ET')}"
            }
            
            # Send to Discord
            payload = {'embeds': [embed]}
            response = requests.post(self.discord_webhook, json=payload, timeout=10)
            response.raise_for_status()
            
            self.logger.info(f"✅ 0DTE alert sent: {symbol} at ${closest['strike']:.2f} ({closest['distance_pct']:.1f}%)")
            self.stats['alerts_sent'] += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending 0DTE alert: {str(e)}")
            self.stats['errors'] += 1
            return False
    
    def run_single_check(self) -> int:
        """
        Run single check of all watchlist symbols
        
        Returns:
            Number of alerts sent
        """
        if not self.enabled:
            self.logger.debug("0DTE monitor disabled")
            return 0
        
        # Check if weekday
        if self.weekdays_only and not self.is_weekday():
            self.logger.debug("Not a weekday, skipping 0DTE check")
            return 0
        
        # Check if within alert window
        if not self.is_alert_time():
            self.logger.debug("Outside alert window (9:00-9:05 AM EST)")
            return 0
        
        # Reset daily tracking if needed
        self.reset_daily_tracking()
        
        # Get watchlist
        try:
            symbols = self.watchlist_manager.load_symbols()
        except Exception as e:
            self.logger.error(f"Error loading watchlist: {str(e)}")
            return 0
        
        self.logger.info(f"🔍 0DTE Gamma Check: {len(symbols)} symbols at {datetime.now().strftime('%H:%M:%S')} EST")
        
        alerts_sent = 0
        
        for symbol in symbols:
            # Skip if already alerted today
            if symbol in self.alerted_today:
                self.logger.debug(f"{symbol}: Already alerted today")
                continue
            
            self.stats['symbols_checked'] += 1
            
            # Check if 0DTE exists
            odte_exists, gamma_data = self.check_odte_exists(symbol)
            
            if not odte_exists:
                continue
            
            # Get current price
            current_price = gamma_data.get('gamma_levels', [{}])[0].get('strike', 0)
            if not current_price:
                quote = self.analyzer.get_real_time_quote(symbol)
                current_price = quote['price']
            
            # Check proximity to gamma walls
            alert_data = self.check_proximity_to_gamma_walls(symbol, current_price, gamma_data)
            
            if not alert_data:
                continue
            
            # Send alert
            success = self.send_alert(alert_data)
            
            if success:
                self.alerted_today.add(symbol)
                alerts_sent += 1
            
            # Small delay between symbols
            time.sleep(0.5)
        
        if alerts_sent > 0:
            self.logger.info(f"✅ 0DTE check complete: {alerts_sent} alerts sent")
        else:
            self.logger.info(f"✅ 0DTE check complete: No proximity matches found")
        
        return alerts_sent
    
    def run_continuous(self):
        """
        Run continuous monitoring
        Checks every minute, only alerts during 9:00-9:05 AM window
        """
        self.logger.info("🚀 Starting 0DTE Gamma Monitor (continuous mode)")
        self.logger.info(f"   🕐 Alert time: {self.alert_time} EST")
        self.logger.info(f"   📏 Proximity: {self.min_proximity_pct}%-{self.max_proximity_pct}%")
        self.logger.info(f"   ⏱️ Alert window: {self.alert_window_minutes} minutes")
        
        try:
            while True:
                try:
                    self.run_single_check()
                except Exception as e:
                    self.logger.error(f"Error in check cycle: {str(e)}")
                    import traceback
                    self.logger.debug(traceback.format_exc())
                    self.stats['errors'] += 1
                
                # Check every 60 seconds
                time.sleep(60)
                
        except KeyboardInterrupt:
            self.logger.info("Stopping 0DTE monitor...")
            self.print_stats()
    
    def print_stats(self):
        """Print monitor statistics"""
        print("\n" + "=" * 60)
        print("0DTE GAMMA MONITOR STATISTICS")
        print("=" * 60)
        print(f"Symbols Checked: {self.stats['symbols_checked']}")
        print(f"0DTE Options Found: {self.stats['odte_found']}")
        print(f"Proximity Matches: {self.stats['proximity_matches']}")
        print(f"Alerts Sent: {self.stats['alerts_sent']}")
        print(f"Errors: {self.stats['errors']}")
        print("=" * 60 + "\n")


def main():
    """Command-line interface for testing"""
    import os
    from dotenv import load_dotenv
    import yaml
    
    load_dotenv()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load config
    config_path = backend_dir / 'config' / 'config.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Get API keys
    polygon_key = os.getenv('POLYGON_API_KEY')
    tradier_key = os.getenv('TRADIER_API_KEY')
    odte_webhook = os.getenv('DISCORD_ODTE_LEVELS')
    
    if not polygon_key:
        print("❌ POLYGON_API_KEY not found")
        return
    
    # Add Tradier key to config if available
    if tradier_key:
        config['tradier_api_key'] = tradier_key
        config['tradier_account_type'] = os.getenv('TRADIER_ACCOUNT_TYPE', 'sandbox')
    
    # Load watchlist
    from utils.watchlist_manager import WatchlistManager
    watchlist_manager = WatchlistManager()
    
    # Initialize monitor
    monitor = ODTEGammaMonitor(
        polygon_api_key=polygon_key,
        config=config,
        watchlist_manager=watchlist_manager
    )
    
    if odte_webhook:
        monitor.set_discord_webhook(odte_webhook)
    
    # Run single check
    print("\n🔍 Running 0DTE Gamma Check...")
    alerts_sent = monitor.run_single_check()
    print(f"\n✅ Check complete: {alerts_sent} alerts sent")
    monitor.print_stats()


if __name__ == '__main__':
    main()
