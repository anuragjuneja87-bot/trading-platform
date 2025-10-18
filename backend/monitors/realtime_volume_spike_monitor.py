"""
backend/monitors/realtime_volume_spike_monitor.py
Real-Time Volume Spike Monitor - Market Hours Edition

Monitors watchlist for volume spikes during regular market hours (9:30 AM - 4:00 PM ET)
- 30-second check interval for catching rapid moves like ORCL +$14
- RVOL-based detection with price movement filter (±0.5% minimum)
- 5-minute cooldown per symbol (catches follow-up spikes quickly)
- Live data only - no caching, real-time prices/VWAP
- Routes to: DISCORD_VOLUME_SPIKE channel
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


class RealtimeVolumeSpikeMonitor:
    def __init__(self, polygon_api_key: str, config: dict = None, watchlist_manager=None):
        """
        Initialize Real-Time Volume Spike Monitor
        
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
        
        # Configuration - REAL-TIME focused
        self.check_interval = 30  # Check every 30 seconds
        self.cooldown_minutes = 5  # 5-minute cooldown
        
        # Thresholds - RVOL based
        self.thresholds = {
            'ELEVATED': 2.0,   # Alert at 2.0x RVOL
            'HIGH': 3.0,       # Alert at 3.0x RVOL
            'EXTREME': 5.0     # Alert at 5.0x RVOL
        }
        
        # Price movement filter - only alert if price moved
        self.min_price_change_pct = 0.5  # Minimum 0.5% price move
        
        # Discord webhook
        self.discord_webhook = None
        
        # State tracking
        self.enabled = True
        self.watchlist = []
        self.alert_cooldowns = {}  # {symbol: last_alert_time}
        
        # Previous price tracking for price movement calculation
        self.previous_prices = {}  # {symbol: {'price': float, 'timestamp': datetime}}
        
        # Stats
        self.stats = {
            'total_checks': 0,
            'spikes_detected': 0,
            'alerts_sent': 0,
            'filtered_by_price': 0,
            'filtered_by_cooldown': 0,
            'last_check': None,
            'api_calls': 0
        }
        
        self.logger.info("🚀 Real-Time Volume Spike Monitor initialized")
        self.logger.info(f"   Check interval: {self.check_interval}s")
        self.logger.info(f"   Thresholds: ELEVATED ≥{self.thresholds['ELEVATED']}x, HIGH ≥{self.thresholds['HIGH']}x, EXTREME ≥{self.thresholds['EXTREME']}x")
        self.logger.info(f"   Price filter: ±{self.min_price_change_pct}% minimum")
        self.logger.info(f"   Cooldown: {self.cooldown_minutes} minutes")
    
    def set_discord_webhook(self, webhook_url: str):
        """Set Discord webhook URL"""
        self.discord_webhook = webhook_url
        self.logger.info("✅ Discord webhook configured for real-time volume spikes")
    
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
    
    def is_market_hours(self) -> bool:
        """Check if currently in market hours (9:30 AM - 4:00 PM ET)"""
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        current_minutes = hour * 60 + minute
        day_of_week = now.weekday()
        
        # Only weekdays
        if day_of_week >= 5:  # Saturday or Sunday
            return False
        
        market_open = 9 * 60 + 30   # 9:30 AM
        market_close = 16 * 60       # 4:00 PM
        
        return market_open <= current_minutes < market_close
    
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
        """
        Get LIVE current price (no caching)
        Returns: {'price': float, 'change_pct': float, 'timestamp': datetime}
        """
        try:
            # Get real-time quote from Polygon
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
    
    def get_live_vwap(self, symbol: str) -> Optional[float]:
        """
        Get LIVE VWAP (today's VWAP, no caching)
        """
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/minute/{today}/{today}"
            params = {
                'apiKey': self.polygon_api_key,
                'adjusted': 'true',
                'sort': 'desc',
                'limit': 1  # Just get the most recent bar
            }
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            self.stats['api_calls'] += 1
            
            if 'results' in data and data['results']:
                # For real VWAP, we'd need to calculate cumulative
                # For now, use the close as approximation or get from snapshot
                # Better approach: use snapshot endpoint
                return self.get_vwap_from_snapshot(symbol)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting VWAP for {symbol}: {str(e)}")
            return None
    
    def get_vwap_from_snapshot(self, symbol: str) -> Optional[float]:
        """Get VWAP from snapshot endpoint (most accurate for real-time)"""
        try:
            url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}"
            params = {'apiKey': self.polygon_api_key}
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            self.stats['api_calls'] += 1
            
            if 'ticker' in data and 'day' in data['ticker']:
                vwap = data['ticker']['day'].get('vw', 0)
                return vwap if vwap > 0 else None
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting VWAP snapshot for {symbol}: {str(e)}")
            return None
    
    def check_volume_spike(self, symbol: str) -> Optional[Dict]:
        """
        Check if symbol has volume spike with LIVE data
        
        Returns:
            Volume spike data if detected, None otherwise
        """
        try:
            # Get LIVE RVOL (no caching)
            rvol_data = self.volume_analyzer.calculate_rvol(symbol)
            
            if not rvol_data or rvol_data.get('rvol', 0) == 0:
                return None
            
            rvol = rvol_data.get('rvol', 0)
            
            # Determine classification based on thresholds
            if rvol >= self.thresholds['EXTREME']:
                classification = 'EXTREME'
            elif rvol >= self.thresholds['HIGH']:
                classification = 'HIGH'
            elif rvol >= self.thresholds['ELEVATED']:
                classification = 'ELEVATED'
            else:
                classification = 'NORMAL'
            
            # Only proceed if we have a spike
            if classification == 'NORMAL':
                return None
            
            self.stats['spikes_detected'] += 1
            
            # Get LIVE price data
            price_data = self.get_live_price(symbol)
            if not price_data:
                self.logger.warning(f"{symbol}: Could not get live price data")
                return None
            
            # Get LIVE VWAP
            vwap = self.get_live_vwap(symbol)
            
            return {
                'symbol': symbol,
                'rvol': rvol,
                'classification': classification,
                'current_volume': rvol_data.get('current_volume', 0),
                'expected_volume': rvol_data.get('expected_volume', 0),
                'avg_volume': rvol_data.get('avg_daily_volume', 0),
                'current_price': price_data['price'],
                'price_change_pct': price_data['change_pct'],
                'vwap': vwap,
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
        if not self.discord_webhook:
            self.logger.warning("Discord webhook not configured")
            return False
        
        try:
            symbol = spike_data['symbol']
            rvol = spike_data['rvol']
            classification = spike_data['classification']
            current_vol = spike_data['current_volume']
            expected_vol = spike_data['expected_volume']
            current_price = spike_data['current_price']
            price_change = spike_data['price_change_pct']
            vwap = spike_data.get('vwap', 0)
            
            # Determine emoji and color based on classification
            if classification == 'EXTREME':
                emoji = '🔥'
                color = 0xff0000  # Red
                urgency_text = 'EXTREME VOLUME SPIKE'
            elif classification == 'HIGH':
                emoji = '📈'
                color = 0xff6600  # Orange
                urgency_text = 'HIGH VOLUME SPIKE'
            else:
                emoji = '📊'
                color = 0xffff00  # Yellow
                urgency_text = 'VOLUME SPIKE DETECTED'
            
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
            
            # Build embed with LIVE data
            embed = {
                'title': f'{emoji} {symbol} - {urgency_text}',
                'description': f'**{classification}** volume detected during market hours',
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
                            f'**Change:** {price_text}\n'
                            f'**VWAP:** ${vwap:.2f}' if vwap else '**VWAP:** N/A'
                        ),
                        'inline': False
                    },
                    {
                        'name': '⏰ Detection Time',
                        'value': datetime.now().strftime('%I:%M:%S %p ET'),
                        'inline': True
                    },
                    {
                        'name': '🎯 Session',
                        'value': 'MARKET HOURS',
                        'inline': True
                    }
                ],
                'footer': {
                    'text': f'Real-Time Monitor • 30s checks • {self.cooldown_minutes}min cooldown'
                }
            }
            
            # Add action guidance based on classification
            if classification == 'EXTREME':
                embed['fields'].append({
                    'name': '⚠️ Action Required',
                    'value': '**EXTREME volume** - Check for catalyst! Major move likely in progress.',
                    'inline': False
                })
            elif classification == 'HIGH':
                embed['fields'].append({
                    'name': '👀 Action',
                    'value': 'Significant volume - Monitor for entry opportunity or breakout.',
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
            self.logger.info(
                f"✅ Real-time volume spike alert sent: {symbol} "
                f"({rvol:.2f}x, {price_text}, ${current_price:.2f})"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send Discord alert: {str(e)}")
            return False
    
    def run_single_check(self) -> int:
        """
        Run a single check cycle (30 seconds)
        
        Returns:
            Number of alerts sent
        """
        alerts_sent = 0
        
        # Check if we're in market hours
        if not self.is_market_hours():
            self.logger.debug("Outside market hours, skipping check")
            return 0
        
        # Load watchlist
        if not self.watchlist:
            self.load_watchlist()
        
        if not self.watchlist:
            self.logger.warning("Empty watchlist, nothing to monitor")
            return 0
        
        self.logger.info(f"🔍 Real-time check: {len(self.watchlist)} symbols...")
        
        for symbol in self.watchlist:
            try:
                # Skip if in cooldown
                if self.is_cooldown_active(symbol):
                    continue
                
                # Check for volume spike with LIVE data
                spike_data = self.check_volume_spike(symbol)
                
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
                        f"🚨 {symbol}: Volume spike detected! "
                        f"RVOL {spike_data['rvol']:.2f}x ({spike_data['classification']}), "
                        f"Price ${spike_data['current_price']:.2f} ({spike_data['price_change_pct']:+.2f}%)"
                    )
                    
                    # Send alert
                    if self.send_discord_alert(spike_data):
                        alerts_sent += 1
                        self.set_cooldown(symbol)
                    else:
                        self.stats['filtered_by_cooldown'] += 1
                
                # Small delay to avoid rate limits (but should be fine with $200 plan)
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Error checking {symbol}: {str(e)}")
                continue
        
        self.stats['total_checks'] += 1
        self.stats['last_check'] = datetime.now().isoformat()
        
        if alerts_sent > 0:
            self.logger.info(f"✅ Sent {alerts_sent} real-time volume spike alerts")
        
        return alerts_sent
    
    def run_continuous(self):
        """Run monitor continuously during market hours"""
        self.logger.info("🚀 Starting Real-Time Volume Spike Monitor (continuous mode)")
        self.logger.info(f"   Active: Market hours only (9:30 AM - 4:00 PM ET)")
        self.logger.info(f"   Check interval: {self.check_interval}s")
        self.logger.info(f"   Price filter: ±{self.min_price_change_pct}% minimum")
        
        # Load watchlist initially
        self.load_watchlist()
        
        while self.enabled:
            try:
                if self.is_market_hours():
                    self.run_single_check()
                else:
                    self.logger.debug("Market closed, waiting...")
                
                # Wait before next check
                time.sleep(self.check_interval)
                
                # Reload watchlist every 20 checks (~10 minutes)
                if self.stats['total_checks'] % 20 == 0:
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
        self.logger.info("Real-time monitor stopped")
        self.print_stats()
    
    def print_stats(self):
        """Print monitor statistics"""
        print("\n" + "=" * 60)
        print("REAL-TIME VOLUME SPIKE MONITOR STATISTICS")
        print("=" * 60)
        print(f"Total Checks: {self.stats['total_checks']}")
        print(f"Spikes Detected: {self.stats['spikes_detected']}")
        print(f"Alerts Sent: {self.stats['alerts_sent']}")
        print(f"Filtered by Price: {self.stats['filtered_by_price']}")
        print(f"Filtered by Cooldown: {self.stats['filtered_by_cooldown']}")
        print(f"API Calls: {self.stats['api_calls']}")
        print(f"Last Check: {self.stats['last_check']}")
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
    
    monitor = RealtimeVolumeSpikeMonitor(
        polygon_api_key=API_KEY,
        watchlist_manager=MockWatchlist()
    )
    
    if WEBHOOK:
        monitor.set_discord_webhook(WEBHOOK)
    
    print("=" * 80)
    print("REAL-TIME VOLUME SPIKE MONITOR - TEST MODE")
    print("=" * 80)
    print(f"\nMarket hours active: {monitor.is_market_hours()}")
    print("\nRunning single check...\n")
    
    alerts = monitor.run_single_check()
    
    print("\n" + "=" * 80)
    print(f"Check complete: {alerts} alerts sent")
    monitor.print_stats()
    print("=" * 80)
