"""
backend/monitors/unusual_activity_monitor.py v2.0
ENHANCED Unusual Activity Monitor - Day Trading Edition

IMPROVEMENTS v2.0:
- Fixed Discord webhook access (works with DiscordAlerter)
- Rate limit protection with retries
- Smart cooldown (2 min prime hours, 5 min normal)
- Pre-market monitoring from 8:00 AM
- Priority symbols checked first
- 15 second check interval (AGGRESSIVE)

UNCHANGED (Already Good):
- UnusualActivityDetector thresholds are already aggressive
- 5% OI change, 1.2x volume ratio, $100k premium
- Prime hours detection (9:30-11:30 AM)
- Professional scoring system

Routes to: DISCORD_UNUSUAL_ACTIVITY channel
"""

import logging
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict


class UnusualActivityMonitor:
    def __init__(self, analyzer, detector, config: dict = None, discord_alerter=None):
        """
        Initialize ENHANCED Unusual Activity Monitor v2.0
        
        Args:
            analyzer: EnhancedProfessionalAnalyzer instance
            detector: UnusualActivityDetector instance
            config: Configuration dict
            discord_alerter: DiscordAlerter instance (NEW)
        """
        self.logger = logging.getLogger(__name__)
        self.analyzer = analyzer
        self.detector = detector
        self.config = config or {}
        self.discord = discord_alerter  # NEW: Use DiscordAlerter
        
        # PROFESSIONAL SETTINGS - Speed optimized
        self.enabled = True
        self.check_interval = 15  # 15 seconds (FAST)
        self.market_hours_only = True
        
        # SMART COOLDOWN - Different for prime hours
        self.cooldown_prime_hours = 2   # 2 min during 9:30-11:30 AM
        self.cooldown_normal = 5        # 5 min rest of day
        self._cooldowns = {}
        
        # PRIORITY SYMBOLS - Check these first
        self.priority_symbols = {'SPY', 'QQQ', 'NVDA', 'TSLA', 'AAPL', 'PLTR', 'ORCL'}
        
        # Statistics
        self.stats = {
            'checks_completed': 0,
            'alerts_generated': 0,
            'symbols_analyzed': 0,
            'unusual_activity_detected': 0,
            'errors': 0,
            'prime_hours_alerts': 0,
            'premarket_alerts': 0,
            'rate_limited': 0
        }
        
        self.logger.info("✅ Unusual Activity Monitor v2.0 - PROFESSIONAL MODE")
        self.logger.info(f"   ⚡ SPEED: {self.check_interval}s checks (AGGRESSIVE)")
        self.logger.info(f"   ⏱️ Cooldown: {self.cooldown_prime_hours}min (prime) / {self.cooldown_normal}min (normal)")
        self.logger.info(f"   🎯 Priority: {len(self.priority_symbols)} symbols checked first")
        self.logger.info(f"   🌅 Pre-market: Monitoring from 8:00 AM")
    
    def get_discord_webhook(self) -> Optional[str]:
        """
        Get Discord webhook URL from DiscordAlerter
        Tries multiple methods to find the webhook
        """
        if not self.discord:
            return None
        
        # Try different ways to access webhook
        if hasattr(self.discord, 'webhooks'):
            return self.discord.webhooks.get('unusual_activity')
        elif hasattr(self.discord, 'config'):
            return self.discord.config.get('webhook_unusual_activity')
        elif hasattr(self.discord, 'webhook_unusual_activity'):
            return self.discord.webhook_unusual_activity
        
        return None
    
    def is_market_hours(self) -> bool:
        """Extended hours: Pre-market + Regular hours (8:00 AM - 4:00 PM ET)"""
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        day_of_week = now.weekday()
        
        # Monday = 0, Friday = 4
        if day_of_week > 4:
            return False
        
        current_minutes = hour * 60 + minute
        premarket_start = 8 * 60        # 8:00 AM (pre-market monitoring)
        market_close = 16 * 60          # 4:00 PM
        
        return premarket_start <= current_minutes < market_close
    
    def is_prime_hours(self) -> bool:
        """Check if in prime trading hours (9:30-11:30 AM)"""
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        current_minutes = hour * 60 + minute
        
        prime_start = 9 * 60 + 30   # 9:30 AM
        prime_end = 11 * 60 + 30    # 11:30 AM
        
        return prime_start <= current_minutes < prime_end
    
    def check_cooldown(self, symbol: str, strike: float, option_type: str) -> bool:
        """
        Smart cooldown - Shorter during prime hours
        
        Args:
            symbol: Stock symbol
            strike: Strike price
            option_type: 'call' or 'put'
        
        Returns:
            True if should send alert, False if in cooldown
        """
        cooldown_key = f"{symbol}_{strike}_{option_type}"
        
        # Determine cooldown period based on time
        if self.is_prime_hours():
            cooldown_minutes = self.cooldown_prime_hours  # 2 min
        else:
            cooldown_minutes = self.cooldown_normal       # 5 min
        
        last_alert = self._cooldowns.get(cooldown_key)
        if last_alert:
            elapsed_minutes = (datetime.now() - last_alert).total_seconds() / 60
            if elapsed_minutes < cooldown_minutes:
                self.logger.debug(
                    f"{symbol} ${strike}{option_type[0].upper()}: "
                    f"Cooldown active ({elapsed_minutes:.0f}min ago, need {cooldown_minutes}min)"
                )
                return False
        
        return True
    
    def record_alert(self, symbol: str, strike: float, option_type: str):
        """Record alert timestamp for cooldown tracking"""
        cooldown_key = f"{symbol}_{strike}_{option_type}"
        self._cooldowns[cooldown_key] = datetime.now()
    
    def send_alert_with_retry(self, webhook_url: str, payload: dict, max_retries: int = 3) -> bool:
        """Send Discord alert with rate limit protection and retry logic"""
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                response = requests.post(webhook_url, json=payload, timeout=10)
                response.raise_for_status()
                return True
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limited
                    self.stats['rate_limited'] += 1
                    if attempt < max_retries - 1:
                        self.logger.warning(f"Discord rate limited, retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        self.logger.error(f"Discord rate limit exceeded after {max_retries} attempts")
                        return False
                else:
                    self.logger.error(f"Discord webhook error: {e}")
                    return False
            except Exception as e:
                self.logger.error(f"Error sending Discord alert: {str(e)}")
                return False
        
        return False
    
    def send_discord_alert(self, alert: Dict) -> bool:
        """
        Send unusual activity alert to Discord with professional formatting
        
        Args:
            alert: Alert dict from detector
        
        Returns:
            True if sent successfully
        """
        webhook_url = self.get_discord_webhook()
        
        if not webhook_url:
            self.logger.warning("Discord webhook not configured for unusual activity")
            return False
        
        try:
            symbol = alert['symbol']
            strike = alert['strike']
            option_type = alert['option_type']
            oi_change_pct = alert['oi_change_pct']
            volume_ratio = alert['volume_ratio']
            premium_swept = alert['premium_swept']
            classification = alert['classification']
            urgency = alert['urgency']
            score = alert['score']
            
            # Determine color and emoji based on urgency
            if urgency == 'EXTREME':
                emoji = '🚨🔥🔥'
                color = 0xff0000  # Red
            elif urgency == 'HIGH':
                emoji = '🔥⚡'
                color = 0xff6600  # Orange
            else:
                emoji = '📊⚡'
                color = 0xffff00  # Yellow
            
            # Add PRIME HOURS indicator
            time_indicator = ""
            if self.is_prime_hours():
                time_indicator = " • 🎯 PRIME HOURS"
                self.stats['prime_hours_alerts'] += 1
            elif datetime.now().hour < 9 or (datetime.now().hour == 9 and datetime.now().minute < 30):
                time_indicator = " • 🌅 PRE-MARKET"
                self.stats['premarket_alerts'] += 1
            
            # Title
            title = f"{emoji} UNUSUAL ACTIVITY - {symbol}{time_indicator}"
            
            # Description with score
            description = f"**{urgency} PRIORITY** • Score: {score:.1f}/10 ⭐"
            
            # Build embed
            embed = {
                'title': title,
                'description': description,
                'color': color,
                'timestamp': datetime.utcnow().isoformat(),
                'fields': []
            }
            
            # Strike info
            strike_display = f"${strike} {option_type.upper()}"
            embed['fields'].append({
                'name': '📍 Strike & Type',
                'value': (
                    f"**Strike:** {strike_display}\n"
                    f"**Classification:** {classification.replace('_', ' ')}\n"
                    f"**Score:** {score:.1f}/10"
                ),
                'inline': True
            })
            
            # OI metrics
            embed['fields'].append({
                'name': '📊 Open Interest',
                'value': (
                    f"**Current OI:** {alert['oi']:,}\n"
                    f"**Change:** {alert['oi_change']:+,} ({oi_change_pct:+.1f}%)\n"
                    f"**Status:** {'INCREASING 📈' if alert['oi_change'] > 0 else 'DECREASING 📉'}"
                ),
                'inline': True
            })
            
            # Volume metrics
            embed['fields'].append({
                'name': '📦 Volume Activity',
                'value': (
                    f"**Current Volume:** {alert['volume']:,}\n"
                    f"**Average Volume:** {alert['avg_volume']:,.0f}\n"
                    f"**Ratio:** {volume_ratio:.1f}x {'🔥🔥' if volume_ratio >= 2 else '🔥' if volume_ratio >= 1.5 else '⚡'}"
                ),
                'inline': True
            })
            
            # Premium swept
            if premium_swept >= 1_000_000:
                premium_display = f"${premium_swept/1_000_000:.2f}M"
            elif premium_swept >= 1_000:
                premium_display = f"${premium_swept/1_000:.0f}K"
            else:
                premium_display = f"${premium_swept:.0f}"
            
            embed['fields'].append({
                'name': '💰 Premium Swept',
                'value': (
                    f"**Total:** {premium_display} {'💰💰💰' if premium_swept >= 1_000_000 else '💰💰' if premium_swept >= 500_000 else '💰'}\n"
                    f"**Last Price:** ${alert['last_price']:.2f}\n"
                    f"**Contracts:** {alert['volume']:,}"
                ),
                'inline': True
            })
            
            # Price relationship
            distance_pct = alert['distance_pct']
            if abs(distance_pct) <= 2:
                proximity = "🎯 AT THE MONEY"
            elif abs(distance_pct) <= 5:
                proximity = "📍 NEAR THE MONEY"
            elif distance_pct > 0:
                proximity = "📈 OUT OF THE MONEY"
            else:
                proximity = "📉 IN THE MONEY"
            
            embed['fields'].append({
                'name': '🎯 Strike Position',
                'value': (
                    f"**Distance:** {distance_pct:+.1f}%\n"
                    f"**Position:** {proximity}"
                ),
                'inline': True
            })
            
            # Time detection
            embed['fields'].append({
                'name': '⏰ Detection Time',
                'value': datetime.now().strftime('%I:%M:%S %p ET'),
                'inline': True
            })
            
            # Add action guidance based on classification
            if urgency == 'EXTREME':
                embed['fields'].append({
                    'name': '⚠️ Institutional Alert',
                    'value': (
                        '**EXTREME unusual activity detected!**\n'
                        '• Large institutional flow\n'
                        '• Monitor price action closely\n'
                        '• Check for catalysts/news'
                    ),
                    'inline': False
                })
            elif urgency == 'HIGH' and self.is_prime_hours():
                embed['fields'].append({
                    'name': '👀 Prime Hours Activity',
                    'value': (
                        '**High activity during prime trading hours**\n'
                        '• Smart money may be positioning\n'
                        '• Watch for confirmation in price action'
                    ),
                    'inline': False
                })
            
            embed['footer'] = {
                'text': f'Unusual Activity Monitor v2.0 • Professional mode • Score: {score:.1f}/10'
            }
            
            payload = {'embeds': [embed]}
            
            # Send with retry logic
            success = self.send_alert_with_retry(webhook_url, payload)
            
            if success:
                self.stats['alerts_generated'] += 1
                self.logger.info(
                    f"✅ Unusual activity alert sent: {symbol} ${strike}{option_type[0].upper()} | "
                    f"{urgency} | Score: {score:.1f}/10"
                )
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending Discord alert: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False
    
    def check_symbol(self, symbol: str) -> List[Dict]:
        """
        Check single symbol for unusual activity
        
        Returns:
            List of alerts sent
        """
        try:
            self.stats['symbols_analyzed'] += 1
            
            # Get options data from analyzer
            options_data = self.analyzer.get_options_chain(symbol)
            
            if not options_data:
                return []
            
            # Get current price
            current_price = self.analyzer.get_current_price(symbol)
            
            if not current_price:
                return []
            
            # Capture snapshot
            self.detector.capture_snapshot(symbol, options_data, current_price)
            
            # Detect unusual activity
            unusual_activities = self.detector.detect_unusual_activity(symbol)
            
            if not unusual_activities:
                return []
            
            self.stats['unusual_activity_detected'] += len(unusual_activities)
            
            # Send alerts (with cooldown check)
            alerts_sent = []
            for alert in unusual_activities:
                strike = alert['strike']
                option_type = alert['option_type']
                
                # Check cooldown
                if not self.check_cooldown(symbol, strike, option_type):
                    continue
                
                # Send alert
                success = self.send_discord_alert(alert)
                
                if success:
                    self.record_alert(symbol, strike, option_type)
                    alerts_sent.append(alert)
            
            return alerts_sent
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"Error checking {symbol}: {str(e)}")
            return []
    
    def run_single_check(self, watchlist: List[str]) -> int:
        """
        Run single check cycle on watchlist
        
        Returns:
            Number of alerts sent
        """
        if not self.enabled:
            return 0
        
        if self.market_hours_only and not self.is_market_hours():
            return 0
        
        self.stats['checks_completed'] += 1
        
        # Separate priority and regular symbols
        priority = [s for s in watchlist if s in self.priority_symbols]
        regular = [s for s in watchlist if s not in self.priority_symbols]
        
        # Check priority symbols first
        ordered_watchlist = priority + regular
        
        total_alerts = 0
        
        for symbol in ordered_watchlist:
            alerts = self.check_symbol(symbol)
            total_alerts += len(alerts)
            
            # Small delay between symbols
            time.sleep(0.3)
        
        return total_alerts
    
    def run_continuous(self, watchlist: List[str]):
        """Run continuous monitoring"""
        self.logger.info("🚀 Starting Unusual Activity Monitor v2.0 (continuous mode)")
        
        try:
            while self.enabled:
                try:
                    if self.market_hours_only and not self.is_market_hours():
                        time.sleep(60)
                        continue
                    
                    alerts_sent = self.run_single_check(watchlist)
                    
                    if alerts_sent > 0:
                        session = "PRIME HOURS" if self.is_prime_hours() else "REGULAR"
                        self.logger.info(
                            f"✅ Check complete: {alerts_sent} alerts sent [{session}]"
                        )
                    
                    time.sleep(self.check_interval)
                    
                except Exception as e:
                    self.logger.error(f"Error in check cycle: {str(e)}")
                    import traceback
                    self.logger.debug(traceback.format_exc())
                    time.sleep(30)
                    
        except KeyboardInterrupt:
            self.logger.info("Stopping unusual activity monitor...")
            self.print_stats()
    
    def print_stats(self):
        """Print monitor statistics"""
        print("\n" + "=" * 60)
        print("UNUSUAL ACTIVITY MONITOR STATISTICS")
        print("=" * 60)
        print(f"Checks Completed: {self.stats['checks_completed']}")
        print(f"Symbols Analyzed: {self.stats['symbols_analyzed']}")
        print(f"Unusual Activity Detected: {self.stats['unusual_activity_detected']}")
        print(f"Alerts Sent: {self.stats['alerts_generated']}")
        print(f"Prime Hours Alerts: {self.stats['prime_hours_alerts']}")
        print(f"Pre-market Alerts: {self.stats['premarket_alerts']}")
        print(f"Rate Limited: {self.stats['rate_limited']}")
        print(f"Errors: {self.stats['errors']}")
        print("=" * 60 + "\n")