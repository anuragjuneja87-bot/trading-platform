"""
backend/monitors/unusual_activity_monitor.py
Unusual Activity Monitor - PROFESSIONAL DAY TRADER EDITION

OPTIMIZED FOR:
- Speed > Everything
- First 2 hours priority (9:30-11:30 AM)
- Pre-market monitoring (8:00 AM start)
- Smart cooldown (2 min during prime hours)
- Priority symbol handling
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict


class UnusualActivityMonitor:
    def __init__(self, analyzer, detector, discord_alerter=None, config: dict = None):
        """
        Initialize Unusual Activity Monitor - PROFESSIONAL MODE
        
        Args:
            analyzer: EnhancedProfessionalAnalyzer instance
            detector: UnusualActivityDetector instance
            discord_alerter: DiscordAlerter instance (modern pattern)
            config: Configuration dict
        """
        self.logger = logging.getLogger(__name__)
        self.analyzer = analyzer
        self.detector = detector
        self.discord_alerter = discord_alerter
        self.config = config or {}
        
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
        
        # Discord webhook (legacy - kept for backwards compatibility)
        self.discord_webhook = None
        
        # Statistics
        self.stats = {
            'checks_completed': 0,
            'alerts_generated': 0,
            'symbols_analyzed': 0,
            'unusual_activity_detected': 0,
            'errors': 0,
            'prime_hours_alerts': 0,
            'premarket_alerts': 0
        }
        
        self.logger.info("✅ Unusual Activity Monitor - PROFESSIONAL MODE")
        self.logger.info(f"   ⚡ SPEED: {self.check_interval}s checks (AGGRESSIVE)")
        self.logger.info(f"   ⏱️ Cooldown: {self.cooldown_prime_hours}min (prime) / {self.cooldown_normal}min (normal)")
        self.logger.info(f"   🎯 Priority: {len(self.priority_symbols)} symbols checked first")
        self.logger.info(f"   🌅 Pre-market: Monitoring from 8:00 AM")
    
    def set_discord_webhook(self, webhook_url: str):
        """Set Discord webhook URL"""
        self.discord_webhook = webhook_url
        self.logger.info(f"✅ Discord webhook configured for unusual activity")
    
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
    
    def send_discord_alert(self, alert: Dict) -> bool:
        """
        Send unusual activity alert to Discord
        Professional formatting with priority indicators
        
        Args:
            alert: Alert dict from detector
        
        Returns:
            True if sent successfully
        """
        # Use discord_alerter if available, otherwise fallback to webhook
        if not self.discord_alerter and not self.discord_webhook:
            self.logger.warning("Discord alerter/webhook not configured")
            return False
        
        try:
            import requests
            
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
            embed['fields'].append({
                'name': '📈 Price Relationship',
                'value': (
                    f"**Distance:** ${alert['distance_from_price']:+.2f} ({alert['distance_pct']:+.1f}%)\n"
                    f"**Status:** {'OTM' if abs(alert['distance_pct']) > 2 else 'ATM' if abs(alert['distance_pct']) < 1 else 'Near-Money'}"
                ),
                'inline': True
            })
            
            # Greeks if available
            if 'delta' in alert.get('greeks', {}) and alert['greeks']['delta'] is not None:
                embed['fields'].append({
                    'name': '🎲 Greeks',
                    'value': (
                        f"**Delta:** {alert['greeks']['delta']:.3f}\n"
                        f"**Gamma:** {alert['greeks'].get('gamma', 0):.4f}\n"
                        f"**IV:** {alert['greeks'].get('iv', 0):.1f}%"
                    ),
                    'inline': True
                })
            
            # Action items based on urgency
            if urgency == 'EXTREME':
                action = (
                    "🚨 **IMMEDIATE ACTION REQUIRED**\n"
                    "✅ Review position NOW\n"
                    "✅ Check Bookmap for confirmation\n"
                    "✅ Monitor for continuation\n"
                    "✅ Consider position sizing"
                )
            elif urgency == 'HIGH':
                action = (
                    "⚡ **HIGH PRIORITY - Act Fast**\n"
                    "✅ Open Bookmap confirmation\n"
                    "✅ Watch for follow-through\n"
                    "✅ Set price alerts\n"
                    "✅ Review related strikes"
                )
            else:
                action = (
                    "👀 **WATCH CLOSELY**\n"
                    "✅ Add to active watchlist\n"
                    "✅ Monitor for trend\n"
                    "✅ Track OI changes"
                )
            
            embed['fields'].append({
                'name': '🎯 Action Items',
                'value': action,
                'inline': False
            })
            
            # Footer
            now = datetime.now()
            time_str = now.strftime("%H:%M:%S ET")
            
            # Add market phase indicator
            if self.is_prime_hours():
                phase = "PRIME HOURS 🎯"
            elif now.hour < 9 or (now.hour == 9 and now.minute < 30):
                phase = "PRE-MARKET 🌅"
            else:
                phase = "REGULAR HOURS"
            
            embed['footer'] = {
                'text': f'Professional Unusual Activity Scanner • {time_str} • {phase}'
            }
            
            # Send via discord_alerter if available, otherwise use webhook
            if self.discord_alerter:
                # Modern pattern - use DiscordAlerter
                self.discord_alerter.send_embed(
                    title=title,
                    description=description,
                    fields=embed['fields'],
                    color=color,
                    footer_text=embed['footer']['text'],
                    channel='unusual_activity'
                )
            else:
                # Legacy pattern - use raw webhook
                import requests
                payload = {'embeds': [embed]}
                response = requests.post(self.discord_webhook, json=payload, timeout=10)
                response.raise_for_status()
            
            self.logger.info(
                f"✅ Alert sent: {symbol} ${strike}{option_type[0].upper()} "
                f"({urgency}) Score: {score:.1f}/10"
            )
            
            # Track prime hours alerts
            if self.is_prime_hours():
                self.stats['prime_hours_alerts'] += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Discord alert failed: {str(e)}")
            self.stats['errors'] += 1
            return False
    
    def _safe_float(self, value, default=0.0) -> float:
        """Safely convert value to float with proper null handling"""
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    
    def _validate_options_data(self, options_data) -> bool:
        """Validate that options data has required fields"""
        if not options_data:
            return False
        
        if isinstance(options_data, dict):
            required_keys = ['calls', 'puts']
            if not all(key in options_data for key in required_keys):
                return False
            
            if not options_data['calls'] and not options_data['puts']:
                return False
        
        elif isinstance(options_data, list):
            if len(options_data) == 0:
                return False
        
        return True
    
    def check_symbol(self, symbol: str) -> int:
        """
        Check one symbol for unusual activity
        
        Args:
            symbol: Stock symbol to check
        
        Returns:
            Number of alerts generated
        """
        try:
            # Get options data
            if not hasattr(self.analyzer, 'get_options_chain'):
                self.logger.debug(f"{symbol}: Options chain method not available")
                return 0
            
            options_data = self.analyzer.get_options_chain(symbol)
            
            if not self._validate_options_data(options_data):
                self.logger.debug(f"{symbol}: No valid options data")
                return 0
            
            # Get current price
            quote = self.analyzer.get_real_time_quote(symbol)
            if not quote:
                self.logger.debug(f"{symbol}: No quote data")
                return 0
            
            current_price = self._safe_float(
                quote.get('price') or quote.get('last') or quote.get('regularMarketPrice'),
                default=None
            )
            
            if current_price is None or current_price <= 0:
                self.logger.debug(f"{symbol}: Invalid price ({current_price})")
                return 0
            
            # Analyze for unusual activity
            result = self.detector.analyze_unusual_activity(
                symbol,
                options_data,
                current_price
            )
            
            self.stats['symbols_analyzed'] += 1
            
            if not result.get('detected'):
                return 0
            
            self.stats['unusual_activity_detected'] += 1
            
            # Send alerts
            alerts_sent = 0
            for alert in result.get('alerts', []):
                # Validate alert
                required_fields = ['symbol', 'strike', 'option_type']
                if not all(field in alert for field in required_fields):
                    self.logger.warning(f"Alert missing required fields: {alert}")
                    continue
                
                strike = self._safe_float(alert.get('strike'), default=None)
                if strike is None or strike <= 0:
                    self.logger.warning(f"Invalid strike: {alert.get('strike')}")
                    continue
                
                alert['strike'] = strike
                
                # Check cooldown
                if not self.check_cooldown(
                    alert['symbol'],
                    strike,
                    alert['option_type']
                ):
                    continue
                
                # Send Discord alert
                if self.send_discord_alert(alert):
                    self.record_alert(
                        alert['symbol'],
                        strike,
                        alert['option_type']
                    )
                    alerts_sent += 1
                    self.stats['alerts_generated'] += 1
            
            return alerts_sent
            
        except Exception as e:
            self.logger.error(f"Error checking {symbol}: {str(e)}", exc_info=True)
            self.stats['errors'] += 1
            return 0
    
    def run_single_check(self, watchlist: List[str]) -> int:
        """
        Run single check with priority symbol handling
        
        Args:
            watchlist: List of symbols to check
        
        Returns:
            Number of alerts sent
        """
        if self.market_hours_only and not self.is_market_hours():
            self.logger.debug("Outside market hours, skipping check")
            return 0
        
        # Separate priority vs normal symbols
        priority = [s for s in watchlist if s in self.priority_symbols]
        normal = [s for s in watchlist if s not in self.priority_symbols]
        
        # Check priority symbols first
        sorted_watchlist = priority + normal
        
        prime_indicator = " 🎯 PRIME HOURS" if self.is_prime_hours() else ""
        self.logger.info(
            f"🔍 Checking {len(sorted_watchlist)} symbols "
            f"({len(priority)} priority){prime_indicator}..."
        )
        
        total_alerts = 0
        for symbol in sorted_watchlist:
            alerts_sent = self.check_symbol(symbol)
            total_alerts += alerts_sent
            time.sleep(0.2)  # Fast iteration (was 0.5s)
        
        self.stats['checks_completed'] += 1
        
        if total_alerts > 0:
            self.logger.info(f"✅ Check complete: {total_alerts} alerts sent")
        else:
            self.logger.debug(f"Check complete: No unusual activity detected")
        
        return total_alerts
    
    def run_continuous(self, watchlist_manager):
        """
        Run continuous monitoring - PROFESSIONAL SPEED MODE
        
        Args:
            watchlist_manager: WatchlistManager instance
        """
        self.logger.info("🚀 Starting Unusual Activity Monitor - PROFESSIONAL MODE")
        self.logger.info(f"   ⚡ Check interval: {self.check_interval}s (AGGRESSIVE)")
        self.logger.info(f"   ⏱️ Cooldown: {self.cooldown_prime_hours}min (prime) / {self.cooldown_normal}min (normal)")
        self.logger.info(f"   🌅 Extended hours: 8:00 AM - 4:00 PM")
        self.logger.info(f"   🎯 Priority symbols: {', '.join(sorted(self.priority_symbols))}")
        
        try:
            while self.enabled:
                try:
                    # Load current watchlist
                    watchlist = watchlist_manager.load_symbols()
                    
                    # Run check
                    self.run_single_check(watchlist)
                    
                    # Sleep until next check
                    time.sleep(self.check_interval)
                    
                except Exception as e:
                    self.logger.error(f"Error in monitoring loop: {str(e)}", exc_info=True)
                    self.stats['errors'] += 1
                    time.sleep(60)  # Wait 1 minute on error
                    
        except KeyboardInterrupt:
            self.logger.info("⏹️ Unusual Activity Monitor stopped")
        except Exception as e:
            self.logger.error(f"❌ Fatal error in monitor: {str(e)}", exc_info=True)
    
    def get_statistics(self) -> Dict:
        """Get monitor statistics"""
        return {
            **self.stats,
            'priority_symbols': list(self.priority_symbols),
            'cooldown_prime': self.cooldown_prime_hours,
            'cooldown_normal': self.cooldown_normal,
            'check_interval': self.check_interval
        }