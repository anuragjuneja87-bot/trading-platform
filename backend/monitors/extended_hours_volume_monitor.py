"""
backend/monitors/extended_hours_volume_monitor.py
Extended Hours Volume Spike Monitor - UPDATED VERSION

Monitors watchlist for volume spikes during extended hours:
- Pre-market: 4:00 AM - 9:30 AM ET
- After-hours: 4:00 PM - 8:00 PM ET

Updates from original:
- 5-minute cooldown (was 30 minutes)
- Consistent 2.0x threshold for both sessions
- Price movement filter (±0.5% minimum)
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
    def __init__(self, polygon_api_key: str, discord_alerter=None, config: dict = None, watchlist_manager=None):
        """
        Initialize Extended Hours Volume Spike Monitor
        
        Args:
            polygon_api_key: Polygon.io API key
            discord_alerter: Discord alerter instance from AlertManager
            config: Optional config dictionary
            watchlist_manager: Watchlist manager instance
        """
        self.polygon_api_key = polygon_api_key
        self.discord_alerter = discord_alerter
        self.config = config or {}
        self.watchlist_manager = watchlist_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize Volume Analyzer
        self.volume_analyzer = VolumeAnalyzer(polygon_api_key)
        
        # Configuration - UPDATED
        self.check_interval = 60  # Check every 60 seconds (extended hours)
        self.spike_threshold = 2.0  # Alert when RVOL ≥ 2.0x
        self.cooldown_minutes = 5  # UPDATED: 5-minute cooldown (was 30)
        
        # Price movement filter - SAME as real-time monitor
        self.min_price_change_pct = 0.5  # Minimum 0.5% price move
        
        # State tracking
        self.enabled = True
        self.watchlist = []
        self.alert_cooldowns = {}  # {symbol: last_alert_time}
        
        # Previous price tracking
        self.previous_prices = {}  # {symbol: {'price': float, 'timestamp': datetime}}
        
        # Stats
        self.stats = {
            'total_checks': 0,
            'spikes_detected': 0,
            'alerts_sent': 0,
            'filtered_by_price': 0,
            'filtered_by_cooldown': 0,
            'last_check': None,
            'current_session': None,
            'api_calls': 0
        }
        
        self.logger.info("🌅 Extended Hours Volume Monitor initialized")
        self.logger.info(f"   Check interval: {self.check_interval}s")
        self.logger.info(f"   Spike threshold: {self.spike_threshold}x RVOL")
        self.logger.info(f"   Price filter: ±{self.min_price_change_pct}% minimum")
        self.logger.info(f"   Cooldown: {self.cooldown_minutes} minutes (UPDATED)")
    
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
    
    def get_live_price(self, symbol: str) -> Optional[Dict]:
        """Get LIVE current price (no caching)"""
        try:
            url = f"https://api.polygon.io/v2/last/trade/{symbol}"
            params = {'apiKey': self.polygon_api_key}
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            self.stats['api_calls'] += 1
            
            if 'results' in data:
                current_price = data['results'].get('p', 0)
                
                # Calculate price change
                change_pct = 0.0
                if symbol in self.previous_prices:
                    prev_price = self.previous_prices[symbol]['price']
                    if prev_price > 0:
                        change_pct = ((current_price - prev_price) / prev_price) * 100
                
                # Update previous price
                self.previous_prices[symbol] = {
                    'price': current_price,
                    'timestamp': datetime.now()
                }
                
                return {
                    'price': current_price,
                    'change_pct': change_pct,
                    'timestamp': datetime.now()
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting live price for {symbol}: {str(e)}")
            return None
    
    def check_volume_spike(self, symbol: str, session: str) -> Optional[Dict]:
        """
        Check if symbol has volume spike with LIVE data
        
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
                rvol_data = self.volume_analyzer.calculate_rvol(symbol)
            else:
                return None
            
            if not rvol_data or rvol_data.get('rvol', 0) == 0:
                return None
            
            rvol = rvol_data.get('rvol', 0)
            classification = rvol_data.get('classification', 'UNKNOWN')
            
            # Check if spike threshold met
            if rvol < self.spike_threshold:
                return None
            
            self.stats['spikes_detected'] += 1
            
            # Get LIVE price data
            price_data = self.get_live_price(symbol)
            if not price_data:
                self.logger.warning(f"{symbol}: Could not get live price data")
                return None
            
            return {
                'symbol': symbol,
                'session': session,
                'rvol': rvol,
                'classification': classification,
                'current_volume': rvol_data.get('current_volume', 0),
                'expected_volume': rvol_data.get('expected_volume', 0),
                'avg_volume': rvol_data.get('avg_daily_volume', 0),
                'current_price': price_data['price'],
                'price_change_pct': price_data['change_pct'],
                'timestamp': datetime.now().isoformat()
            }
            
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
        Send Discord alert for volume spike with LIVE detailed data
        
        Args:
            spike_data: Volume spike information (ALL LIVE DATA)
        
        Returns:
            True if sent successfully
        """
        if not self.discord_alerter:
            self.logger.warning("Discord alerter not configured")
            return False
        
        try:
            symbol = spike_data['symbol']
            session = spike_data['session']
            rvol = spike_data['rvol']
            classification = spike_data['classification']
            current_vol = spike_data['current_volume']
            expected_vol = spike_data['expected_volume']
            current_price = spike_data['current_price']
            price_change = spike_data['price_change_pct']
            
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
            session_emoji = "🌅" if session == 'premarket' else "🌙"
            
            # Price change emoji
            if price_change > 0:
                price_emoji = '🟢'
                price_text = f'+{price_change:.2f}%'
            elif price_change < 0:
                price_emoji = '🔴'
                price_text = f'{price_change:.2f}%'
            else:
                price_emoji = '⚪'
                price_text = '0.00%'
            
            # Calculate volume vs expected
            vol_vs_expected = ((current_vol - expected_vol) / expected_vol * 100) if expected_vol > 0 else 0
            
            # Build embed
            embed = {
                'title': f'{emoji} {symbol} - {session_display} VOLUME SPIKE',
                'description': f'**{classification}** volume detected during extended hours',
                'color': color,
                'timestamp': datetime.utcnow().isoformat(),
                'fields': [
                    {
                        'name': '📊 Volume Metrics (LIVE)',
                        'value': (
                            f'**RVOL:** {rvol:.2f}x ({classification})\n'
                            f'**Current Volume:** {self.format_volume(current_vol)} shares\n'
                            f'**Expected:** {self.format_volume(expected_vol)} shares\n'
                            f'**vs Expected:** +{vol_vs_expected:.0f}%'
                        ),
                        'inline': False
                    },
                    {
                        'name': f'{price_emoji} Price Action (LIVE)',
                        'value': (
                            f'**Current:** ${current_price:.2f}\n'
                            f'**Change:** {price_text}'
                        ),
                        'inline': False
                    },
                    {
                        'name': f'{session_emoji} Session',
                        'value': session_display,
                        'inline': True
                    },
                    {
                        'name': '⏰ Detection Time',
                        'value': datetime.now().strftime('%I:%M:%S %p ET'),
                        'inline': True
                    }
                ],
                'footer': {
                    'text': f'Extended Hours Monitor • 60s checks • {self.cooldown_minutes}min cooldown'
                }
            }
            
            # Add context message
            if rvol >= 5.0:
                embed['fields'].append({
                    'name': '⚠️ Action',
                    'value': '**EXTREME volume** - Check for news catalyst or earnings!',
                    'inline': False
                })
            elif rvol >= 3.0:
                embed['fields'].append({
                    'name': '👀 Action',
                    'value': 'Significant volume - Monitor for market open impact.',
                    'inline': False
                })
            
            payload = {
                'embeds': [embed]
            }
            
            # Send via discord_alerter
            self.discord_alerter.send_webhook('VOLUME_SPIKE', payload)
            
            self.stats['alerts_sent'] += 1
            self.logger.info(
                f"✅ Extended hours volume spike alert sent: {symbol} "
                f"({rvol:.2f}x, {price_text}, {session_display})"
            )
            
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
        
        session_display = "PRE-MARKET" if session == 'premarket' else "AFTER-HOURS"
        self.logger.info(f"🔍 {session_display} check: {len(self.watchlist)} symbols...")
        
        for symbol in self.watchlist:
            try:
                # Skip if in cooldown
                if self.is_cooldown_active(symbol):
                    continue
                
                # Check for volume spike
                spike_data = self.check_volume_spike(symbol, session)
                
                if spike_data:
                    # Apply price movement filter
                    price_change = abs(spike_data['price_change_pct'])
                    
                    if price_change < self.min_price_change_pct:
                        self.logger.debug(
                            f"{symbol}: Volume spike detected but price change "
                            f"({price_change:.2f}%) below minimum ({self.min_price_change_pct}%)"
                        )
                        self.stats['filtered_by_price'] += 1
                        continue
                    
                    self.logger.info(
                        f"🚨 {symbol}: {session_display} volume spike! "
                        f"RVOL {spike_data['rvol']:.2f}x ({spike_data['classification']}), "
                        f"Price ${spike_data['current_price']:.2f} ({spike_data['price_change_pct']:+.2f}%)"
                    )
                    
                    # Send alert
                    if self.send_discord_alert(spike_data):
                        alerts_sent += 1
                        self.set_cooldown(symbol)
                    else:
                        self.stats['filtered_by_cooldown'] += 1
                
                # Small delay to avoid API rate limits
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Error checking {symbol}: {str(e)}")
                continue
        
        self.stats['total_checks'] += 1
        self.stats['last_check'] = datetime.now().isoformat()
        
        if alerts_sent > 0:
            self.logger.info(f"✅ Sent {alerts_sent} extended hours volume spike alerts")
        
        return alerts_sent
    
    def run_continuous(self):
        """Run monitor continuously"""
        self.logger.info("🚀 Starting Extended Hours Volume Monitor (continuous mode)")
        self.logger.info(f"   Monitoring: Pre-market (4:00-9:30 AM) & After-hours (4:00-8:00 PM)")
        self.logger.info(f"   Check interval: {self.check_interval}s")
        self.logger.info(f"   Cooldown: {self.cooldown_minutes} minutes")
        
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
        self.logger.info("Extended hours monitor stopped")
        self.print_stats()
    
    def print_stats(self):
        """Print monitor statistics"""
        print("\n" + "=" * 60)
        print("EXTENDED HOURS VOLUME SPIKE MONITOR STATISTICS")
        print("=" * 60)
        print(f"Total Checks: {self.stats['total_checks']}")
        print(f"Spikes Detected: {self.stats['spikes_detected']}")
        print(f"Alerts Sent: {self.stats['alerts_sent']}")
        print(f"Filtered by Price: {self.stats['filtered_by_price']}")
        print(f"Filtered by Cooldown: {self.stats['filtered_by_cooldown']}")
        print(f"API Calls: {self.stats['api_calls']}")
        print(f"Last Check: {self.stats['last_check']}")
        print(f"Current Session: {self.stats['current_session']}")
        print("=" * 60 + "\n")


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
        print("⚠️ Warning: DISCORD_VOLUME_SPIKE not configured")
    
    # Create simple watchlist manager mock
    class MockWatchlist:
        def load_symbols(self):
            return ['SPY', 'QQQ', 'NVDA', 'TSLA', 'AAPL', 'ORCL', 'PLTR']
    
    monitor = ExtendedHoursVolumeMonitor(
        polygon_api_key=API_KEY,
        watchlist_manager=MockWatchlist()
    )
    
    if WEBHOOK:
        monitor.set_discord_webhook(WEBHOOK)
    
    print("=" * 80)
    print("EXTENDED HOURS VOLUME SPIKE MONITOR - TEST MODE")
    print("=" * 80)
    print(f"\nCurrent session: {monitor.get_current_session()}")
    print(f"Extended hours: {monitor.is_extended_hours()}")
    print("\nRunning single check...\n")
    
    alerts = monitor.run_single_check()
    
    print("\n" + "=" * 80)
    print(f"Check complete: {alerts} alerts sent")
    monitor.print_stats()
    print("=" * 80)