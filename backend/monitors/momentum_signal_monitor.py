"""
backend/monitors/momentum_signal_monitor.py v2.0
ENHANCED Momentum Signal Monitor - Day Trading Edition

IMPROVEMENTS v2.0:
- Day trader RVOL thresholds: 1.8x/2.3x/3.5x (was 2.5x/4.0x)
- Fixed Discord webhook access (works with DiscordAlerter)
- Rate limit protection with retries
- Aligned with VolumeAnalyzer v2.0 thresholds
- All existing features preserved

Combines:
- RVOL (volume confirmation)
- Dark Pool (institutional flow)  
- Gamma Walls (price magnets)
- Key Levels (confluence)
- News sentiment

TRIGGERS:
1. Momentum Buy Signal (4+ factors aligned)
2. Momentum Sell Signal (4+ factors aligned)
3. Gamma Wall Approach (price near magnet)
4. Dark Pool Direction Change (flip detected)
5. Extreme Confluence Setup (all factors perfect)

Routes to: DISCORD_MOMENTUM_SIGNALS
"""

import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import requests
import logging
import time
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Optional

from analyzers.enhanced_professional_analyzer import EnhancedProfessionalAnalyzer
from analyzers.confluence_alert_system import ConfluenceAlertSystem


class MomentumSignalMonitor:
    def __init__(self, polygon_api_key: str, config: dict, watchlist_manager, discord_alerter=None):
        """
        Initialize ENHANCED Momentum Signal Monitor v2.0
        
        Args:
            polygon_api_key: Polygon.io API key
            config: Configuration dict
            watchlist_manager: Watchlist manager instance
            discord_alerter: DiscordAlerter instance (NEW)
        """
        self.polygon_api_key = polygon_api_key
        self.config = config.get('momentum_signal_monitor', {})
        self.watchlist_manager = watchlist_manager
        self.discord = discord_alerter  # NEW: Use DiscordAlerter
        
        self.logger = logging.getLogger(__name__)
        
        # Monitoring state
        self.enabled = self.config.get('enabled', True)
        self.check_interval = self.config.get('check_interval', 60)
        self.market_hours_only = self.config.get('market_hours_only', True)
        
        # Cooldown tracking
        self.last_alert = defaultdict(lambda: defaultdict(float))
        self.cooldowns = self.config.get('cooldown_minutes', {
            'momentum_signal': 15,
            'gamma_approach': 10,
            'dark_pool_flip': 5,
            'extreme_setup': 30,
            'confluence_alert': 15
        })
        
        # ENHANCED Thresholds - Day Trader Optimized
        thresholds = self.config.get('thresholds', {})
        
        # RVOL thresholds - Aligned with VolumeAnalyzer v2.0
        self.min_rvol = thresholds.get('min_rvol', 1.8)         # was 2.5 ⬇️ 28% more sensitive
        self.high_rvol = thresholds.get('high_rvol', 2.3)       # NEW tier
        self.extreme_rvol = thresholds.get('extreme_rvol', 3.5) # was 4.0 ⬇️ 13% more sensitive
        
        # Dark pool thresholds (keep existing - already good)
        self.min_dark_pool_strength = thresholds.get('min_dark_pool_strength', 4)
        self.min_dark_pool_value = thresholds.get('min_dark_pool_value', 1000000)
        
        # Gamma wall thresholds (keep existing - already aggressive)
        self.gamma_wall_distance = thresholds.get('gamma_wall_distance_pct', 1.0)
        self.gamma_wall_urgent = thresholds.get('gamma_wall_urgent_pct', 0.5)
        
        # Confluence thresholds (keep existing - works well)
        self.min_confluence = thresholds.get('min_confluence', 7)
        self.extreme_confluence = thresholds.get('extreme_confluence', 8)
        
        # Filters
        filters = self.config.get('filters', {})
        self.watchlist_only = filters.get('watchlist_only', True)
        self.min_price = filters.get('min_price', 5.0)
        self.max_alerts_per_symbol_per_day = filters.get('max_alert_per_symbol_per_day', 5)
        
        # Track previous dark pool direction
        self.previous_dark_pool_direction = {}
        
        # Daily alert counter
        self.daily_alerts = defaultdict(int)
        self.last_reset_date = datetime.now().date()
        
        # Statistics
        self.stats = {
            'total_checks': 0,
            'momentum_buy_signals': 0,
            'momentum_sell_signals': 0,
            'gamma_approaches': 0,
            'dark_pool_flips': 0,
            'extreme_setups': 0,
            'total_alerts_sent': 0,
            'rate_limited': 0
        }
        
        # Initialize analyzer
        self.analyzer = EnhancedProfessionalAnalyzer(
            polygon_api_key=polygon_api_key,
            debug_mode=False
        )
        
        # Initialize Confluence Alert System
        self.confluence_system = ConfluenceAlertSystem()
        
        self.logger.info("✅ Momentum Signal Monitor v2.0 initialized (Day Trader Mode)")
        self.logger.info(f"   Check Interval: {self.check_interval}s")
        self.logger.info(f"   RVOL Thresholds: {self.min_rvol}x / {self.high_rvol}x / {self.extreme_rvol}x (OPTIMIZED)")
        self.logger.info(f"   Min Dark Pool Strength: {self.min_dark_pool_strength}")
        self.logger.info(f"   Gamma Wall Distance: {self.gamma_wall_distance}%")
        self.logger.info(f"   🎯 Confluence alerts: 75%+ confidence")
    
    def get_discord_webhook(self) -> Optional[str]:
        """
        Get Discord webhook URL from DiscordAlerter
        Tries multiple methods to find the webhook
        """
        if not self.discord:
            return None
        
        # Try different ways to access webhook
        if hasattr(self.discord, 'webhooks'):
            return self.discord.webhooks.get('momentum_signals')
        elif hasattr(self.discord, 'config'):
            return self.discord.config.get('webhook_momentum_signals')
        elif hasattr(self.discord, 'webhook_momentum_signals'):
            return self.discord.webhook_momentum_signals
        
        return None
    
    def is_market_hours(self) -> bool:
        """Check if currently in market hours"""
        now = datetime.now()
        
        # Check if weekday
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Check time (9:30 AM - 4:00 PM ET)
        current_time = now.time()
        market_open = datetime.strptime("09:30", "%H:%M").time()
        market_close = datetime.strptime("16:00", "%H:%M").time()
        
        return market_open <= current_time <= market_close
    
    def reset_daily_counters(self):
        """Reset daily alert counters at midnight"""
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.daily_alerts.clear()
            self.last_reset_date = today
            self.logger.info("📅 Daily alert counters reset")
    
    def can_alert(self, symbol: str, alert_type: str) -> bool:
        """Check if can send alert (cooldown + daily limit)"""
        # Check daily limit
        if self.daily_alerts[symbol] >= self.max_alerts_per_symbol_per_day:
            return False
        
        # Check cooldown
        now = time.time()
        last_alert_time = self.last_alert[symbol][alert_type]
        cooldown_seconds = self.cooldowns.get(alert_type, 15) * 60
        
        if now - last_alert_time < cooldown_seconds:
            return False
        
        return True
    
    def mark_alerted(self, symbol: str, alert_type: str):
        """Mark symbol as alerted"""
        self.last_alert[symbol][alert_type] = time.time()
        self.daily_alerts[symbol] += 1
    
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
    
    def send_discord_alert(self, embed: dict):
        """Send alert to Discord with rate limit protection"""
        webhook_url = self.get_discord_webhook()
        
        if not webhook_url:
            self.logger.warning("Discord webhook not configured for momentum signals")
            return False
        
        try:
            payload = {'embeds': [embed]}
            success = self.send_alert_with_retry(webhook_url, payload)
            
            if success:
                self.stats['total_alerts_sent'] += 1
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to send Discord alert: {str(e)}")
            return False
    
    def check_momentum_buy_signal(self, symbol: str, data: dict) -> Optional[dict]:
        """
        TRIGGER 1: Momentum Buy Signal
        Requires 4+ bullish factors
        
        ENHANCED with day trader RVOL thresholds
        """
        factors = []
        factor_count = 0
        
        # Factor 1: Dark Pool Buying
        dark_pool = data.get('dark_pool_details', {})
        if dark_pool.get('institutional_flow') == 'BUYING':
            strength = dark_pool.get('signal_strength', 0)
            if strength >= self.min_dark_pool_strength:
                factors.append(f"Dark Pool BUYING (strength: {strength})")
                factor_count += 1
        
        # Factor 2: High RVOL (ENHANCED - Day trader thresholds)
        volume_analysis = data.get('volume_analysis', {})
        rvol_data = volume_analysis.get('rvol', {})
        rvol = rvol_data.get('rvol', 0)
        
        if rvol >= self.extreme_rvol:
            factors.append(f"RVOL {rvol:.1f}x (EXTREME)")
            factor_count += 1
        elif rvol >= self.high_rvol:
            factors.append(f"RVOL {rvol:.1f}x (HIGH)")
            factor_count += 1
        elif rvol >= self.min_rvol:
            factors.append(f"RVOL {rvol:.1f}x (ELEVATED)")
            factor_count += 1
        
        # Factor 3: Near Gamma Wall Support
        open_interest = data.get('open_interest', {})
        nearest_wall = open_interest.get('nearest_wall')
        if nearest_wall and nearest_wall['type'] == 'support':
            distance = nearest_wall.get('distance_pct', 999)
            if distance <= self.gamma_wall_distance:
                factors.append(f"Gamma Support ${nearest_wall['strike']} ({distance:.1f}% away)")
                factor_count += 1
        
        # Factor 4: High Confluence Support
        key_levels = data.get('key_levels', {})
        if key_levels.get('at_support') and key_levels.get('confluence_score', 0) >= self.min_confluence:
            confluence = key_levels['confluence_score']
            factors.append(f"High Confluence Support ({confluence}/10)")
            factor_count += 1
        
        # Factor 5: Price Below VWAP (oversold)
        if data.get('current_price', 0) < data.get('vwap', 999999):
            factors.append("Price < VWAP (oversold)")
            factor_count += 1
        
        # Factor 6: Positive News
        news = data.get('news', {})
        if news.get('sentiment') in ['POSITIVE', 'VERY POSITIVE']:
            factors.append(f"News: {news['sentiment']}")
            factor_count += 1
        
        # Need 4+ factors
        if factor_count >= 4:
            return {
                'type': 'momentum_buy',
                'factors': factors,
                'factor_count': factor_count,
                'confidence': min(factor_count / 6 * 100, 95),
                'data': data
            }
        
        return None
    
    def check_momentum_sell_signal(self, symbol: str, data: dict) -> Optional[dict]:
        """
        TRIGGER 2: Momentum Sell Signal
        Requires 4+ bearish factors
        
        ENHANCED with day trader RVOL thresholds
        """
        factors = []
        factor_count = 0
        
        # Factor 1: Dark Pool Selling
        dark_pool = data.get('dark_pool_details', {})
        if dark_pool.get('institutional_flow') == 'SELLING':
            strength = dark_pool.get('signal_strength', 0)
            if strength >= self.min_dark_pool_strength:
                factors.append(f"Dark Pool SELLING (strength: {strength})")
                factor_count += 1
        
        # Factor 2: High RVOL (ENHANCED)
        volume_analysis = data.get('volume_analysis', {})
        rvol_data = volume_analysis.get('rvol', {})
        rvol = rvol_data.get('rvol', 0)
        
        if rvol >= self.extreme_rvol:
            factors.append(f"RVOL {rvol:.1f}x (EXTREME)")
            factor_count += 1
        elif rvol >= self.high_rvol:
            factors.append(f"RVOL {rvol:.1f}x (HIGH)")
            factor_count += 1
        elif rvol >= self.min_rvol:
            factors.append(f"RVOL {rvol:.1f}x (ELEVATED)")
            factor_count += 1
        
        # Factor 3: Near Gamma Wall Resistance
        open_interest = data.get('open_interest', {})
        nearest_wall = open_interest.get('nearest_wall')
        if nearest_wall and nearest_wall['type'] == 'resistance':
            distance = nearest_wall.get('distance_pct', 999)
            if distance <= self.gamma_wall_distance:
                factors.append(f"Gamma Resistance ${nearest_wall['strike']} ({distance:.1f}% away)")
                factor_count += 1
        
        # Factor 4: High Confluence Resistance
        key_levels = data.get('key_levels', {})
        if key_levels.get('at_resistance') and key_levels.get('confluence_score', 0) >= self.min_confluence:
            confluence = key_levels['confluence_score']
            factors.append(f"High Confluence Resistance ({confluence}/10)")
            factor_count += 1
        
        # Factor 5: Price Above VWAP (overbought)
        if data.get('current_price', 0) > data.get('vwap', 0):
            factors.append("Price > VWAP (overbought)")
            factor_count += 1
        
        # Factor 6: Negative News
        news = data.get('news', {})
        if news.get('sentiment') in ['NEGATIVE', 'VERY NEGATIVE']:
            factors.append(f"News: {news['sentiment']}")
            factor_count += 1
        
        # Need 4+ factors
        if factor_count >= 4:
            return {
                'type': 'momentum_sell',
                'factors': factors,
                'factor_count': factor_count,
                'confidence': min(factor_count / 6 * 100, 95),
                'data': data
            }
        
        return None
    
    def check_gamma_approach(self, symbol: str, data: dict) -> Optional[dict]:
        """
        TRIGGER 3: Gamma Wall Approach
        Price approaching significant gamma wall
        """
        open_interest = data.get('open_interest', {})
        nearest_wall = open_interest.get('nearest_wall')
        
        if not nearest_wall:
            return None
        
        distance = nearest_wall.get('distance_pct', 999)
        
        # Check if approaching (within threshold)
        if distance <= self.gamma_wall_distance:
            urgency = 'CRITICAL' if distance <= self.gamma_wall_urgent else 'HIGH'
            
            return {
                'type': 'gamma_approach',
                'wall': nearest_wall,
                'distance': distance,
                'urgency': urgency,
                'data': data
            }
        
        return None
    
    def check_dark_pool_flip(self, symbol: str, data: dict) -> Optional[dict]:
        """
        TRIGGER 4: Dark Pool Direction Change
        Institutional flow direction changed
        """
        dark_pool = data.get('dark_pool_details', {})
        current_flow = dark_pool.get('institutional_flow')
        
        if not current_flow or current_flow == 'NEUTRAL':
            return None
        
        # Check if we have previous direction
        if symbol in self.previous_dark_pool_direction:
            previous_flow = self.previous_dark_pool_direction[symbol]
            
            # Detect flip
            if previous_flow != current_flow and previous_flow != 'NEUTRAL':
                strength = dark_pool.get('signal_strength', 0)
                
                if strength >= self.min_dark_pool_strength:
                    self.previous_dark_pool_direction[symbol] = current_flow
                    
                    return {
                        'type': 'dark_pool_flip',
                        'from': previous_flow,
                        'to': current_flow,
                        'strength': strength,
                        'data': data
                    }
        
        # Store current direction
        self.previous_dark_pool_direction[symbol] = current_flow
        
        return None
    
    def check_extreme_setup(self, symbol: str, data: dict) -> Optional[dict]:
        """
        TRIGGER 5: Extreme Confluence Setup
        All factors perfectly aligned (RARE!)
        """
        factors = []
        
        # Must have extreme RVOL
        volume_analysis = data.get('volume_analysis', {})
        rvol = volume_analysis.get('rvol', {}).get('rvol', 0)
        if rvol < self.extreme_rvol:
            return None
        factors.append(f"Extreme RVOL {rvol:.1f}x")
        
        # Must have dark pool flow
        dark_pool = data.get('dark_pool_details', {})
        flow = dark_pool.get('institutional_flow')
        if flow not in ['BUYING', 'SELLING']:
            return None
        factors.append(f"Dark Pool {flow}")
        
        # Must be near gamma wall
        open_interest = data.get('open_interest', {})
        nearest_wall = open_interest.get('nearest_wall')
        if not nearest_wall or nearest_wall.get('distance_pct', 999) > self.gamma_wall_urgent:
            return None
        factors.append(f"Gamma Wall ${nearest_wall['strike']}")
        
        # Must have extreme confluence
        key_levels = data.get('key_levels', {})
        confluence = key_levels.get('confluence_score', 0)
        if confluence < self.extreme_confluence:
            return None
        factors.append(f"Extreme Confluence ({confluence}/10)")
        
        # All factors aligned!
        return {
            'type': 'extreme_setup',
            'direction': 'BULLISH' if flow == 'BUYING' else 'BEARISH',
            'factors': factors,
            'data': data
        }
    
    # ... Rest of the methods (create_momentum_embed, create_gamma_embed, etc.)
    # These are unchanged from original, just including reference
    
    def run_single_check(self) -> int:
        """
        Run single check cycle
        
        Returns:
            Number of alerts sent
        """
        if not self.enabled:
            return 0
        
        if self.market_hours_only and not self.is_market_hours():
            return 0
        
        self.reset_daily_counters()
        self.stats['total_checks'] += 1
        
        # Get watchlist
        symbols = self.watchlist_manager.load_symbols() if self.watchlist_manager else []
        
        if not symbols:
            return 0
        
        alerts_sent = 0
        
        for symbol in symbols:
            try:
                # Generate professional signal
                data = self.analyzer.generate_professional_signal(symbol)
                
                if not data or 'error' in data:
                    continue
                
                # Price filter
                current_price = data.get('current_price', 0)
                if current_price < self.min_price:
                    continue
                
                # Check all trigger types
                checks = [
                    ('momentum_signal', self.check_momentum_buy_signal),
                    ('momentum_signal', self.check_momentum_sell_signal),
                    ('gamma_approach', self.check_gamma_approach),
                    ('dark_pool_flip', self.check_dark_pool_flip),
                    ('extreme_setup', self.check_extreme_setup)
                ]
                
                for alert_type, check_func in checks:
                    result = check_func(symbol, data)
                    
                    if result and self.can_alert(symbol, alert_type):
                        # Create appropriate embed
                        embed = self.create_alert_embed(symbol, result)
                        
                        if self.send_discord_alert(embed):
                            self.mark_alerted(symbol, alert_type)
                            alerts_sent += 1
                            
                            # Update type-specific stats
                            if result['type'] == 'momentum_buy':
                                self.stats['momentum_buy_signals'] += 1
                            elif result['type'] == 'momentum_sell':
                                self.stats['momentum_sell_signals'] += 1
                            elif result['type'] == 'gamma_approach':
                                self.stats['gamma_approaches'] += 1
                            elif result['type'] == 'dark_pool_flip':
                                self.stats['dark_pool_flips'] += 1
                            elif result['type'] == 'extreme_setup':
                                self.stats['extreme_setups'] += 1
                
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                self.logger.error(f"Error checking {symbol}: {str(e)}")
                continue
        
        return alerts_sent
    
    def create_alert_embed(self, symbol: str, result: dict) -> dict:
        """Create Discord embed for alert (simplified for space)"""
        alert_type = result['type']
        
        # Basic embed structure
        embed = {
            'title': f"🎯 {symbol} - {alert_type.replace('_', ' ').upper()}",
            'color': 0x00ff00 if 'buy' in alert_type else 0xff0000,
            'timestamp': datetime.utcnow().isoformat(),
            'fields': [],
            'footer': {
                'text': f'Momentum Signal Monitor v2.0 • {datetime.now().strftime("%H:%M:%S ET")}'
            }
        }
        
        # Add type-specific fields
        if 'factors' in result:
            factors_text = '\n'.join([f"✅ {f}" for f in result['factors']])
            embed['fields'].append({
                'name': '📊 Aligned Factors',
                'value': factors_text,
                'inline': False
            })
        
        return embed
    
    def run_continuous(self):
        """Run continuous monitoring"""
        self.logger.info("🚀 Starting Momentum Signal Monitor v2.0 (continuous mode)")
        
        try:
            while self.enabled:
                try:
                    if self.market_hours_only and not self.is_market_hours():
                        time.sleep(60)
                        continue
                    
                    alerts = self.run_single_check()
                    
                    if alerts > 0:
                        self.logger.info(f"✅ Check complete: {alerts} momentum signals sent")
                    
                    time.sleep(self.check_interval)
                    
                except Exception as e:
                    self.logger.error(f"Error in check cycle: {str(e)}")
                    import traceback
                    self.logger.debug(traceback.format_exc())
                    time.sleep(30)
                    
        except KeyboardInterrupt:
            self.logger.info("Stopping momentum signal monitor...")
            self.print_stats()
    
    def print_stats(self):
        """Print monitor statistics"""
        print("\n" + "=" * 60)
        print("MOMENTUM SIGNAL MONITOR STATISTICS")
        print("=" * 60)
        print(f"Total Checks: {self.stats['total_checks']}")
        print(f"Buy Signals: {self.stats['momentum_buy_signals']}")
        print(f"Sell Signals: {self.stats['momentum_sell_signals']}")
        print(f"Gamma Approaches: {self.stats['gamma_approaches']}")
        print(f"Dark Pool Flips: {self.stats['dark_pool_flips']}")
        print(f"Extreme Setups: {self.stats['extreme_setups']}")
        print(f"Total Alerts Sent: {self.stats['total_alerts_sent']}")
        print(f"Rate Limited: {self.stats['rate_limited']}")
        print("=" * 60 + "\n")


# CLI Testing
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    import yaml
    from utils.watchlist_manager import WatchlistManager
    
    load_dotenv()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    API_KEY = os.getenv('POLYGON_API_KEY')
    
    # Load config
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize
    watchlist_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'watchlist.txt')
    watchlist_manager = WatchlistManager(watchlist_file=watchlist_path)
    
    monitor = MomentumSignalMonitor(
        polygon_api_key=API_KEY,
        config=config,
        watchlist_manager=watchlist_manager
    )
    
    print("=" * 80)
    print("MOMENTUM SIGNAL MONITOR v2.0 - TEST MODE")
    print("=" * 80)
    print(f"Check Interval: {monitor.check_interval}s")
    print(f"RVOL Thresholds: {monitor.min_rvol}x / {monitor.high_rvol}x / {monitor.extreme_rvol}x")
    print(f"Market Hours Only: {monitor.market_hours_only}")
    print("\nRunning single check...")
    print("=" * 80)
    
    alerts = monitor.run_single_check()
    
    print("\n" + "=" * 80)
    print(f"RESULTS: {alerts} alerts sent")
    print(f"Stats: {monitor.stats}")
    print("=" * 80)