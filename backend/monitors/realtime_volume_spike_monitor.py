"""
backend/monitors/realtime_volume_spike_monitor.py v2.1
ENHANCED Real-Time Volume Spike Monitor - Day Trading Edition

IMPROVEMENTS v2.1:
- Uses VolumeAnalyzer v2.0 with progressive checking (30-45s faster alerts)
- Day trader thresholds: 1.5x/1.8x/2.3x/3.5x (was 2.5x/4.0x/6.0x)
- Leverages VolumeAnalyzer's quality scoring (volume + price confirmation)
- Fixed Discord webhook access (works with DiscordAlerter)
- Tiered alert urgency: WATCH/MEDIUM/HIGH/CRITICAL
- Smart check intervals: 15s during active periods

FOR 7-FIGURE DAY TRADERS - Catch moves early, not late

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
    def __init__(self, polygon_api_key: str, config: dict = None, watchlist_manager=None,
                 discord_alerter=None, trading_style: str = 'day_trader'):
        """
        Initialize ENHANCED Real-Time Volume Spike Monitor v2.1
        
        Args:
            polygon_api_key: Polygon.io API key
            config: Configuration dictionary from config.yaml
            watchlist_manager: Watchlist manager instance
            discord_alerter: DiscordAlerter instance (NEW)
            trading_style: 'day_trader' (balanced), 'scalper' (fastest), 'swing_trader' (conservative)
        """
        self.polygon_api_key = polygon_api_key
        self.config = config or {}
        self.watchlist_manager = watchlist_manager
        self.discord = discord_alerter  # NEW: Use DiscordAlerter
        self.trading_style = trading_style
        self.logger = logging.getLogger(__name__)
        
        # Initialize Volume Analyzer v2.0 with trading style
        self.volume_analyzer = VolumeAnalyzer(polygon_api_key, trading_style=trading_style)
        
        # Session-aware check intervals (OPTIMIZED for day trading)
        self.check_intervals = {
            'FIRST_HOUR': 15,   # 15s during opening volatility (was 20s)
            'POWER_HOUR': 15,   # 15s during closing volatility (was 20s)
            'MID_DAY': 20,      # 20s during mid-day (was 30s)
            'PRE_MARKET': 30,   # 30s pre-market (was 45s)
            'AFTER_HOURS': 45   # 45s after-hours (was 60s)
        }
        
        # Cooldown settings (per symbol per session)
        self.cooldown_minutes = {
            'BUILDING': 10,     # 10 min for building volume
            'ELEVATED': 8,      # 8 min for elevated spikes
            'HIGH': 5,          # 5 min for high spikes
            'EXTREME': 3,       # 3 min for extreme spikes
            'PARABOLIC': 3      # 3 min for parabolic moves
        }
        
        # Minimum quality threshold (from VolumeAnalyzer v2.0)
        self.min_quality_score = 40  # Quality score must be ≥40
        
        # State tracking
        self.enabled = True
        self.watchlist = []
        self.alert_cooldowns = {}  # {(symbol, classification): last_alert_time}
        
        # Stats
        self.stats = {
            'total_checks': 0,
            'spikes_detected': 0,
            'alerts_sent': 0,
            'filtered_by_quality': 0,
            'filtered_by_cooldown': 0,
            'last_check': None,
            'timing_advantage_total': 0,  # Total seconds saved vs old method
            'api_calls': 0
        }
        
        self.logger.info("🚀 Real-Time Volume Spike Monitor v2.1 initialized")
        self.logger.info(f"   🎯 Trading style: {trading_style}")
        self.logger.info(f"   📏 Thresholds: {self.volume_analyzer.threshold_elevated}x / "
                        f"{self.volume_analyzer.threshold_high}x / "
                        f"{self.volume_analyzer.threshold_extreme}x")
        self.logger.info(f"   ⏱️ Check intervals: First Hour=15s, Power Hour=15s, Mid-Day=20s")
        self.logger.info(f"   ✅ Progressive checking enabled (30-45s faster alerts)")
    
    def get_discord_webhook(self) -> Optional[str]:
        """
        Get Discord webhook URL from DiscordAlerter
        Tries multiple methods to find the webhook
        """
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
    
    def get_check_interval(self, session: str) -> int:
        """Get check interval for current session"""
        return self.check_intervals.get(session, 30)
    
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
    
    def check_cooldown(self, symbol: str, classification: str) -> bool:
        """
        Check if symbol+classification is in cooldown period
        
        Returns:
            True if can send alert, False if in cooldown
        """
        key = (symbol, classification)
        
        if key not in self.alert_cooldowns:
            return True
        
        last_alert = self.alert_cooldowns[key]
        cooldown_minutes = self.cooldown_minutes.get(classification, 8)
        elapsed = (datetime.now() - last_alert).total_seconds() / 60
        
        return elapsed >= cooldown_minutes
    
    def set_cooldown(self, symbol: str, classification: str):
        """Set cooldown for symbol+classification"""
        key = (symbol, classification)
        self.alert_cooldowns[key] = datetime.now()
    
    def check_volume_spike(self, symbol: str, session: str) -> Optional[Dict]:
        """
        Check if symbol has volume spike using VolumeAnalyzer v2.0
        
        Args:
            symbol: Stock symbol
            session: Current session
        
        Returns:
            Volume spike data if detected, None otherwise
        """
        try:
            # Use VolumeAnalyzer v2.0 with progressive checking
            if session in ['PRE_MARKET']:
                spike_data = self.volume_analyzer.calculate_premarket_rvol(symbol)
            else:
                # Use progressive spike detection (30-45s faster!)
                spike_data = self.volume_analyzer.calculate_progressive_spike(
                    symbol, 
                    check_partial_bar=True
                )
            
            if not spike_data or not spike_data.get('spike_detected'):
                return None
            
            # VolumeAnalyzer already classified the spike
            classification = spike_data.get('classification')
            quality_score = spike_data.get('quality_score', 0)
            
            # Quality filter: Must meet minimum quality score
            if quality_score < self.min_quality_score:
                self.stats['filtered_by_quality'] += 1
                self.logger.debug(f"{symbol}: Quality score {quality_score} below threshold {self.min_quality_score}")
                return None
            
            self.stats['spikes_detected'] += 1
            
            # Track timing advantage
            timing_advantage = spike_data.get('timing_advantage_seconds', 0)
            self.stats['timing_advantage_total'] += timing_advantage
            
            return {
                'symbol': symbol,
                'classification': classification,
                'spike_ratio': spike_data.get('spike_ratio', 0),
                'rvol': spike_data.get('rvol', spike_data.get('spike_ratio', 0)),
                'current_volume': spike_data.get('current_bar_volume', 0) or spike_data.get('current_5min_volume', 0),
                'avg_volume': spike_data.get('avg_previous_volume', 0) or spike_data.get('avg_hist_5min_volume', 0),
                'direction': spike_data.get('direction', 'UNKNOWN'),
                'price_change_pct': spike_data.get('price_change_pct', 0),
                'quality_score': quality_score,
                'alert_urgency': spike_data.get('alert_urgency', 'MEDIUM'),
                'emoji': spike_data.get('emoji', '📊'),
                'timing_advantage_seconds': timing_advantage,
                'session': session,
                'timestamp': datetime.now().isoformat()
            }
            
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
            self.logger.warning("Discord webhook not configured for volume spikes")
            return False
        
        try:
            symbol = spike_data['symbol']
            classification = spike_data['classification']
            spike_ratio = spike_data['spike_ratio']
            direction = spike_data['direction']
            price_change = spike_data['price_change_pct']
            quality_score = spike_data['quality_score']
            urgency = spike_data['alert_urgency']
            emoji = spike_data['emoji']
            timing_advantage = spike_data['timing_advantage_seconds']
            session = spike_data['session']
            
            # Determine color based on urgency
            color_map = {
                'CRITICAL': 0xff0000,  # Red
                'HIGH': 0xff6600,      # Orange
                'MEDIUM': 0xffaa00,    # Yellow
                'WATCH': 0x00aaff      # Blue
            }
            color = color_map.get(urgency, 0xffaa00)
            
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
            
            # Session display
            session_display = session.replace('_', ' ').title()
            
            # Build embed
            embed = {
                'title': f'{emoji} {symbol} - VOLUME SPIKE',
                'description': f'**{classification}** - {urgency} urgency - {direction}',
                'color': color,
                'timestamp': datetime.utcnow().isoformat(),
                'fields': [
                    {
                        'name': '📊 Volume Spike',
                        'value': (
                            f'**Ratio:** {spike_ratio:.2f}x\n'
                            f'**Classification:** {classification}\n'
                            f'**Quality Score:** {quality_score}/100'
                        ),
                        'inline': True
                    },
                    {
                        'name': f'{price_emoji} Price Action',
                        'value': (
                            f'**Change:** {price_text}\n'
                            f'**Direction:** {direction}\n'
                            f'**Urgency:** {urgency}'
                        ),
                        'inline': True
                    },
                    {
                        'name': '⚡ Speed Advantage',
                        'value': f'**{timing_advantage}s faster** than old method',
                        'inline': False
                    } if timing_advantage > 0 else None,
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
                    'text': f'Real-Time Monitor v2.1 • {self.trading_style} mode'
                }
            }
            
            # Remove None fields
            embed['fields'] = [f for f in embed['fields'] if f is not None]
            
            # Add action guidance
            if classification in ['EXTREME', 'PARABOLIC']:
                embed['fields'].append({
                    'name': '⚠️ Action Required',
                    'value': f'**{classification} volume** - Check for catalyst! Major move likely.',
                    'inline': False
                })
            elif classification == 'HIGH':
                embed['fields'].append({
                    'name': '👀 Action',
                    'value': 'Significant volume - Monitor for entry opportunity.',
                    'inline': False
                })
            elif classification == 'BUILDING':
                embed['fields'].append({
                    'name': '📈 Watch',
                    'value': 'Volume building - Setup may be forming.',
                    'inline': False
                })
            
            payload = {'embeds': [embed]}
            
            # Send with retry logic
            success = self.send_alert_with_retry(webhook_url, payload)
            
            if success:
                self.stats['alerts_sent'] += 1
                self.logger.info(
                    f"✅ Volume spike alert sent: {symbol} "
                    f"({classification}, {spike_ratio:.2f}x, {price_text}) [{session_display}]"
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
        
        if session == 'CLOSED':
            return 0
        
        self.stats['total_checks'] += 1
        self.stats['last_check'] = datetime.now().isoformat()
        
        # Load watchlist
        if not self.watchlist:
            self.load_watchlist()
        
        if not self.watchlist:
            return 0
        
        alerts_sent = 0
        
        for symbol in self.watchlist:
            try:
                # Check for volume spike
                spike_data = self.check_volume_spike(symbol, session)
                
                if not spike_data:
                    continue
                
                classification = spike_data['classification']
                
                # Check cooldown
                if not self.check_cooldown(symbol, classification):
                    self.stats['filtered_by_cooldown'] += 1
                    self.logger.debug(f"{symbol}: {classification} in cooldown")
                    continue
                
                # Send alert
                success = self.send_discord_alert(spike_data)
                
                if success:
                    self.set_cooldown(symbol, classification)
                    alerts_sent += 1
                
                # Small delay between symbols
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Error processing {symbol}: {str(e)}")
                continue
        
        if alerts_sent > 0:
            avg_advantage = self.stats['timing_advantage_total'] / self.stats['spikes_detected']
            self.logger.info(
                f"✅ Volume check complete: {alerts_sent} alerts sent "
                f"(avg {avg_advantage:.0f}s faster) [{session}]"
            )
        
        return alerts_sent
    
    def run_continuous(self):
        """Run continuous monitoring with session-aware intervals"""
        self.logger.info("🚀 Starting Real-Time Volume Spike Monitor v2.1 (continuous mode)")
        self.logger.info(f"   🎯 Trading style: {self.trading_style}")
        
        try:
            while self.enabled:
                try:
                    session = self.get_current_session()
                    
                    if session != 'CLOSED':
                        self.run_single_check()
                    
                    # Dynamic check interval based on session
                    check_interval = self.get_check_interval(session)
                    time.sleep(check_interval)
                    
                except Exception as e:
                    self.logger.error(f"Error in check cycle: {str(e)}")
                    import traceback
                    self.logger.debug(traceback.format_exc())
                    time.sleep(30)
                    
        except KeyboardInterrupt:
            self.logger.info("Stopping volume spike monitor...")
            self.print_stats()
    
    def print_stats(self):
        """Print monitor statistics"""
        print("\n" + "=" * 60)
        print("REAL-TIME VOLUME SPIKE MONITOR STATISTICS")
        print("=" * 60)
        print(f"Total Checks: {self.stats['total_checks']}")
        print(f"Spikes Detected: {self.stats['spikes_detected']}")
        print(f"Alerts Sent: {self.stats['alerts_sent']}")
        print(f"Filtered by Quality: {self.stats['filtered_by_quality']}")
        print(f"Filtered by Cooldown: {self.stats['filtered_by_cooldown']}")
        if self.stats['spikes_detected'] > 0:
            avg_advantage = self.stats['timing_advantage_total'] / self.stats['spikes_detected']
            print(f"Average Timing Advantage: {avg_advantage:.0f} seconds vs old method")
        print("=" * 60 + "\n")


if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    API_KEY = os.getenv('POLYGON_API_KEY')
    
    monitor = RealtimeVolumeSpikeMonitor(API_KEY, trading_style='day_trader')
    monitor.watchlist = ['SPY', 'QQQ', 'NVDA', 'TSLA', 'AMD']
    
    print("\n🔍 Running test check...")
    alerts = monitor.run_single_check()
    print(f"\n✅ Test complete: {alerts} alerts sent")
    monitor.print_stats()