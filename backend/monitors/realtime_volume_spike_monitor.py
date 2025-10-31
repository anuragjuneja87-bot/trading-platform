"""
backend/monitors/realtime_volume_spike_monitor.py
OPTIMIZED Real-Time Volume Spike Monitor v2.0
Professional day trader configuration

NEW FEATURES:
- Session-aware thresholds (market/pre-market/after-hours)
- Dynamic check intervals (first hour: 20s, power hour: 20s, mid-day: 30s)
- VWAP proximity filtering (alert when price near VWAP)
- Configurable via config.yaml (no code edits needed)
- All original features preserved

Monitors watchlist for volume spikes with professional-grade filtering
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


class RealtimeVolumeSpikeMonitor:
    def __init__(self, polygon_api_key: str, discord_alerter=None, config: dict = None, watchlist_manager=None):
        """
        Initialize OPTIMIZED Real-Time Volume Spike Monitor
        
        Args:
            polygon_api_key: Polygon.io API key
            discord_alerter: Discord alerter instance from AlertManager
            config: Configuration dictionary from config.yaml
            watchlist_manager: Watchlist manager instance
        """
        self.polygon_api_key = polygon_api_key
        self.discord_alerter = discord_alerter
        self.config = config or {}
        self.watchlist_manager = watchlist_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize Volume Analyzer
        self.volume_analyzer = VolumeAnalyzer(polygon_api_key)
        
        # Load configuration from config.yaml
        self._load_configuration()
        
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
            'filtered_by_vwap': 0,
            'last_check': None,
            'api_calls': 0
        }
        
        self.logger.info("🚀 OPTIMIZED Real-Time Volume Spike Monitor v2.0 initialized")
        self._log_configuration()
    
    def _load_configuration(self):
        """Load configuration from config.yaml"""
        realtime_config = self.config.get('realtime_volume_spike', {})
        
        # Market hours configuration
        market_config = realtime_config.get('market_hours', {})
        self.market_thresholds = market_config.get('thresholds', {
            'elevated': 2.5,
            'high': 4.0,
            'extreme': 6.0
        })
        self.market_min_price_change = market_config.get('min_price_change_pct', 1.0)
        self.market_check_intervals = market_config.get('check_intervals', {
            'first_hour': 20,
            'power_hour': 20,
            'mid_day': 30
        })
        self.market_cooldown = market_config.get('cooldown_minutes', 8)
        self.market_vwap_config = market_config.get('vwap_filter', {
            'enabled': True,
            'proximity_pct': 0.5,
            'require_proximity': False
        })
        
        # Pre-market configuration
        premarket_config = realtime_config.get('pre_market', {})
        self.premarket_thresholds = premarket_config.get('thresholds', {
            'elevated': 3.5,
            'high': 5.0,
            'extreme': 8.0
        })
        self.premarket_min_price_change = premarket_config.get('min_price_change_pct', 1.5)
        self.premarket_check_interval = premarket_config.get('check_interval', 45)
        self.premarket_cooldown = premarket_config.get('cooldown_minutes', 15)
        self.premarket_vwap_config = premarket_config.get('vwap_filter', {
            'enabled': True,
            'proximity_pct': 0.75,
            'require_proximity': False
        })
        
        # After hours configuration
        afterhours_config = realtime_config.get('after_hours', {})
        self.afterhours_thresholds = afterhours_config.get('thresholds', {
            'elevated': 3.5,
            'high': 5.0,
            'extreme': 8.0
        })
        self.afterhours_min_price_change = afterhours_config.get('min_price_change_pct', 1.5)
        self.afterhours_check_interval = afterhours_config.get('check_interval', 60)
        self.afterhours_cooldown = afterhours_config.get('cooldown_minutes', 15)
        self.afterhours_vwap_config = afterhours_config.get('vwap_filter', {
            'enabled': False
        })
    
    def _log_configuration(self):
        """Log current configuration"""
        self.logger.info("📋 Configuration:")
        self.logger.info(f"   Market Hours Thresholds: {self.market_thresholds}")
        self.logger.info(f"   Market Price Filter: ±{self.market_min_price_change}%")
        self.logger.info(f"   Market Check Intervals: First Hour={self.market_check_intervals['first_hour']}s, Power Hour={self.market_check_intervals['power_hour']}s, Mid-Day={self.market_check_intervals['mid_day']}s")
        self.logger.info(f"   Market Cooldown: {self.market_cooldown} min")
        self.logger.info(f"   Market VWAP Filter: {self.market_vwap_config}")
        self.logger.info(f"   Pre-Market Thresholds: {self.premarket_thresholds}")
        self.logger.info(f"   Pre-Market Price Filter: ±{self.premarket_min_price_change}%")
        self.logger.info(f"   Pre-Market Check Interval: {self.premarket_check_interval}s")
    
    def get_current_session(self) -> str:
        """
        Determine current trading session
        Returns: 'PRE_MARKET', 'FIRST_HOUR', 'MID_DAY', 'POWER_HOUR', 'AFTER_HOURS', 'CLOSED'
        """
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        current_minutes = hour * 60 + minute
        day_of_week = now.weekday()
        
        # Only weekdays
        if day_of_week >= 5:
            return 'CLOSED'
        
        # Define session times (in minutes from midnight)
        premarket_start = 4 * 60  # 4:00 AM
        market_open = 9 * 60 + 30  # 9:30 AM
        first_hour_end = 10 * 60 + 30  # 10:30 AM
        power_hour_start = 15 * 60  # 3:00 PM
        market_close = 16 * 60  # 4:00 PM
        afterhours_end = 20 * 60  # 8:00 PM
        
        if current_minutes < premarket_start:
            return 'CLOSED'
        elif current_minutes < market_open:
            return 'PRE_MARKET'
        elif current_minutes < first_hour_end:
            return 'FIRST_HOUR'
        elif current_minutes < power_hour_start:
            return 'MID_DAY'
        elif current_minutes < market_close:
            return 'POWER_HOUR'
        elif current_minutes < afterhours_end:
            return 'AFTER_HOURS'
        else:
            return 'CLOSED'
    
    def get_session_config(self, session: str) -> Dict:
        """
        Get configuration for current session
        
        Returns:
            Dict with thresholds, check_interval, cooldown, price_filter, vwap_config
        """
        if session == 'PRE_MARKET':
            return {
                'thresholds': self.premarket_thresholds,
                'check_interval': self.premarket_check_interval,
                'cooldown_minutes': self.premarket_cooldown,
                'min_price_change': self.premarket_min_price_change,
                'vwap_config': self.premarket_vwap_config
            }
        elif session == 'AFTER_HOURS':
            return {
                'thresholds': self.afterhours_thresholds,
                'check_interval': self.afterhours_check_interval,
                'cooldown_minutes': self.afterhours_cooldown,
                'min_price_change': self.afterhours_min_price_change,
                'vwap_config': self.afterhours_vwap_config
            }
        elif session in ['FIRST_HOUR', 'POWER_HOUR']:
            return {
                'thresholds': self.market_thresholds,
                'check_interval': self.market_check_intervals.get(session.lower(), 20),
                'cooldown_minutes': self.market_cooldown,
                'min_price_change': self.market_min_price_change,
                'vwap_config': self.market_vwap_config
            }
        else:  # MID_DAY
            return {
                'thresholds': self.market_thresholds,
                'check_interval': self.market_check_intervals.get('mid_day', 30),
                'cooldown_minutes': self.market_cooldown,
                'min_price_change': self.market_min_price_change,
                'vwap_config': self.market_vwap_config
            }
    
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
    
    def is_cooldown_active(self, symbol: str, cooldown_minutes: int) -> bool:
        """Check if symbol is in cooldown period"""
        if symbol not in self.alert_cooldowns:
            return False
        
        last_alert = self.alert_cooldowns[symbol]
        elapsed = (datetime.now() - last_alert).total_seconds() / 60
        
        return elapsed < cooldown_minutes
    
    def set_cooldown(self, symbol: str):
        """Set cooldown for symbol"""
        self.alert_cooldowns[symbol] = datetime.now()
    
    def get_live_price(self, symbol: str) -> Optional[Dict]:
        """
        Get LIVE current price (no caching)
        Returns: {'price': float, 'change_pct': float, 'timestamp': datetime}
        """
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
    
    def get_live_vwap(self, symbol: str) -> Optional[float]:
        """Get LIVE VWAP from snapshot endpoint"""
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
            self.logger.error(f"Error getting VWAP for {symbol}: {str(e)}")
            return None
    
    def check_vwap_proximity(self, price: float, vwap: float, proximity_pct: float) -> bool:
        """
        Check if price is within proximity % of VWAP
        
        Args:
            price: Current price
            vwap: VWAP value
            proximity_pct: Proximity threshold (e.g., 0.5 = within 0.5%)
        
        Returns:
            True if within proximity, False otherwise
        """
        if not vwap or vwap == 0:
            return False
        
        distance_pct = abs((price - vwap) / vwap) * 100
        return distance_pct <= proximity_pct
    
    def check_volume_spike(self, symbol: str, session: str, session_config: Dict) -> Optional[Dict]:
        """
        Check if symbol has volume spike with session-specific thresholds
        
        Args:
            symbol: Stock symbol
            session: Current session
            session_config: Configuration for current session
        
        Returns:
            Volume spike data if detected, None otherwise
        """
        try:
            # Get LIVE RVOL (no caching)
            rvol_data = self.volume_analyzer.calculate_rvol(symbol)
            
            if not rvol_data or rvol_data.get('rvol', 0) == 0:
                return None
            
            rvol = rvol_data.get('rvol', 0)
            thresholds = session_config['thresholds']
            
            # Determine classification based on session thresholds
            if rvol >= thresholds['extreme']:
                classification = 'EXTREME'
            elif rvol >= thresholds['high']:
                classification = 'HIGH'
            elif rvol >= thresholds['elevated']:
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
                'timestamp': datetime.now().isoformat(),
                'session': session
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
    
    def send_discord_alert(self, spike_data: Dict, session: str) -> bool:
        """
        Send Discord alert for volume spike with session context
        
        Args:
            spike_data: Volume spike information
            session: Current session (for display)
        
        Returns:
            True if sent successfully
        """
        if not self.discord_alerter:
            self.logger.warning("Discord alerter not configured")
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
            
            # VWAP proximity indicator
            vwap_indicator = ''
            if vwap and current_price:
                distance_pct = abs((current_price - vwap) / vwap) * 100
                if distance_pct <= 0.5:
                    vwap_indicator = ' 🎯 **AT VWAP**'
                elif distance_pct <= 1.0:
                    vwap_indicator = ' 📍 **NEAR VWAP**'
            
            # Session display
            session_display = session.replace('_', ' ').title()
            
            # Calculate volume vs expected
            vol_vs_expected = ((current_vol - expected_vol) / expected_vol * 100) if expected_vol > 0 else 0
            
            # Build embed
            embed = {
                'title': f'{emoji} {symbol} - {urgency_text}',
                'description': f'**{classification}** volume detected{vwap_indicator}',
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
                        'value': session_display,
                        'inline': True
                    }
                ],
                'footer': {
                    'text': f'Real-Time Monitor v2.0 • Session-aware detection'
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
            
            payload = {'embeds': [embed]}
            
            # Send via discord_alerter
            self.discord_alerter.send_webhook('VOLUME_SPIKE', payload)
            
            self.stats['alerts_sent'] += 1
            self.logger.info(
                f"✅ Volume spike alert sent: {symbol} "
                f"({rvol:.2f}x, {price_text}, ${current_price:.2f}) [{session_display}]"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send Discord alert: {str(e)}")
            return False
    
    def run_single_check(self) -> int:
        """
        Run a single check cycle with session-aware configuration
        
        Returns:
            Number of alerts sent
        """
        alerts_sent = 0
        
        # Get current session
        session = self.get_current_session()
        
        if session == 'CLOSED':
            self.logger.debug("Market closed, skipping check")
            return 0
        
        # Get session configuration
        session_config = self.get_session_config(session)
        
        # Load watchlist
        if not self.watchlist:
            self.load_watchlist()
        
        if not self.watchlist:
            self.logger.warning("Empty watchlist, nothing to monitor")
            return 0
        
        self.logger.info(
            f"🔍 {session.replace('_', ' ')} check: {len(self.watchlist)} symbols "
            f"(Interval: {session_config['check_interval']}s, "
            f"RVOL≥{session_config['thresholds']['elevated']}x, "
            f"Price≥{session_config['min_price_change']}%)"
        )
        
        for symbol in self.watchlist:
            try:
                # Skip if in cooldown
                if self.is_cooldown_active(symbol, session_config['cooldown_minutes']):
                    continue
                
                # Check for volume spike with session config
                spike_data = self.check_volume_spike(symbol, session, session_config)
                
                if spike_data:
                    # Apply price movement filter
                    price_change = abs(spike_data['price_change_pct'])
                    
                    if price_change < session_config['min_price_change']:
                        self.logger.debug(
                            f"{symbol}: Volume spike detected but price change "
                            f"({price_change:.2f}%) below minimum ({session_config['min_price_change']}%)"
                        )
                        self.stats['filtered_by_price'] += 1
                        continue
                    
                    # Apply VWAP filter if enabled
                    vwap_config = session_config['vwap_config']
                    if vwap_config.get('enabled', False):
                        vwap = spike_data.get('vwap')
                        price = spike_data['current_price']
                        
                        if vwap and price:
                            near_vwap = self.check_vwap_proximity(
                                price, 
                                vwap, 
                                vwap_config.get('proximity_pct', 0.5)
                            )
                            
                            # If require_proximity is True, only alert if near VWAP
                            if vwap_config.get('require_proximity', False) and not near_vwap:
                                self.logger.debug(
                                    f"{symbol}: Not near VWAP "
                                    f"(Price: ${price:.2f}, VWAP: ${vwap:.2f})"
                                )
                                self.stats['filtered_by_vwap'] += 1
                                continue
                    
                    self.logger.info(
                        f"🚨 {symbol}: Volume spike detected! "
                        f"RVOL {spike_data['rvol']:.2f}x ({spike_data['classification']}), "
                        f"Price ${spike_data['current_price']:.2f} ({spike_data['price_change_pct']:+.2f}%)"
                    )
                    
                    # Send alert
                    if self.send_discord_alert(spike_data, session):
                        alerts_sent += 1
                        self.set_cooldown(symbol)
                    else:
                        self.stats['filtered_by_cooldown'] += 1
                
                # Small delay to avoid rate limits
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Error checking {symbol}: {str(e)}")
                continue
        
        self.stats['total_checks'] += 1
        self.stats['last_check'] = datetime.now().isoformat()
        
        if alerts_sent > 0:
            self.logger.info(f"✅ Sent {alerts_sent} volume spike alerts")
        
        return alerts_sent
    
    def run_continuous(self):
        """Run monitor continuously with dynamic intervals"""
        self.logger.info("🚀 Starting OPTIMIZED Real-Time Volume Spike Monitor (continuous mode)")
        self.logger.info("   Session-aware: Pre-market, First Hour, Mid-Day, Power Hour, After Hours")
        
        # Load watchlist initially
        self.load_watchlist()
        
        while self.enabled:
            try:
                session = self.get_current_session()
                
                if session != 'CLOSED':
                    self.run_single_check()
                    session_config = self.get_session_config(session)
                    check_interval = session_config['check_interval']
                else:
                    self.logger.debug("Market closed, waiting...")
                    check_interval = 60
                
                # Wait before next check
                time.sleep(check_interval)
                
                # Reload watchlist every 20 checks (~10 minutes)
                if self.stats['total_checks'] % 20 == 0:
                    self.load_watchlist()
                
            except KeyboardInterrupt:
                self.logger.info("Monitor stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {str(e)}")
                time.sleep(30)
    
    def stop(self):
        """Stop the monitor"""
        self.enabled = False
        self.logger.info("Real-time monitor stopped")
        self.print_stats()
    
    def print_stats(self):
        """Print monitor statistics"""
        print("\n" + "=" * 60)
        print("OPTIMIZED REAL-TIME VOLUME SPIKE MONITOR STATISTICS")
        print("=" * 60)
        print(f"Total Checks: {self.stats['total_checks']}")
        print(f"Spikes Detected: {self.stats['spikes_detected']}")
        print(f"Alerts Sent: {self.stats['alerts_sent']}")
        print(f"Filtered by Price: {self.stats['filtered_by_price']}")
        print(f"Filtered by VWAP: {self.stats['filtered_by_vwap']}")
        print(f"Filtered by Cooldown: {self.stats['filtered_by_cooldown']}")
        print(f"API Calls: {self.stats['api_calls']}")
        print(f"Last Check: {self.stats['last_check']}")
        print("=" * 60 + "\n")


# CLI Testing
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    import yaml
    
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
    
    # Load config
    config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Create simple watchlist manager mock
    class MockWatchlist:
        def load_symbols(self):
            return ['SPY', 'QQQ', 'NVDA', 'TSLA', 'AAPL']
    
    monitor = RealtimeVolumeSpikeMonitor(
        polygon_api_key=API_KEY,
        config=config,
        watchlist_manager=MockWatchlist()
    )
    
    if WEBHOOK:
        monitor.set_discord_webhook(WEBHOOK)
    
    print("=" * 80)
    print("OPTIMIZED REAL-TIME VOLUME SPIKE MONITOR v2.0 - TEST MODE")
    print("=" * 80)
    print(f"\nCurrent session: {monitor.get_current_session()}")
    print("\nRunning single check...\n")
    
    alerts = monitor.run_single_check()
    
    print("\n" + "=" * 80)
    print(f"Check complete: {alerts} alerts sent")
    monitor.print_stats()
    print("=" * 80)