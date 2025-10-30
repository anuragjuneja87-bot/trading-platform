"""
backend/monitors/extended_hours_volume_monitor.py v2.0
ENHANCED Extended Hours Volume Spike Monitor - Day Trading Edition

IMPROVEMENTS v2.0:
- Uses VolumeAnalyzer v2.0 with day trader thresholds
- Pre-market: 1.8x/2.3x/3.5x (was 2.0x single threshold)
- After-hours: 2.0x/2.5x/3.5x (more conservative)
- Fixed Discord webhook access (works with DiscordAlerter)
- Rate limit protection with retries
- 5 minute cooldown (optimized for pre-market action)

Monitors watchlist for volume spikes during extended hours:
- Pre-market: 4:00 AM - 9:30 AM ET
- After-hours: 4:00 PM - 8:00 PM ET

Routes to: DISCORD_VOLUME_SPIKE channel
"""

import requests
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from analyzers.volume_analyzer import VolumeAnalyzer


class ExtendedHoursVolumeMonitor:
    def __init__(self, polygon_api_key: str, config: dict = None, watchlist_manager=None,
                 discord_alerter=None):
        """
        Initialize ENHANCED Extended Hours Volume Spike Monitor v2.0
        
        Args:
            polygon_api_key: Polygon.io API key
            config: Optional config dictionary
            watchlist_manager: Watchlist manager instance
            discord_alerter: DiscordAlerter instance (NEW)
        """
        self.polygon_api_key = polygon_api_key
        self.config = config or {}
        self.watchlist_manager = watchlist_manager
        self.discord = discord_alerter  # NEW: Use DiscordAlerter
        self.logger = logging.getLogger(__name__)
        
        # Initialize Volume Analyzer v2.0 (day trader mode)
        self.volume_analyzer = VolumeAnalyzer(polygon_api_key, trading_style='day_trader')
        
        # Check intervals
        self.premarket_check_interval = 30  # 30s pre-market
        self.afterhours_check_interval = 45  # 45s after-hours
        
        # Pre-market thresholds (use VolumeAnalyzer defaults: 1.8x/2.3x/3.5x)
        # After-hours thresholds (slightly more conservative)
        self.afterhours_threshold_elevated = 2.0  # After-hours: 2.0x minimum
        self.afterhours_threshold_high = 2.5
        self.afterhours_threshold_extreme = 3.5
        
        # Cooldown
        self.cooldown_minutes = 5  # 5 minute cooldown per symbol
        
        # State tracking
        self.enabled = True
        self.watchlist = []
        self.alert_cooldowns = {}  # {symbol: last_alert_time}
        
        # Stats
        self.stats = {
            'total_checks': 0,
            'spikes_detected': 0,
            'alerts_sent': 0,
            'filtered_by_cooldown': 0,
            'last_check': None,
            'current_session': None,
            'api_calls': 0
        }
        
        self.logger.info("🌅 Extended Hours Volume Monitor v2.0 initialized")
        self.logger.info(f"   Check intervals: Pre-market={self.premarket_check_interval}s, "
                        f"After-hours={self.afterhours_check_interval}s")
        self.logger.info(f"   Pre-market thresholds: {self.volume_analyzer.threshold_elevated}x / "
                        f"{self.volume_analyzer.threshold_high}x / "
                        f"{self.volume_analyzer.threshold_extreme}x")
        self.logger.info(f"   After-hours thresholds: {self.afterhours_threshold_elevated}x / "
                        f"{self.afterhours_threshold_high}x / "
                        f"{self.afterhours_threshold_extreme}x")
        self.logger.info(f"   Cooldown: {self.cooldown_minutes} minutes")
    
    def get_discord_webhook(self) -> Optional[str]:
        """Get Discord webhook URL from DiscordAlerter"""
        if not self.discord:
            return None
        
        # Try different ways to access webhook
        if hasattr(self.discord, 'webhooks'):
            return self.discord.webhooks.get('volume_spike')
        elif hasattr(self.discord, 'config'):
            return self.discord.config.get('webhook_volume_spike')
        elif hasattr(self.discord, 'webhook_volume_spike'):
            return self.discord.webhook_volume_spike
        
        return None
    
    def load_watchlist(self) -> List[str]:
        """Load watchlist from manager"""
        if self.watchlist_manager:
            try:
                symbols = self.watchlist_manager.load_symbols()
                self.watchlist = symbols
                self.logger.info(f"📋 Loaded {len(symbols)} symbols from watchlist")
                return symbols
            except Exception as e:
                self.logger.error(f"Error loading watchlist: {str(e)}")
                return []
        return []
    
    def get_current_session(self) -> Optional[str]:
        """
        Determine current trading session
        
        Returns:
            'PREMARKET', 'REGULAR', 'AFTERHOURS', or None
        """
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        current_minutes = hour * 60 + minute
        day_of_week = now.weekday()
        
        # Only weekdays
        if day_of_week >= 5:  # Saturday or Sunday
            return None
        
        # Define sessions (in minutes since midnight)
        premarket_start = 4 * 60  # 4:00 AM
        premarket_end = 9 * 60 + 30  # 9:30 AM
        regular_end = 16 * 60  # 4:00 PM
        afterhours_end = 20 * 60  # 8:00 PM
        
        if premarket_start <= current_minutes < premarket_end:
            return 'PREMARKET'
        elif premarket_end <= current_minutes < regular_end:
            return 'REGULAR'
        elif regular_end <= current_minutes < afterhours_end:
            return 'AFTERHOURS'
        else:
            return None
    
    def is_extended_hours(self) -> bool:
        """Check if currently in extended hours (pre-market or after-hours)"""
        session = self.get_current_session()
        return session in ['PREMARKET', 'AFTERHOURS']
    
    def check_cooldown(self, symbol: str) -> bool:
        """Check if symbol is in cooldown period"""
        if symbol not in self.alert_cooldowns:
            return True
        
        last_alert = self.alert_cooldowns[symbol]
        elapsed = (datetime.now() - last_alert).total_seconds() / 60
        
        return elapsed >= self.cooldown_minutes
    
    def set_cooldown(self, symbol: str):
        """Set cooldown for symbol"""
        self.alert_cooldowns[symbol] = datetime.now()
    
    def check_volume_spike(self, symbol: str, session: str) -> Optional[Dict]:
        """
        Check if symbol has volume spike in extended hours
        
        Args:
            symbol: Stock symbol
            session: Current session ('PREMARKET' or 'AFTERHOURS')
        
        Returns:
            Volume spike data if detected, None otherwise
        """
        try:
            if session == 'PREMARKET':
                # Use pre-market RVOL with VolumeAnalyzer v2.0
                spike_data = self.volume_analyzer.calculate_premarket_rvol(symbol)
                
                if not spike_data or not spike_data.get('spike_detected'):
                    return None
                
                # Use VolumeAnalyzer classification
                return {
                    'symbol': symbol,
                    'rvol': spike_data.get('rvol', 0),
                    'classification': spike_data.get('classification'),
                    'current_volume': spike_data.get('current_5min_volume', 0),
                    'avg_volume': spike_data.get('avg_hist_5min_volume', 0),
                    'signal_strength': spike_data.get('signal_strength', 0),
                    'session': session
                }
            
            elif session == 'AFTERHOURS':
                # Use regular RVOL but with after-hours thresholds
                rvol_data = self.volume_analyzer.calculate_rvol(symbol)
                
                if not rvol_data or rvol_data.get('rvol', 0) == 0:
                    return None
                
                rvol = rvol_data.get('rvol', 0)
                
                # Apply after-hours thresholds (more conservative)
                if rvol >= self.afterhours_threshold_extreme:
                    classification = 'EXTREME'
                    signal_strength = 4
                elif rvol >= self.afterhours_threshold_high:
                    classification = 'HIGH'
                    signal_strength = 3
                elif rvol >= self.afterhours_threshold_elevated:
                    classification = 'ELEVATED'
                    signal_strength = 2
                else:
                    return None  # Below threshold
                
                self.stats['spikes_detected'] += 1
                
                return {
                    'symbol': symbol,
                    'rvol': rvol,
                    'classification': classification,
                    'current_volume': rvol_data.get('current_volume', 0),
                    'avg_volume': rvol_data.get('expected_volume', 0),
                    'signal_strength': signal_strength,
                    'session': session
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking volume spike for {symbol}: {str(e)}")
            return None
    
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
    
    def send_discord_alert(self, spike_data: Dict) -> bool:
        """
        Send Discord alert for volume spike
        
        Returns:
            True if sent successfully
        """
        webhook_url = self.get_discord_webhook()
        
        if not webhook_url:
            self.logger.warning("Discord webhook not configured for extended hours volume spikes")
            return False
        
        try:
            symbol = spike_data['symbol']
            rvol = spike_data['rvol']
            classification = spike_data['classification']
            current_vol = spike_data['current_volume']
            avg_vol = spike_data['avg_volume']
            session = spike_data['session']
            
            # Determine emoji and color based on classification
            if classification == 'EXTREME':
                emoji = '🔥🔥'
                color = 0xff0000  # Red
                urgency_text = 'EXTREME VOLUME'
            elif classification == 'HIGH':
                emoji = '🔥'
                color = 0xff6600  # Orange
                urgency_text = 'HIGH VOLUME'
            elif classification == 'ELEVATED':
                emoji = '📈'
                color = 0xffaa00  # Yellow
                urgency_text = 'ELEVATED VOLUME'
            else:
                emoji = '📊'
                color = 0x00aaff  # Blue
                urgency_text = 'VOLUME SPIKE'
            
            # Session display
            session_icon = '🌅' if session == 'PREMARKET' else '🌆'
            session_display = 'Pre-Market' if session == 'PREMARKET' else 'After-Hours'
            
            # Format volumes
            def format_volume(volume: int) -> str:
                if volume >= 1_000_000:
                    return f"{volume / 1_000_000:.1f}M"
                elif volume >= 1_000:
                    return f"{volume / 1_000:.1f}K"
                else:
                    return str(volume)
            
            # Build embed
            embed = {
                'title': f'{emoji} {symbol} - {urgency_text} {session_icon}',
                'description': f'**{classification}** volume detected in {session_display}',
                'color': color,
                'timestamp': datetime.utcnow().isoformat(),
                'fields': [
                    {
                        'name': '📊 Volume Metrics',
                        'value': (
                            f'**RVOL:** {rvol:.2f}x\n'
                            f'**Classification:** {classification}\n'
                            f'**Current Volume:** {format_volume(int(current_vol))}\n'
                            f'**Average:** {format_volume(int(avg_vol))}'
                        ),
                        'inline': False
                    },
                    {
                        'name': '⏰ Detection Time',
                        'value': datetime.now().strftime('%I:%M:%S %p ET'),
                        'inline': True
                    },
                    {
                        'name': f'{session_icon} Session',
                        'value': session_display,
                        'inline': True
                    }
                ],
                'footer': {
                    'text': f'Extended Hours Monitor v2.0 • Day trader mode'
                }
            }
            
            # Add action guidance
            if session == 'PREMARKET':
                if classification in ['EXTREME', 'HIGH']:
                    embed['fields'].append({
                        'name': '👀 Pre-Market Action',
                        'value': (
                            '**Early catalyst detected!**\n'
                            '• Check news/catalysts\n'
                            '• Watch for market open continuation\n'
                            '• Set alerts for 9:30 AM open'
                        ),
                        'inline': False
                    })
                else:
                    embed['fields'].append({
                        'name': '📈 Pre-Market Watch',
                        'value': 'Volume building - Monitor into market open',
                        'inline': False
                    })
            else:  # AFTERHOURS
                if classification in ['EXTREME', 'HIGH']:
                    embed['fields'].append({
                        'name': '⚠️ After-Hours Action',
                        'value': (
                            '**Late catalyst or earnings!**\n'
                            '• Check for news/earnings\n'
                            '• Watch for next-day gap\n'
                            '• Set alerts for pre-market'
                        ),
                        'inline': False
                    })
            
            payload = {'embeds': [embed]}
            
            # Send with retry logic
            success = self.send_alert_with_retry(webhook_url, payload)
            
            if success:
                self.stats['alerts_sent'] += 1
                self.logger.info(
                    f"✅ Extended hours alert sent: {symbol} "
                    f"({classification}, {rvol:.2f}x) [{session_display}]"
                )
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending Discord alert: {str(e)}")
            return False
    
    def run_single_check(self) -> int:
        """
        Run single check of all watchlist symbols
        
        Returns:
            Number of alerts sent
        """
        if not self.enabled:
            return 0
        
        session = self.get_current_session()
        
        if not session or session not in ['PREMARKET', 'AFTERHOURS']:
            return 0
        
        self.stats['total_checks'] += 1
        self.stats['last_check'] = datetime.now().isoformat()
        self.stats['current_session'] = session
        
        # Load watchlist
        if not self.watchlist:
            self.load_watchlist()
        
        if not self.watchlist:
            return 0
        
        alerts_sent = 0
        
        for symbol in self.watchlist:
            try:
                # Check cooldown
                if not self.check_cooldown(symbol):
                    self.stats['filtered_by_cooldown'] += 1
                    continue
                
                # Check for volume spike
                spike_data = self.check_volume_spike(symbol, session)
                
                if not spike_data:
                    continue
                
                # Send alert
                success = self.send_discord_alert(spike_data)
                
                if success:
                    self.set_cooldown(symbol)
                    alerts_sent += 1
                
                # Small delay between symbols
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Error processing {symbol}: {str(e)}")
                continue
        
        if alerts_sent > 0:
            self.logger.info(
                f"✅ Extended hours check complete: {alerts_sent} alerts sent [{session}]"
            )
        
        return alerts_sent
    
    def run_continuous(self):
        """Run continuous monitoring during extended hours"""
        self.logger.info("🚀 Starting Extended Hours Volume Monitor v2.0 (continuous mode)")
        
        try:
            while self.enabled:
                try:
                    session = self.get_current_session()
                    
                    if session in ['PREMARKET', 'AFTERHOURS']:
                        self.run_single_check()
                        
                        # Use session-specific check interval
                        if session == 'PREMARKET':
                            time.sleep(self.premarket_check_interval)
                        else:
                            time.sleep(self.afterhours_check_interval)
                    else:
                        # Not in extended hours, check less frequently
                        time.sleep(60)
                    
                except Exception as e:
                    self.logger.error(f"Error in check cycle: {str(e)}")
                    import traceback
                    self.logger.debug(traceback.format_exc())
                    time.sleep(30)
                    
        except KeyboardInterrupt:
            self.logger.info("Stopping extended hours monitor...")
            self.print_stats()
    
    def print_stats(self):
        """Print monitor statistics"""
        print("\n" + "=" * 60)
        print("EXTENDED HOURS VOLUME MONITOR STATISTICS")
        print("=" * 60)
        print(f"Total Checks: {self.stats['total_checks']}")
        print(f"Spikes Detected: {self.stats['spikes_detected']}")
        print(f"Alerts Sent: {self.stats['alerts_sent']}")
        print(f"Filtered by Cooldown: {self.stats['filtered_by_cooldown']}")
        print(f"Current Session: {self.stats['current_session']}")
        print("=" * 60 + "\n")


if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    API_KEY = os.getenv('POLYGON_API_KEY')
    
    monitor = ExtendedHoursVolumeMonitor(API_KEY)
    monitor.watchlist = ['SPY', 'QQQ', 'NVDA', 'TSLA', 'AMD']
    
    print("\n🔍 Running test check...")
    alerts = monitor.run_single_check()
    print(f"\n✅ Test complete: {alerts} alerts sent")
    monitor.print_stats()