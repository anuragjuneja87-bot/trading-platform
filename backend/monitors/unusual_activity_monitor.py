"""
backend/monitors/unusual_activity_monitor.py
Unusual Activity Monitor

Background monitor that scans watchlist for unusual options activity
Generates Discord alerts following same patterns as volume_spike and wall_strength monitors

DAY TRADER OPTIMIZED - 5-minute cooldown for frequent updates
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict


class UnusualActivityMonitor:
    def __init__(self, analyzer, detector, config: dict = None):
        """
        Initialize Unusual Activity Monitor
        
        Args:
            analyzer: EnhancedProfessionalAnalyzer instance
            detector: UnusualActivityDetector instance
            config: Configuration dict
        """
        self.logger = logging.getLogger(__name__)
        self.analyzer = analyzer
        self.detector = detector
        self.config = config or {}
        
        # Monitor settings (same pattern as wall_strength_monitor)
        self.enabled = True
        self.check_interval = 30  # 30 seconds (matches main system)
        self.market_hours_only = True
        
        # Cooldown tracking - REDUCED FOR DAY TRADING
        self.cooldown_minutes = 5  # 5 minutes (was 15 - TOO LONG for day trading)
        self._cooldowns = {}  # {symbol_strike_key: datetime}
        
        # Discord webhook
        self.discord_webhook = None
        
        # Statistics
        self.stats = {
            'checks_completed': 0,
            'alerts_generated': 0,
            'symbols_analyzed': 0,
            'unusual_activity_detected': 0,
            'errors': 0
        }
        
        self.logger.info("✅ Unusual Activity Monitor initialized (DAY TRADER MODE)")
        self.logger.info(f"   🕐 Check interval: {self.check_interval} seconds")
        self.logger.info(f"   ⏱️ Alert cooldown: {self.cooldown_minutes} minutes (optimized for day trading)")
        self.logger.info(f"   🏢 Market hours only: {self.market_hours_only}")
    
    def set_discord_webhook(self, webhook_url: str):
        """Set Discord webhook URL"""
        self.discord_webhook = webhook_url
        self.logger.info(f"✅ Discord webhook configured for unusual activity")
    
    def is_market_hours(self) -> bool:
        """Check if currently in market hours (9:30 AM - 4:00 PM ET)"""
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        day_of_week = now.weekday()
        
        # Monday = 0, Friday = 4
        if day_of_week > 4:
            return False
        
        current_minutes = hour * 60 + minute
        market_open = 9 * 60 + 30  # 9:30 AM
        market_close = 16 * 60     # 4:00 PM
        
        return market_open <= current_minutes < market_close
    
    def check_cooldown(self, symbol: str, strike: float, option_type: str) -> bool:
        """
        Check if alert is in cooldown period
        
        Args:
            symbol: Stock symbol
            strike: Strike price
            option_type: 'call' or 'put'
        
        Returns:
            True if should send alert, False if in cooldown
        """
        cooldown_key = f"{symbol}_{strike}_{option_type}"
        
        last_alert = self._cooldowns.get(cooldown_key)
        if last_alert:
            elapsed_minutes = (datetime.now() - last_alert).total_seconds() / 60
            if elapsed_minutes < self.cooldown_minutes:
                self.logger.debug(
                    f"{symbol} ${strike}{option_type[0].upper()}: "
                    f"Cooldown active ({elapsed_minutes:.0f}min ago)"
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
        Following exact pattern from discord_alerter.py
        
        Args:
            alert: Alert dict from detector
        
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
            option_type = alert['option_type']
            oi_change_pct = alert['oi_change_pct']
            volume_ratio = alert['volume_ratio']
            premium_swept = alert['premium_swept']
            classification = alert['classification']
            urgency = alert['urgency']
            score = alert['score']
            
            # Determine color and emoji based on urgency (matching discord_alerter pattern)
            if urgency == 'EXTREME':
                emoji = '🔥🔥'
                color = 0xff0000  # Red
            elif urgency == 'HIGH':
                emoji = '🔥'
                color = 0xff6600  # Orange
            else:
                emoji = '📊'
                color = 0xffff00  # Yellow
            
            # Title
            title = f"{emoji} UNUSUAL ACTIVITY - {symbol}"
            
            # Description
            description = f"**{urgency} PRIORITY** • Score: {score:.1f}/10 ⭐"
            
            # Build embed (exact pattern from discord_alerter)
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
                    f"**Ratio:** {volume_ratio:.1f}x {'🔥' if volume_ratio >= 3 else '⚡' if volume_ratio >= 2 else ''}"
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
                    f"**Total:** {premium_display} {'💰💰' if premium_swept >= 2_000_000 else '💰' if premium_swept >= 500_000 else ''}\n"
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
                    "✅ Review position immediately\n"
                    "✅ Check related strikes\n"
                    "✅ Monitor for continuation\n"
                    "✅ Consider hedge if exposed"
                )
            elif urgency == 'HIGH':
                action = (
                    "⚡ **HIGH PRIORITY**\n"
                    "✅ Monitor closely\n"
                    "✅ Review position sizing\n"
                    "✅ Watch for follow-through\n"
                    "✅ Set alerts for movement"
                )
            else:
                action = (
                    "👀 **WATCH CLOSELY**\n"
                    "✅ Add to active watchlist\n"
                    "✅ Monitor for continuation\n"
                    "✅ Track for trend development"
                )
            
            embed['fields'].append({
                'name': '🎯 Action Items',
                'value': action,
                'inline': False
            })
            
            # Footer (matching discord_alerter pattern)
            embed['footer'] = {
                'text': f'Unusual Activity Scanner • {datetime.now().strftime("%H:%M:%S ET")}'
            }
            
            # Send webhook
            payload = {'embeds': [embed]}
            response = requests.post(self.discord_webhook, json=payload, timeout=10)
            response.raise_for_status()
            
            self.logger.info(
                f"✅ Alert sent: {symbol} ${strike}{option_type[0].upper()} "
                f"({urgency}) Score: {score:.1f}/10"
            )
            
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
        
        # Handle both dict and list formats
        if isinstance(options_data, dict):
            # Check for required keys
            required_keys = ['calls', 'puts']
            if not all(key in options_data for key in required_keys):
                return False
            
            # Check that calls and puts have data
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
            # Get options data from analyzer
            if not hasattr(self.analyzer, 'get_options_chain'):
                self.logger.debug(f"{symbol}: Options chain method not available")
                return 0
            
            options_data = self.analyzer.get_options_chain(symbol)
            
            # Validate options data
            if not self._validate_options_data(options_data):
                self.logger.debug(f"{symbol}: No valid options data available")
                return 0
            
            # Get current price with null safety
            quote = self.analyzer.get_real_time_quote(symbol)
            if not quote:
                self.logger.debug(f"{symbol}: No quote data available")
                return 0
            
            # Safe price extraction with multiple fallbacks
            current_price = self._safe_float(
                quote.get('price') or quote.get('last') or quote.get('regularMarketPrice'),
                default=None
            )
            
            if current_price is None or current_price <= 0:
                self.logger.debug(f"{symbol}: Invalid price data (price={current_price})")
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
            
            # Send alerts for each unusual activity
            alerts_sent = 0
            for alert in result.get('alerts', []):
                # Validate alert has required fields
                required_fields = ['symbol', 'strike', 'option_type']
                if not all(field in alert for field in required_fields):
                    self.logger.warning(f"Alert missing required fields: {alert}")
                    continue
                
                # Ensure strike is valid
                strike = self._safe_float(alert.get('strike'), default=None)
                if strike is None or strike <= 0:
                    self.logger.warning(f"Invalid strike in alert: {alert.get('strike')}")
                    continue
                
                # Update alert with safe strike value
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
        Run single check across watchlist
        
        Args:
            watchlist: List of symbols to check
        
        Returns:
            Number of alerts sent
        """
        if self.market_hours_only and not self.is_market_hours():
            self.logger.debug("Outside market hours, skipping check")
            return 0
        
        self.logger.info(f"🔍 Checking {len(watchlist)} symbols for unusual activity...")
        
        total_alerts = 0
        for symbol in watchlist:
            alerts_sent = self.check_symbol(symbol)
            total_alerts += alerts_sent
            time.sleep(0.5)  # Small delay between symbols
        
        self.stats['checks_completed'] += 1
        
        if total_alerts > 0:
            self.logger.info(f"✅ Check complete: {total_alerts} alerts sent")
        else:
            self.logger.debug(f"Check complete: No unusual activity detected")
        
        return total_alerts
    
    def run_continuous(self, watchlist_manager):
        """
        Run continuous monitoring (called from background thread)
        Following same pattern as wall_strength_monitor
        
        Args:
            watchlist_manager: WatchlistManager instance
        """
        self.logger.info("🚀 Starting Unusual Activity Monitor (DAY TRADER MODE)...")
        self.logger.info(f"   Check interval: {self.check_interval}s")
        self.logger.info(f"   Cooldown: {self.cooldown_minutes}min (optimized for active trading)")
        self.logger.info(f"   Market hours only: {self.market_hours_only}")
        
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