"""
backend/monitors/relative_strength_monitor.py
Relative Strength Monitor - Catches divergence plays

Monitors symbol performance vs SPY/QQQ
Alerts when stocks significantly outperform/underperform benchmarks
AGGRESSIVE thresholds for 7-figure day trading

Pre-Market Mode: 7:00-9:25 AM (±1.0% threshold)
Market Mode: 9:30-4:00 PM (±1.5% threshold)
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import logging
import time
from datetime import datetime
from typing import Dict, List
import pytz
import requests


class RelativeStrengthMonitor:
    def __init__(self, analyzer, config: dict):
        """
        Initialize Relative Strength Monitor
        
        Args:
            analyzer: EnhancedProfessionalAnalyzer instance
            config: Configuration dict from config.yaml
        """
        self.logger = logging.getLogger(__name__)
        self.analyzer = analyzer
        
        # Load config
        rs_config = config.get('relative_strength_monitor', {})
        self.enabled = rs_config.get('enabled', True)
        self.check_interval = rs_config.get('check_interval', 30)
        self.market_hours_only = rs_config.get('market_hours_only', False)
        
        # Benchmarks
        self.benchmarks = rs_config.get('benchmarks', ['SPY', 'QQQ'])
        
        # Thresholds
        thresholds = rs_config.get('thresholds', {})
        self.premarket_thresholds = thresholds.get('premarket', {
            'strong_divergence_pct': 1.0,
            'extreme_divergence_pct': 2.5
        })
        self.market_thresholds = thresholds.get('market_hours', {
            'strong_divergence_pct': 1.5,
            'extreme_divergence_pct': 3.0
        })
        
        # Filters
        filters = rs_config.get('filters', {})
        self.watchlist_only = filters.get('watchlist_only', True)
        self.min_price = filters.get('min_price', 5.0)
        self.max_alerts_per_day = filters.get('max_alerts_per_symbol_per_day', 20)
        self.exclude_benchmarks = filters.get('exclude_benchmarks', True)
        
        # Cooldowns
        cooldowns = rs_config.get('cooldown_minutes', {})
        self.cooldown_premarket = cooldowns.get('premarket', 3) * 60  # Convert to seconds
        self.cooldown_market = cooldowns.get('market_hours', 2) * 60
        
        # Schedule
        schedule = rs_config.get('schedule', {})
        self.premarket_start = schedule.get('premarket_start', '07:00')
        self.premarket_end = schedule.get('premarket_end', '09:25')
        
        # Discord webhook
        discord_config = config.get('discord', {})
        self.discord_webhook = discord_config.get('webhook_momentum_signals') or discord_config.get('webhook_url')
        
        # Tracking
        self.last_alert_time = {}  # {(symbol, benchmark): timestamp}
        self.daily_alert_count = {}  # {symbol: count}
        self.last_reset_date = datetime.now().date()
        
        # Stats
        self.stats = {
            'checks_performed': 0,
            'alerts_sent': 0,
            'strong_divergences': 0,
            'extreme_divergences': 0,
            'errors': 0
        }
        
        self.logger.info("✅ Relative Strength Monitor initialized")
        self.logger.info(f"   📊 Benchmarks: {', '.join(self.benchmarks)}")
        self.logger.info(f"   ⏱️ Check interval: {self.check_interval}s")
        self.logger.info(f"   🎯 Pre-market threshold: ±{self.premarket_thresholds['strong_divergence_pct']}%")
        self.logger.info(f"   🎯 Market threshold: ±{self.market_thresholds['strong_divergence_pct']}%")
    
    def get_market_session(self) -> str:
        """
        Determine current market session
        
        Returns:
            'PRE_MARKET', 'MARKET_HOURS', 'AFTER_HOURS', or 'CLOSED'
        """
        et_tz = pytz.timezone('America/New_York')
        now = datetime.now(et_tz)
        
        # Check weekday
        if now.weekday() >= 5:  # Weekend
            return 'CLOSED'
        
        # Parse time
        current_time = now.strftime('%H:%M')
        
        # Pre-market: 7:00-9:25 AM
        if self.premarket_start <= current_time < self.premarket_end:
            return 'PRE_MARKET'
        
        # Market hours: 9:30 AM - 4:00 PM
        if '09:30' <= current_time < '16:00':
            return 'MARKET_HOURS'
        
        # After hours: 4:00-8:00 PM
        if '16:00' <= current_time < '20:00':
            return 'AFTER_HOURS'
        
        return 'CLOSED'
    
    def reset_daily_counts(self):
        """Reset daily alert counts at midnight"""
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.daily_alert_count = {}
            self.last_reset_date = today
            self.logger.info("🔄 Daily alert counts reset")
    
    def check_cooldown(self, symbol: str, benchmark: str) -> bool:
        """
        Check if alert is in cooldown period
        
        Returns:
            True if can send alert, False if in cooldown
        """
        key = (symbol, benchmark)
        
        if key not in self.last_alert_time:
            return True
        
        last_alert = self.last_alert_time[key]
        session = self.get_market_session()
        
        # Choose cooldown based on session
        if session == 'PRE_MARKET':
            cooldown_seconds = self.cooldown_premarket
        else:
            cooldown_seconds = self.cooldown_market
        
        elapsed = (datetime.now() - last_alert).total_seconds()
        
        return elapsed >= cooldown_seconds
    
    def check_daily_limit(self, symbol: str) -> bool:
        """Check if symbol has hit daily alert limit"""
        self.reset_daily_counts()
        
        count = self.daily_alert_count.get(symbol, 0)
        return count < self.max_alerts_per_day
    
    def analyze_relative_strength(self, symbol: str, watchlist: List[str]) -> List[Dict]:
        """
        Analyze relative strength for a symbol against all benchmarks
        
        Returns:
            List of alert dicts if divergence detected
        """
        try:
            # Skip if symbol is a benchmark itself (and exclude_benchmarks=True)
            if self.exclude_benchmarks and symbol in self.benchmarks:
                return []
            
            # Get session
            session = self.get_market_session()
            
            # Skip if market closed and market_hours_only=True
            if self.market_hours_only and session == 'CLOSED':
                return []
            
            # Get current price
            quote = self.analyzer.get_real_time_quote(symbol)
            current_price = quote['price']
            
            if current_price == 0 or current_price < self.min_price:
                return []
            
            alerts = []
            
            # Check against each benchmark
            for benchmark in self.benchmarks:
                # Calculate RS
                rs = self.analyzer.calculate_relative_strength(symbol, current_price, benchmark)
                
                if rs == 0:
                    continue
                
                # Get thresholds based on session
                if session == 'PRE_MARKET':
                    strong_threshold = self.premarket_thresholds['strong_divergence_pct']
                    extreme_threshold = self.premarket_thresholds['extreme_divergence_pct']
                else:
                    strong_threshold = self.market_thresholds['strong_divergence_pct']
                    extreme_threshold = self.market_thresholds['extreme_divergence_pct']
                
                # Determine alert type
                alert_type = None
                urgency = None
                
                if abs(rs) >= extreme_threshold:
                    alert_type = 'EXTREME_DIVERGENCE'
                    urgency = 'EXTREME'
                elif abs(rs) >= strong_threshold:
                    alert_type = 'STRONG_DIVERGENCE'
                    urgency = 'HIGH'
                
                if alert_type:
                    # Check cooldown
                    if not self.check_cooldown(symbol, benchmark):
                        self.logger.debug(f"RS alert in cooldown: {symbol} vs {benchmark}")
                        continue
                    
                    # Check daily limit
                    if not self.check_daily_limit(symbol):
                        self.logger.debug(f"RS alert daily limit reached: {symbol}")
                        continue
                    
                    # Create alert
                    alerts.append({
                        'symbol': symbol,
                        'benchmark': benchmark,
                        'rs': rs,
                        'current_price': current_price,
                        'alert_type': alert_type,
                        'urgency': urgency,
                        'session': session,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    # Update tracking
                    self.last_alert_time[(symbol, benchmark)] = datetime.now()
                    self.daily_alert_count[symbol] = self.daily_alert_count.get(symbol, 0) + 1
                    
                    # Update stats
                    if urgency == 'EXTREME':
                        self.stats['extreme_divergences'] += 1
                    else:
                        self.stats['strong_divergences'] += 1
            
            return alerts
            
        except Exception as e:
            self.logger.error(f"Error analyzing RS for {symbol}: {str(e)}")
            self.stats['errors'] += 1
            return []
    
    def send_discord_alert(self, alert: Dict) -> bool:
        """
        Send relative strength alert to Discord
        
        Args:
            alert: Alert dict from analyze_relative_strength
        
        Returns:
            True if sent successfully
        """
        if not self.discord_webhook:
            self.logger.warning("Discord webhook not configured")
            return False
        
        try:
            symbol = alert['symbol']
            benchmark = alert['benchmark']
            rs = alert['rs']
            current_price = alert['current_price']
            urgency = alert['urgency']
            session = alert['session']
            
            # Determine direction and color
            if rs > 0:
                direction = 'OUTPERFORMING'
                color = 0x00ff00  # Green
                emoji = '🟢'
                arrow = '⬆️'
            else:
                direction = 'UNDERPERFORMING'
                color = 0xff0000  # Red
                emoji = '🔴'
                arrow = '⬇️'
            
            # Extreme = brighter color
            if urgency == 'EXTREME':
                emoji = f'{emoji}{emoji}'
                color = 0x00ff00 if rs > 0 else 0xff0000
            
            # Title
            title = f"{emoji} {direction} - {symbol} vs {benchmark} {arrow}"
            
            # Description
            sign = '+' if rs > 0 else ''
            description = f"**{sign}{rs:.1f}%** relative strength detected"
            
            # Session indicator
            if session == 'PRE_MARKET':
                description += f"\n\n📅 **PRE-MARKET** ({self.premarket_start}-{self.premarket_end} ET)"
            
            embed = {
                'title': title,
                'description': description,
                'color': color,
                'timestamp': datetime.utcnow().isoformat(),
                'fields': []
            }
            
            # Price field
            embed['fields'].append({
                'name': '💰 Current Price',
                'value': f"**${current_price:.2f}**",
                'inline': True
            })
            
            # RS field
            embed['fields'].append({
                'name': '📊 Relative Strength',
                'value': f"**{sign}{rs:.1f}%**",
                'inline': True
            })
            
            # Urgency field
            urgency_display = '🔥🔥🔥 EXTREME' if urgency == 'EXTREME' else '🔥 HIGH'
            embed['fields'].append({
                'name': '⚡ Urgency',
                'value': f"**{urgency_display}**",
                'inline': True
            })
            
            # Trading interpretation
            if rs > 0:
                if session == 'PRE_MARKET':
                    interpretation = (
                        f"✅ **{symbol} showing pre-market strength**\n"
                        f"→ Watch for continuation at open\n"
                        f"→ Consider long bias if holds at 9:30\n"
                        f"→ Strong relative leader"
                    )
                else:
                    interpretation = (
                        f"✅ **{symbol} leading the market**\n"
                        f"→ Momentum play if breaks resistance\n"
                        f"→ Outperforming {benchmark} significantly\n"
                        f"→ Consider adding to longs"
                    )
            else:
                if session == 'PRE_MARKET':
                    interpretation = (
                        f"⚠️ **{symbol} showing pre-market weakness**\n"
                        f"→ Watch for gap fill at open\n"
                        f"→ Consider short bias if breaks support\n"
                        f"→ Relative underperformer"
                    )
                else:
                    interpretation = (
                        f"⚠️ **{symbol} lagging the market**\n"
                        f"→ Short setup if breaks support\n"
                        f"→ Underperforming {benchmark} significantly\n"
                        f"→ Consider fade or short"
                    )
            
            embed['fields'].append({
                'name': '🎯 Trading Action',
                'value': interpretation,
                'inline': False
            })
            
            # Footer
            embed['footer'] = {
                'text': f'Relative Strength Monitor • {datetime.now().strftime("%H:%M:%S ET")}'
            }
            
            # Send to Discord
            payload = {'embeds': [embed]}
            response = requests.post(self.discord_webhook, json=payload, timeout=10)
            response.raise_for_status()
            
            self.logger.info(f"✅ RS alert sent: {symbol} vs {benchmark} ({sign}{rs:.1f}%)")
            self.stats['alerts_sent'] += 1
            
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
            self.logger.debug("Relative strength monitor disabled")
            return 0
        
        # Check session
        session = self.get_market_session()
        
        if self.market_hours_only and session not in ['PRE_MARKET', 'MARKET_HOURS']:
            self.logger.debug(f"Outside active hours, skipping check (session: {session})")
            return 0
        
        self.logger.info(f"🔍 RS Check: {len(watchlist)} symbols at {datetime.now().strftime('%H:%M:%S')} ({session})")
        
        self.stats['checks_performed'] += 1
        alerts_sent = 0
        
        for symbol in watchlist:
            try:
                # Analyze RS for this symbol
                alerts = self.analyze_relative_strength(symbol, watchlist)
                
                # Send Discord alerts
                for alert in alerts:
                    success = self.send_discord_alert(alert)
                    if success:
                        alerts_sent += 1
                
                # Small delay between symbols
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Error checking {symbol}: {str(e)}")
                self.stats['errors'] += 1
                continue
        
        if alerts_sent > 0:
            self.logger.info(f"✅ RS check complete: {alerts_sent} alerts sent")
        else:
            self.logger.info(f"✅ RS check complete: No significant divergences detected")
        
        return alerts_sent
    
    def run_continuous(self, watchlist_manager):
        """
        Run continuous monitoring
        
        Args:
            watchlist_manager: WatchlistManager instance
        """
        self.logger.info("🚀 Starting Relative Strength Monitor (continuous mode)")
        self.logger.info(f"   ⏱️ Check interval: {self.check_interval} seconds")
        self.logger.info(f"   🕐 Pre-market: {self.premarket_start}-{self.premarket_end} ET")
        self.logger.info(f"   📊 Market hours: 09:30-16:00 ET")
        
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
            self.logger.info("Stopping relative strength monitor...")
            self.print_stats()
    
    def print_stats(self):
        """Print monitor statistics"""
        print("\n" + "=" * 60)
        print("RELATIVE STRENGTH MONITOR STATISTICS")
        print("=" * 60)
        print(f"Checks Performed: {self.stats['checks_performed']}")
        print(f"Alerts Sent: {self.stats['alerts_sent']}")
        print(f"  Strong Divergences: {self.stats['strong_divergences']}")
        print(f"  Extreme Divergences: {self.stats['extreme_divergences']}")
        print(f"Errors: {self.stats['errors']}")
        print("=" * 60 + "\n")
