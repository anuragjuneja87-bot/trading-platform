"""
backend/monitors/wall_strength_monitor.py
Wall Strength Monitor - Background Service

Runs every 5 minutes during market hours
Tracks OI/Volume changes at gamma walls
Sends Discord alerts when walls building/weakening
Routes to: DISCORD_ODTE_LEVELS webhook
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import logging
import time
from datetime import datetime
from typing import Dict, List
import pytz


class WallStrengthMonitor:
    def __init__(self, analyzer, wall_tracker, config: dict):
        """
        Initialize Wall Strength Monitor
        
        Args:
            analyzer: EnhancedProfessionalAnalyzer instance
            wall_tracker: WallStrengthTracker instance
            config: Configuration dict from config.yaml
        """
        self.logger = logging.getLogger(__name__)
        self.analyzer = analyzer
        self.wall_tracker = wall_tracker
        self.config = config
        
        # Monitor settings
        self.enabled = True
        self.check_interval = 300  # 5 minutes
        self.market_hours_only = True
        
        # Cooldown to prevent spam (per symbol per strike)
        # REDUCED for 6-figure day trading speed
        self.cooldown_minutes = {
            'WALL_BUILDING': 10,     # 10 min (was 15)
            'WALL_WEAKENING': 7,     # 7 min (was 10)
            'WALL_BROKEN': 3         # 3 min (was 5) - URGENT
        }
        
        self.last_alert_time = {}  # {(symbol, strike, type): timestamp}
        
        # Discord webhook
        self.discord_webhook = None
        
        # Stats
        self.stats = {
            'checks_performed': 0,
            'alerts_sent': 0,
            'symbols_monitored': 0,
            'walls_tracked': 0,
            'errors': 0
        }
        
        self.logger.info("✅ Wall Strength Monitor initialized")
        self.logger.info(f"   🕐 Check interval: {self.check_interval} seconds")
        self.logger.info(f"   ⏱️ Cooldowns: Building={self.cooldown_minutes['WALL_BUILDING']}min, Weakening={self.cooldown_minutes['WALL_WEAKENING']}min")
    
    def set_discord_webhook(self, webhook_url: str):
        """Set Discord webhook URL"""
        self.discord_webhook = webhook_url
        self.logger.info("✅ Discord webhook configured for wall strength alerts")
    
    def is_market_hours(self) -> bool:
        """Check if currently in market hours (9:30 AM - 4:00 PM ET)"""
        et_tz = pytz.timezone('America/New_York')
        now = datetime.now(et_tz)
        
        # Check weekday
        if now.weekday() >= 5:  # Saturday or Sunday
            return False
        
        # Check time
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_open <= now <= market_close
    
    def check_cooldown(self, symbol: str, strike: float, alert_type: str) -> bool:
        """
        Check if alert is in cooldown period
        
        Returns:
            True if can send alert, False if in cooldown
        """
        key = (symbol, strike, alert_type)
        
        if key not in self.last_alert_time:
            return True
        
        last_alert = self.last_alert_time[key]
        cooldown_seconds = self.cooldown_minutes.get(alert_type, 15) * 60
        
        elapsed = (datetime.now() - last_alert).total_seconds()
        
        return elapsed >= cooldown_seconds
    
    def send_discord_alert(self, alert: Dict) -> bool:
        """
        Send wall strength alert to Discord
        
        Args:
            alert: Alert dict from wall tracker
        
        Returns:
            True if sent successfully
        """
        if not self.discord_webhook:
            self.logger.warning("Discord webhook not configured")
            return False
        
        try:
            import requests
            
            symbol = alert['symbol']
            strike = alert['strike']
            wall_type = alert['wall_type']
            change_pct = alert['change_pct']
            urgency = alert['urgency']
            emoji = alert['emoji']
            timeline = alert['timeline']
            distance_pct = alert['distance_pct']
            
            # Determine color based on alert type
            if alert['type'] == 'WALL_BUILDING':
                if urgency == 'VERY_STRONG':
                    color = 0x00ff00  # Bright green
                elif urgency == 'STRONG':
                    color = 0x00cc00  # Green
                else:
                    color = 0x009900  # Dark green
            else:  # WALL_WEAKENING
                if urgency == 'BREAKING':
                    color = 0xff0000  # Red
                elif urgency == 'MODERATE':
                    color = 0xff6600  # Orange
                else:
                    color = 0xffaa00  # Yellow
            
            # Direction emoji
            dir_emoji = '⬆️' if wall_type == 'RESISTANCE' else '⬇️'
            
            # Title
            if alert['type'] == 'WALL_BUILDING':
                title = f"{emoji} GAMMA WALL BUILDING - {symbol} {dir_emoji}"
            else:
                title = f"{emoji} GAMMA WALL WEAKENING - {symbol} {dir_emoji}"
            
            # Description
            description = f"**${strike:.2f} {wall_type}** - {urgency.replace('_', ' ')} change detected"
            
            embed = {
                'title': title,
                'description': description,
                'color': color,
                'timestamp': datetime.utcnow().isoformat(),
                'fields': []
            }
            
            # OI Change
            embed['fields'].append({
                'name': '📊 Open Interest Change',
                'value': f"**{change_pct:+.1f}%** from baseline",
                'inline': True
            })
            
            # Distance from current price
            embed['fields'].append({
                'name': '📍 Distance',
                'value': f"**{abs(distance_pct):.1f}%** from current price",
                'inline': True
            })
            
            # Wall Type
            embed['fields'].append({
                'name': f'{dir_emoji} Wall Type',
                'value': f"**{wall_type}**",
                'inline': True
            })
            
            # Timeline
            if len(timeline) >= 2:
                timeline_text = []
                for entry in timeline:
                    change_emoji = ''
                    if entry['change_pct'] >= 50:
                        change_emoji = ' 🔥🔥🔥'
                    elif entry['change_pct'] >= 25:
                        change_emoji = ' 🔥🔥'
                    elif entry['change_pct'] <= -25:
                        change_emoji = ' ⚠️⚠️'
                    elif entry['change_pct'] <= -15:
                        change_emoji = ' ⚠️'
                    
                    timeline_text.append(
                        f"`{entry['time']}` → **{entry['oi']:,} OI** "
                        f"({entry['change_pct']:+.1f}%){change_emoji}"
                    )
                
                embed['fields'].append({
                    'name': '⏱️ Timeline',
                    'value': '\n'.join(timeline_text),
                    'inline': False
                })
            
            # Trading action
            if alert['type'] == 'WALL_BUILDING':
                if wall_type == 'RESISTANCE':
                    action = (
                        "🔴 **RESISTANCE STRENGTHENING**\n"
                        "✅ Expect rejection at this level\n"
                        "✅ Consider fade/short setup\n"
                        "✅ Watch for breakdown if weakens"
                    )
                else:  # SUPPORT
                    action = (
                        "🟢 **SUPPORT STRENGTHENING**\n"
                        "✅ Expect bounce at this level\n"
                        "✅ Consider long setup on dip\n"
                        "✅ Watch for breakdown if weakens"
                    )
            else:  # WALL_WEAKENING
                if wall_type == 'RESISTANCE':
                    action = (
                        "⚠️ **RESISTANCE WEAKENING**\n"
                        "✅ Potential breakout setup\n"
                        "✅ Watch for volume confirmation\n"
                        "✅ Prepare for upside move"
                    )
                else:  # SUPPORT
                    action = (
                        "⚠️ **SUPPORT WEAKENING**\n"
                        "✅ Potential breakdown setup\n"
                        "✅ Watch for volume confirmation\n"
                        "✅ Prepare for downside move"
                    )
            
            embed['fields'].append({
                'name': '🎯 Trading Action',
                'value': action,
                'inline': False
            })
            
            # Footer
            embed['footer'] = {
                'text': f'Wall Strength Monitor • {datetime.now().strftime("%H:%M:%S ET")}'
            }
            
            # Send to Discord
            payload = {'embeds': [embed]}
            response = requests.post(self.discord_webhook, json=payload, timeout=10)
            response.raise_for_status()
            
            self.logger.info(f"✅ Wall strength alert sent: {symbol} ${strike:.2f} ({change_pct:+.1f}%)")
            self.stats['alerts_sent'] += 1
            
            # Update last alert time
            key = (symbol, strike, alert['type'])
            self.last_alert_time[key] = datetime.now()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending Discord alert: {str(e)}")
            self.stats['errors'] += 1
            return False
    
    def run_single_check(self, watchlist: List[str]) -> int:
        """
        Run single check of all watchlist symbols
        
        Args:
            watchlist: List of symbols to check
        
        Returns:
            Number of alerts sent
        """
        if not self.enabled:
            self.logger.debug("Wall strength monitor disabled")
            return 0
        
        # Check if market hours (if required)
        if self.market_hours_only and not self.is_market_hours():
            self.logger.debug("Outside market hours, skipping check")
            return 0
        
        self.logger.info(f"🔍 Wall Strength Check: {len(watchlist)} symbols at {datetime.now().strftime('%H:%M:%S')}")
        
        self.stats['checks_performed'] += 1
        alerts_sent = 0
        
        for symbol in watchlist:
            try:
                # Get current price
                quote = self.analyzer.get_real_time_quote(symbol)
                current_price = quote['price']
                
                if current_price == 0:
                    continue
                
                # Get gamma analysis (using Tradier if available)
                gamma_data = self.analyzer.analyze_open_interest(symbol, current_price)
                
                if not gamma_data.get('available'):
                    continue
                
                # Track wall strength
                result = self.wall_tracker.track_wall_strength(symbol, current_price, gamma_data)
                
                if not result.get('available'):
                    continue
                
                self.stats['symbols_monitored'] += 1
                self.stats['walls_tracked'] += result.get('walls_tracked', 0)
                
                # Send alerts
                alerts = result.get('alerts', [])
                
                for alert in alerts:
                    # Check cooldown
                    if not self.check_cooldown(alert['symbol'], alert['strike'], alert['type']):
                        self.logger.debug(f"Alert in cooldown: {alert['symbol']} ${alert['strike']}")
                        continue
                    
                    # Send Discord alert
                    success = self.send_discord_alert(alert)
                    
                    if success:
                        alerts_sent += 1
                
                # Small delay between symbols
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Error checking {symbol}: {str(e)}")
                self.stats['errors'] += 1
                continue
        
        if alerts_sent > 0:
            self.logger.info(f"✅ Wall strength check complete: {alerts_sent} alerts sent")
        else:
            self.logger.info(f"✅ Wall strength check complete: No significant changes detected")
        
        return alerts_sent
    
    def run_continuous(self, watchlist_manager):
        """
        Run continuous monitoring
        
        Args:
            watchlist_manager: WatchlistManager instance
        """
        self.logger.info("🚀 Starting Wall Strength Monitor (continuous mode)")
        self.logger.info(f"   🕐 Check interval: {self.check_interval} seconds")
        self.logger.info(f"   🏢 Market hours only: {self.market_hours_only}")
        
        try:
            while True:
                try:
                    # Load watchlist
                    watchlist = watchlist_manager.load_symbols()
                    
                    # Run check
                    self.run_single_check(watchlist)
                    
                except Exception as e:
                    self.logger.error(f"Error in check cycle: {str(e)}")
                    import traceback
                    self.logger.debug(traceback.format_exc())
                    self.stats['errors'] += 1
                
                # Wait for next check
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            self.logger.info("Stopping wall strength monitor...")
            self.print_stats()
    
    def print_stats(self):
        """Print monitor statistics"""
        print("\n" + "=" * 60)
        print("WALL STRENGTH MONITOR STATISTICS")
        print("=" * 60)
        print(f"Checks Performed: {self.stats['checks_performed']}")
        print(f"Symbols Monitored: {self.stats['symbols_monitored']}")
        print(f"Walls Tracked: {self.stats['walls_tracked']}")
        print(f"Alerts Sent: {self.stats['alerts_sent']}")
        print(f"Errors: {self.stats['errors']}")
        print("=" * 60 + "\n")