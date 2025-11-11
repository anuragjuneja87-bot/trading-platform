"""
backend/monitors/opening_range_monitor.py
Opening Range Monitor - Catches OR breakouts/breakdowns

Activates at 9:30 AM sharp
Defines opening range in first 5 minutes (9:30-9:35)
Monitors for breakouts/breakdowns (9:35-11:30)
AGGRESSIVE thresholds for early detection

One direction alert per symbol per day
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
import requests


class OpeningRangeMonitor:
    def __init__(self, analyzer, opening_range_analyzer, config: dict):
        """
        Initialize Opening Range Monitor
        
        Args:
            analyzer: EnhancedProfessionalAnalyzer instance
            opening_range_analyzer: OpeningRangeAnalyzer instance
            config: Configuration dict from config.yaml
        """
        self.logger = logging.getLogger(__name__)
        self.analyzer = analyzer
        self.or_analyzer = opening_range_analyzer
        
        # Load config
        or_config = config.get('opening_range_monitor', {})
        self.enabled = or_config.get('enabled', True)
        self.check_interval = or_config.get('check_interval', 10)
        self.market_hours_only = or_config.get('market_hours_only', True)
        
        # Thresholds
        thresholds = or_config.get('thresholds', {})
        self.or_minutes = thresholds.get('or_minutes', 5)
        self.min_price_change_pct = thresholds.get('min_price_change_pct', 0.2)
        self.strong_price_change_pct = thresholds.get('strong_price_change_pct', 0.5)
        self.min_volume_ratio = thresholds.get('min_volume_ratio', 1.3)
        self.breakout_confirmation_pct = thresholds.get('breakout_confirmation_pct', 0.05)
        
        # Filters
        filters = or_config.get('filters', {})
        self.watchlist_only = filters.get('watchlist_only', True)
        self.min_price = filters.get('min_price', 5.0)
        self.max_alerts_per_day = filters.get('max_alerts_per_symbol_per_day', 4)
        
        # Cooldowns (in seconds)
        cooldowns = or_config.get('cooldown_minutes', {})
        self.cooldown_or_signal = cooldowns.get('or_signal', 1440) * 60  # Once per day
        self.cooldown_breakout = cooldowns.get('breakout', 30) * 60
        self.cooldown_breakdown = cooldowns.get('breakdown', 30) * 60
        
        # Alert window
        alert_window = or_config.get('alert_window', {})
        self.start_time = alert_window.get('start_time', '09:30')
        self.end_time = alert_window.get('end_time', '11:30')
        self.or_definition_end = alert_window.get('or_definition_end', '09:35')
        
        # Discord webhook
        discord_config = config.get('discord', {})
        self.discord_webhook = discord_config.get('webhook_volume_spike') or discord_config.get('webhook_url')
        
        # Tracking
        self.or_data = {}  # {symbol: OR data dict}
        self.alerts_sent_today = {}  # {(symbol, alert_type): timestamp}
        self.last_reset_date = datetime.now().date()
        
        # Stats
        self.stats = {
            'checks_performed': 0,
            'or_detected': 0,
            'breakouts': 0,
            'breakdowns': 0,
            'alerts_sent': 0,
            'errors': 0
        }
        
        self.logger.info("✅ Opening Range Monitor initialized")
        self.logger.info(f"   ⏱️ Check interval: {self.check_interval}s")
        self.logger.info(f"   🕐 Active window: {self.start_time}-{self.end_time} ET")
        self.logger.info(f"   📊 OR definition: First {self.or_minutes} minutes")
        self.logger.info(f"   🎯 Breakout threshold: {self.breakout_confirmation_pct}%")
    
    def is_in_alert_window(self) -> bool:
        """Check if currently in alert window"""
        et_tz = pytz.timezone('America/New_York')
        now = datetime.now(et_tz)
        
        # Check weekday
        if now.weekday() >= 5:
            return False
        
        current_time = now.strftime('%H:%M')
        return self.start_time <= current_time <= self.end_time
    
    def is_or_definition_period(self) -> bool:
        """Check if currently in OR definition period (9:30-9:35)"""
        et_tz = pytz.timezone('America/New_York')
        now = datetime.now(et_tz)
        
        if now.weekday() >= 5:
            return False
        
        current_time = now.strftime('%H:%M')
        return self.start_time <= current_time < self.or_definition_end
    
    def reset_daily_tracking(self):
        """Reset daily tracking at midnight"""
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.or_data = {}
            self.alerts_sent_today = {}
            self.last_reset_date = today
            self.logger.info("🔄 Opening range tracking reset for new day")
    
    def check_cooldown(self, symbol: str, alert_type: str) -> bool:
        """
        Check if alert is in cooldown period
        
        Returns:
            True if can send alert, False if in cooldown
        """
        key = (symbol, alert_type)
        
        if key not in self.alerts_sent_today:
            return True
        
        last_alert = self.alerts_sent_today[key]
        
        # Choose cooldown based on alert type
        if alert_type == 'OR_DIRECTION':
            cooldown_seconds = self.cooldown_or_signal
        elif alert_type == 'BREAKOUT':
            cooldown_seconds = self.cooldown_breakout
        elif alert_type == 'BREAKDOWN':
            cooldown_seconds = self.cooldown_breakdown
        else:
            cooldown_seconds = 3600  # Default 1 hour
        
        elapsed = (datetime.now() - last_alert).total_seconds()
        
        return elapsed >= cooldown_seconds
    
    def analyze_opening_range(self, symbol: str) -> Optional[Dict]:
        """
        Analyze opening range for a symbol
        
        Returns:
            Dict with OR data or None if not ready
        """
        try:
            # Get current price
            quote = self.analyzer.get_real_time_quote(symbol)
            current_price = quote['price']
            
            if current_price == 0 or current_price < self.min_price:
                return None
            
            # Use OR analyzer to get OR data
            or_analysis = self.or_analyzer.analyze_opening_range(symbol, range_minutes=self.or_minutes)
            
            if or_analysis.get('status') != 'COMPLETE':
                return None
            
            # Store OR data
            self.or_data[symbol] = or_analysis
            self.stats['or_detected'] += 1
            
            return or_analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing OR for {symbol}: {str(e)}")
            self.stats['errors'] += 1
            return None
    
    def check_or_direction_signal(self, symbol: str, or_data: Dict) -> Optional[Dict]:
        """
        Check if OR direction meets signal criteria
        
        Returns:
            Alert dict or None
        """
        try:
            direction = or_data.get('direction')
            strength = or_data.get('strength')
            price_change_pct = or_data.get('price_change_pct', 0)
            volume_ratio = or_data.get('volume_ratio', 0)
            high_volume = or_data.get('high_volume', False)
            
            # Skip if neutral
            if direction == 'NEUTRAL':
                return None
            
            # Check if meets thresholds
            if abs(price_change_pct) < self.min_price_change_pct:
                return None
            
            if volume_ratio < self.min_volume_ratio:
                return None
            
            # Check cooldown
            if not self.check_cooldown(symbol, 'OR_DIRECTION'):
                return None
            
            # Determine urgency
            urgency = 'HIGH' if strength == 'STRONG' else 'MODERATE'
            
            return {
                'symbol': symbol,
                'alert_type': 'OR_DIRECTION',
                'direction': direction,
                'strength': strength,
                'urgency': urgency,
                'or_data': or_data,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error checking OR direction for {symbol}: {str(e)}")
            return None
    
    def check_breakout_breakdown(self, symbol: str) -> Optional[Dict]:
        """
        Check if price has broken out/down from OR
        
        Returns:
            Alert dict or None
        """
        try:
            # Get stored OR data
            or_data = self.or_data.get(symbol)
            if not or_data:
                return None
            
            or_high = or_data.get('or_high', 0)
            or_low = or_data.get('or_low', 0)
            
            if or_high == 0 or or_low == 0:
                return None
            
            # Get current price
            quote = self.analyzer.get_real_time_quote(symbol)
            current_price = quote['price']
            
            if current_price == 0:
                return None
            
            # Calculate breakout/breakdown with confirmation threshold
            breakout_level = or_high * (1 + self.breakout_confirmation_pct / 100)
            breakdown_level = or_low * (1 - self.breakout_confirmation_pct / 100)
            
            alert_type = None
            direction = None
            
            if current_price > breakout_level:
                alert_type = 'BREAKOUT'
                direction = 'BULLISH'
                
                # Check cooldown
                if not self.check_cooldown(symbol, 'BREAKOUT'):
                    return None
                    
            elif current_price < breakdown_level:
                alert_type = 'BREAKDOWN'
                direction = 'BEARISH'
                
                # Check cooldown
                if not self.check_cooldown(symbol, 'BREAKDOWN'):
                    return None
            
            if alert_type:
                # Calculate distance from OR
                if alert_type == 'BREAKOUT':
                    distance_pct = ((current_price - or_high) / or_high) * 100
                else:
                    distance_pct = ((or_low - current_price) / or_low) * 100
                
                return {
                    'symbol': symbol,
                    'alert_type': alert_type,
                    'direction': direction,
                    'current_price': current_price,
                    'or_high': or_high,
                    'or_low': or_low,
                    'distance_pct': distance_pct,
                    'or_data': or_data,
                    'timestamp': datetime.now().isoformat()
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking breakout/breakdown for {symbol}: {str(e)}")
            return None
    
    def send_discord_alert(self, alert: Dict) -> bool:
        """
        Send opening range alert to Discord
        
        Args:
            alert: Alert dict
        
        Returns:
            True if sent successfully
        """
        if not self.discord_webhook:
            self.logger.warning("Discord webhook not configured")
            return False
        
        try:
            symbol = alert['symbol']
            alert_type = alert['alert_type']
            or_data = alert.get('or_data', {})
            
            # Determine color and emoji based on alert type
            if alert_type == 'OR_DIRECTION':
                direction = alert['direction']
                strength = alert['strength']
                
                if direction == 'BULLISH':
                    color = 0x00ff00
                    emoji = '🟢'
                    arrow = '⬆️'
                else:
                    color = 0xff0000
                    emoji = '🔴'
                    arrow = '⬇️'
                
                if strength == 'STRONG':
                    emoji = f'{emoji}{emoji}'
                
                title = f"{emoji} OPENING RANGE {direction} - {symbol} {arrow}"
                description = f"**{strength}** {direction.lower()} opening range detected"
                
            elif alert_type == 'BREAKOUT':
                color = 0x00ff00
                emoji = '🚀'
                title = f"{emoji} OR BREAKOUT - {symbol} ⬆️"
                description = f"Price broke above opening range high"
                
            elif alert_type == 'BREAKDOWN':
                color = 0xff0000
                emoji = '💥'
                title = f"{emoji} OR BREAKDOWN - {symbol} ⬇️"
                description = f"Price broke below opening range low"
            
            embed = {
                'title': title,
                'description': description,
                'color': color,
                'timestamp': datetime.utcnow().isoformat(),
                'fields': []
            }
            
            # OR Direction Alert Fields
            if alert_type == 'OR_DIRECTION':
                embed['fields'].append({
                    'name': '📊 OR High/Low',
                    'value': f"High: **${or_data['or_high']:.2f}**\nLow: **${or_data['or_low']:.2f}**",
                    'inline': True
                })
                
                embed['fields'].append({
                    'name': '📈 Price Change',
                    'value': f"**{or_data['price_change_pct']:+.2f}%**",
                    'inline': True
                })
                
                embed['fields'].append({
                    'name': '📊 Volume',
                    'value': f"**{or_data['volume_ratio']:.1f}x** average",
                    'inline': True
                })
                
                # Trading action
                if direction == 'BULLISH':
                    interpretation = (
                        f"✅ **Bullish opening range**\n"
                        f"→ Watch for breakout above ${or_data['or_high']:.2f}\n"
                        f"→ Entry on OR high break + volume\n"
                        f"→ Stop below OR low ${or_data['or_low']:.2f}"
                    )
                else:
                    interpretation = (
                        f"⚠️ **Bearish opening range**\n"
                        f"→ Watch for breakdown below ${or_data['or_low']:.2f}\n"
                        f"→ Entry on OR low break + volume\n"
                        f"→ Stop above OR high ${or_data['or_high']:.2f}"
                    )
            
            # Breakout/Breakdown Alert Fields
            else:
                current_price = alert['current_price']
                or_high = alert['or_high']
                or_low = alert['or_low']
                distance_pct = alert['distance_pct']
                
                embed['fields'].append({
                    'name': '💰 Current Price',
                    'value': f"**${current_price:.2f}**",
                    'inline': True
                })
                
                embed['fields'].append({
                    'name': '📊 OR High/Low',
                    'value': f"High: ${or_high:.2f}\nLow: ${or_low:.2f}",
                    'inline': True
                })
                
                embed['fields'].append({
                    'name': '🎯 Distance',
                    'value': f"**{distance_pct:.2f}%** beyond OR",
                    'inline': True
                })
                
                # Trading action
                if alert_type == 'BREAKOUT':
                    interpretation = (
                        f"🚀 **BREAKOUT CONFIRMED**\n"
                        f"→ Long setup active\n"
                        f"→ Entry: Current levels\n"
                        f"→ Stop: Below OR high ${or_high:.2f}\n"
                        f"→ Target: +2x OR range"
                    )
                else:
                    interpretation = (
                        f"💥 **BREAKDOWN CONFIRMED**\n"
                        f"→ Short setup active\n"
                        f"→ Entry: Current levels\n"
                        f"→ Stop: Above OR low ${or_low:.2f}\n"
                        f"→ Target: -2x OR range"
                    )
            
            embed['fields'].append({
                'name': '🎯 Trading Action',
                'value': interpretation,
                'inline': False
            })
            
            # Footer
            embed['footer'] = {
                'text': f'Opening Range Monitor • {datetime.now().strftime("%H:%M:%S ET")}'
            }
            
            # Send to Discord
            payload = {'embeds': [embed]}
            response = requests.post(self.discord_webhook, json=payload, timeout=10)
            response.raise_for_status()
            
            self.logger.info(f"✅ OR alert sent: {symbol} - {alert_type}")
            self.stats['alerts_sent'] += 1
            
            # Track alert
            self.alerts_sent_today[(symbol, alert_type)] = datetime.now()
            
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
            self.logger.debug("Opening range monitor disabled")
            return 0
        
        # Reset daily tracking
        self.reset_daily_tracking()
        
        # Check if in alert window
        if not self.is_in_alert_window():
            self.logger.debug("Outside alert window, skipping check")
            return 0
        
        self.logger.info(f"🔍 OR Check: {len(watchlist)} symbols at {datetime.now().strftime('%H:%M:%S')}")
        
        self.stats['checks_performed'] += 1
        alerts_sent = 0
        
        # Check if in OR definition period
        in_or_period = self.is_or_definition_period()
        
        for symbol in watchlist:
            try:
                # If in OR period, analyze OR
                if in_or_period:
                    or_data = self.analyze_opening_range(symbol)
                    
                    if or_data:
                        # Check for OR direction signal
                        alert = self.check_or_direction_signal(symbol, or_data)
                        
                        if alert:
                            success = self.send_discord_alert(alert)
                            if success:
                                alerts_sent += 1
                
                # Always check for breakout/breakdown (after OR is defined)
                else:
                    alert = self.check_breakout_breakdown(symbol)
                    
                    if alert:
                        success = self.send_discord_alert(alert)
                        if success:
                            alerts_sent += 1
                            
                            # Update stats
                            if alert['alert_type'] == 'BREAKOUT':
                                self.stats['breakouts'] += 1
                            elif alert['alert_type'] == 'BREAKDOWN':
                                self.stats['breakdowns'] += 1
                
                # Small delay
                time.sleep(0.3)
                
            except Exception as e:
                self.logger.error(f"Error checking {symbol}: {str(e)}")
                self.stats['errors'] += 1
                continue
        
        if alerts_sent > 0:
            self.logger.info(f"✅ OR check complete: {alerts_sent} alerts sent")
        else:
            self.logger.info(f"✅ OR check complete: No signals detected")
        
        return alerts_sent
    
    def run_continuous(self, watchlist_manager):
        """
        Run continuous monitoring
        
        Args:
            watchlist_manager: WatchlistManager instance
        """
        self.logger.info("🚀 Starting Opening Range Monitor (continuous mode)")
        self.logger.info(f"   ⏱️ Check interval: {self.check_interval} seconds")
        self.logger.info(f"   🕐 Active window: {self.start_time}-{self.end_time} ET")
        self.logger.info(f"   📊 OR period: {self.start_time}-{self.or_definition_end} ET")
        
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
            self.logger.info("Stopping opening range monitor...")
            self.print_stats()
    
    def print_stats(self):
        """Print monitor statistics"""
        print("\n" + "=" * 60)
        print("OPENING RANGE MONITOR STATISTICS")
        print("=" * 60)
        print(f"Checks Performed: {self.stats['checks_performed']}")
        print(f"OR Detected: {self.stats['or_detected']}")
        print(f"Breakouts: {self.stats['breakouts']}")
        print(f"Breakdowns: {self.stats['breakdowns']}")
        print(f"Alerts Sent: {self.stats['alerts_sent']}")
        print(f"Errors: {self.stats['errors']}")
        print("=" * 60 + "\n")
