"""
backend/monitors/premarket_volume_monitor.py
Pre-Market & After-Hours Volume Spike Monitor

Monitors watchlist for volume spikes during extended hours:
- Pre-market: 4:00 AM - 9:30 AM ET
- After-hours: 4:00 PM - 8:00 PM ET

Alerts when RVOL ≥ 2.0x with 30-minute cooldown per symbol
"""

import requests
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from collections import defaultdict
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from analyzers.volume_analyzer import VolumeAnalyzer


class PremarketVolumeMonitor:
    def __init__(self, polygon_api_key: str, config: dict = None, watchlist_manager=None):
        """
        Initialize Pre-Market Volume Spike Monitor
        
        Args:
            polygon_api_key: Polygon.io API key
            config: Optional config dictionary
            watchlist_manager: Watchlist manager instance
        """
        self.polygon_api_key = polygon_api_key
        self.config = config or {}
        self.watchlist_manager = watchlist_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize Volume Analyzer
        self.volume_analyzer = VolumeAnalyzer(polygon_api_key)
        
        # Configuration
        self.check_interval = 60  # Check every 60 seconds
        self.spike_threshold = 2.0  # Alert when RVOL ≥ 2.0x
        self.cooldown_minutes = 30  # 30-minute cooldown per symbol
        
        # Discord webhook
        self.discord_webhook = None
        
        # State tracking
        self.enabled = True
        self.watchlist = []
        self.alert_cooldowns = {}  # {symbol: last_alert_time}
        self.current_session_alerts = defaultdict(set)  # {session: {symbols}}
        
        # Stats
        self.stats = {
            'total_checks': 0,
            'spikes_detected': 0,
            'alerts_sent': 0,
            'cooldowns_active': 0,
            'last_check': None,
            'current_session': None
        }
        
        self.logger.info("📊 Pre-Market Volume Monitor initialized")
        self.logger.info(f"   Check interval: {self.check_interval}s")
        self.logger.info(f"   Spike threshold: {self.spike_threshold}x RVOL")
        self.logger.info(f"   Cooldown: {self.cooldown_minutes} minutes")
    
    def set_discord_webhook(self, webhook_url: str):
        """Set Discord webhook URL"""
        self.discord_webhook = webhook_url
        self.logger.info("✅ Discord webhook configured for volume spikes")
    
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
            'premarket', 'regular', 'afterhours', or None
        """
        now = datetime.now()
        et = datetime.now()  # Assume server is in ET, adjust if needed
        
        hour = et.hour
        minute = et.minute
        current_minutes = hour * 60 + minute
        day_of_week = et.weekday()
        
        # Only weekdays
        if day_of_week >= 5:  # Saturday or Sunday
            return None
        
        # Define sessions (in minutes since midnight)
        premarket_start = 4 * 60  # 4:00 AM
        premarket_end = 9 * 60 + 30  # 9:30 AM
        regular_end = 16 * 60  # 4:00 PM
        afterhours_end = 20 * 60  # 8:00 PM
        
        if premarket_start <= current_minutes < premarket_end:
            return 'premarket'
        elif premarket_end <= current_minutes < regular_end:
            return 'regular'
        elif regular_end <= current_minutes < afterhours_end:
            return 'afterhours'
        else:
            return None
    
    def is_extended_hours(self) -> bool:
        """Check if currently in extended hours (pre-market or after-hours)"""
        session = self.get_current_session()
        return session in ['premarket', 'afterhours']
    
    def is_cooldown_active(self, symbol: str) -> bool:
        """Check if symbol is in cooldown period"""
        if symbol not in self.alert_cooldowns:
            return False
        
        last_alert = self.alert_cooldowns[symbol]
        elapsed = (datetime.now() - last_alert).total_seconds() / 60
        
        return elapsed < self.cooldown_minutes
    
    def set_cooldown(self, symbol: str):
        """Set cooldown for symbol"""
        self.alert_cooldowns[symbol] = datetime.now()
        self.logger.debug(f"{symbol}: Cooldown set for {self.cooldown_minutes} minutes")
    
    def check_volume_spike(self, symbol: str, session: str) -> Optional[Dict]:
        """
        Check if symbol has volume spike
        
        Args:
            symbol: Stock symbol
            session: 'premarket' or 'afterhours'
        
        Returns:
            Volume spike data if detected, None otherwise
        """
        try:
            # Get appropriate RVOL based on session
            if session == 'premarket':
                rvol_data = self.volume_analyzer.calculate_premarket_rvol(symbol)
            elif session == 'afterhours':
                # For after-hours, use regular RVOL calculation
                # (we could create a separate after-hours RVOL method if needed)
                rvol_data = self.volume_analyzer.calculate_rvol(symbol)
            else:
                return None
            
            if not rvol_data or rvol_data.get('rvol', 0) == 0:
                return None
            
            rvol = rvol_data.get('rvol', 0)
            classification = rvol_data.get('classification', 'UNKNOWN')
            
            # Check if spike threshold met
            if rvol >= self.spike_threshold:
                self.stats['spikes_detected'] += 1
                
                return {
                    'symbol': symbol,
                    'session': session,
                    'rvol': rvol,
                    'classification': classification,
                    'current_volume': rvol_data.get('current_volume', 0),
                    'expected_volume': rvol_data.get('expected_volume', 0),
                    'avg_volume': rvol_data.get('avg_daily_volume', 0),
                    'timestamp': datetime.now().isoformat()
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking volume spike for {symbol}: {str(e)}")
            return None
    
    def format_volume(self, volume: int) -> str:
        """Format volume for display"""
        if volume >= 1_000_000:
            return f"{volume / 1_000_000:.1f}M"
        elif volume >= 1_000:
            return f"{volume / 1_000:.1f}K"
        else:
            return str(volume)
    
    def send_discord_alert(self, spike_data: Dict) -> bool:
        """
        Send Discord alert for volume spike
        
        Args:
            spike_data: Volume spike information
        
        Returns:
            True if sent successfully
        """
        if not self.discord_webhook:
            self.logger.warning("Discord webhook not configured")
            return False
        
        try:
            symbol = spike_data['symbol']
            session = spike_data['session']
            rvol = spike_data['rvol']
            classification = spike_data['classification']
            current_vol = spike_data['current_volume']
            expected_vol = spike_data['expected_volume']
            
            # Determine emoji and color based on classification
            if classification == 'EXTREME':
                emoji = '🔥'
                color = 0xff0000  # Red
            elif classification == 'HIGH':
                emoji = '📈'
                color = 0xff6600  # Orange
            else:
                emoji = '📊'
                color = 0xffff00  # Yellow
            
            # Session display
            session_display = "PRE-MARKET" if session == 'premarket' else "AFTER-HOURS"
            
            # Build embed
            embed = {
                'title': f'{emoji} {symbol} - {session_display} VOLUME SPIKE',
                'description': f'**{classification}** volume detected during extended hours',
                'color': color,
                'timestamp': datetime.utcnow().isoformat(),
                'fields': [
                    {
                        'name': '📊 Relative Volume (RVOL)',
                        'value': f'**{rvol:.2f}x** ({classification})',
                        'inline': True
                    },
                    {
                        'name': '⏰ Session',
                        'value': session_display,
                        'inline': True
                    },
                    {
                        'name': '📦 Current Volume',
                        'value': f'{self.format_volume(current_vol)} shares',
                        'inline': True
                    },
                    {
                        'name': '📉 Expected Volume',
                        'value': f'{self.format_volume(expected_vol)} shares',
                        'inline': True
                    },
                    {
                        'name': '📈 Volume vs Expected',
                        'value': f'+{((current_vol - expected_vol) / expected_vol * 100):.0f}%',
                        'inline': True
                    }
                ],
                'footer': {
                    'text': f'Pre-Market Volume Monitor • Cooldown: {self.cooldown_minutes}min'
                }
            }
            
            # Add context message
            if rvol >= 3.0:
                embed['fields'].append({
                    'name': '⚠️ Action',
                    'value': '**EXTREME volume** - Check for news catalyst!',
                    'inline': False
                })
            elif rvol >= 2.5:
                embed['fields'].append({
                    'name': '👀 Action',
                    'value': 'Significant volume - Monitor for entry opportunity',
                    'inline': False
                })
            
            payload = {
                'embeds': [embed]
            }
            
            response = requests.post(
                self.discord_webhook,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            
            self.stats['alerts_sent'] += 1
            self.logger.info(f"✅ Volume spike alert sent: {symbol} ({rvol:.2f}x)")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send Discord alert: {str(e)}")
            return False
    
    def run_single_check(self) -> int:
        """
        Run a single check cycle
        
        Returns:
            Number of alerts sent
        """
        alerts_sent = 0
        
        # Check if we're in extended hours
        session = self.get_current_session()
        
        if session not in ['premarket', 'afterhours']:
            self.logger.debug(f"Not in extended hours (session: {session}), skipping check")
            return 0
        
        self.stats['current_session'] = session
        
        # Load watchlist
        if not self.watchlist:
            self.load_watchlist()
        
        if not self.watchlist:
            self.logger.warning("Empty watchlist, nothing to monitor")
            return 0
        
        self.logger.info(f"🔍 Checking {len(self.watchlist)} symbols for {session} volume spikes...")
        
        for symbol in self.watchlist:
            try:
                # Skip if in cooldown
                if self.is_cooldown_active(symbol):
                    continue
                
                # Check for volume spike
                spike_data = self.check_volume_spike(symbol, session)
                
                if spike_data:
                    self.logger.info(
                        f"🚨 {symbol}: Volume spike detected! "
                        f"RVOL {spike_data['rvol']:.2f}x ({spike_data['classification']})"
                    )
                    
                    # Send alert
                    if self.send_discord_alert(spike_data):
                        alerts_sent += 1
                        self.set_cooldown(symbol)
                
                # Small delay to avoid API rate limits
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Error checking {symbol}: {str(e)}")
                continue
        
        self.stats['total_checks'] += 1
        self.stats['last_check'] = datetime.now().isoformat()
        self.stats['cooldowns_active'] = sum(1 for s in self.watchlist if self.is_cooldown_active(s))
        
        if alerts_sent > 0:
            self.logger.info(f"✅ Sent {alerts_sent} volume spike alerts")
        
        return alerts_sent
    
    def run_continuous(self):
        """Run monitor continuously"""
        self.logger.info("🚀 Starting Pre-Market Volume Monitor (continuous mode)")
        self.logger.info(f"   Monitoring: Pre-market (4:00-9:30 AM) & After-hours (4:00-8:00 PM)")
        self.logger.info(f"   Check interval: {self.check_interval}s")
        
        # Load watchlist initially
        self.load_watchlist()
        
        while self.enabled:
            try:
                session = self.get_current_session()
                
                # Only check during extended hours
                if session in ['premarket', 'afterhours']:
                    self.run_single_check()
                else:
                    self.logger.debug(f"Outside extended hours (session: {session}), waiting...")
                
                # Wait before next check
                time.sleep(self.check_interval)
                
                # Reload watchlist every 10 minutes
                if self.stats['total_checks'] % 10 == 0:
                    self.load_watchlist()
                
            except KeyboardInterrupt:
                self.logger.info("Monitor stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {str(e)}")
                time.sleep(self.check_interval)
    
    def stop(self):
        """Stop the monitor"""
        self.enabled = False
        self.logger.info("Monitor stopped")


# CLI Testing
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    API_KEY = os.getenv('POLYGON_API_KEY')
    WEBHOOK = os.getenv('DISCORD_VOLUME_SPIKE')
    
    if not API_KEY:
        print("❌ Error: POLYGON_API_KEY not found")
        exit(1)
    
    if not WEBHOOK:
        print("⚠️  Warning: DISCORD_VOLUME_SPIKE not configured")
    
    # Create simple watchlist manager mock
    class MockWatchlist:
        def load_symbols(self):
            return ['SPY', 'QQQ', 'NVDA', 'TSLA', 'AAPL']
    
    monitor = PremarketVolumeMonitor(
        polygon_api_key=API_KEY,
        watchlist_manager=MockWatchlist()
    )
    
    if WEBHOOK:
        monitor.set_discord_webhook(WEBHOOK)
    
    print("=" * 80)
    print("PRE-MARKET VOLUME SPIKE MONITOR - TEST MODE")
    print("=" * 80)
    print(f"\nCurrent session: {monitor.get_current_session()}")
    print(f"Extended hours: {monitor.is_extended_hours()}")
    print("\nRunning single check...\n")
    
    alerts = monitor.run_single_check()
    
    print("\n" + "=" * 80)
    print(f"Check complete: {alerts} alerts sent")
    print(f"Stats: {monitor.stats}")
    print("=" * 80)
