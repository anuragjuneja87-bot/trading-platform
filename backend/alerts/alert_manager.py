"""
backend/alerts/alert_manager.py
Enhanced Alert Manager - PHASE 1 UPDATE + VOLUME SPIKE ALERTS
- Better scan intervals (60s first hour, 2min mid-day)
- Signal metrics tracking integration
- Volume spike detection and alerting (NEW)
- Enhanced status logging
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import logging
import time
import yaml
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

from scheduler.market_scheduler import MarketScheduler
from analyzers.enhanced_professional_analyzer import EnhancedProfessionalAnalyzer
from alerts.discord_alerter import DiscordAlerter
from alerts.alert_filter import AlertFilter

# PHASE 1: Signal metrics tracking
try:
    from utils.signal_metrics import SignalMetricsTracker
    SIGNAL_METRICS_AVAILABLE = True
except ImportError:
    SIGNAL_METRICS_AVAILABLE = False
    logging.warning("Signal metrics tracking not available")


class AlertManager:
    def __init__(self, config_path: str = None, polygon_api_key: str = None):
        """Initialize Enhanced Alert Manager - PHASE 1 + Volume Spikes"""
        self.logger = logging.getLogger(__name__)
        
        if config_path is None:
            config_path = backend_dir / 'config' / 'config.yaml'
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.api_key = polygon_api_key or self.config.get('polygon_api_key')
        if not self.api_key:
            raise ValueError("Polygon API key not provided")
        
        self.scheduler = MarketScheduler(str(config_path))
        self.analyzer = EnhancedProfessionalAnalyzer(polygon_api_key=self.api_key)
        
        discord_config = self.config.get('discord', {})
        self.alert_filter = AlertFilter(discord_config)
        
        self.discord = None
        if self.config.get('discord', {}).get('enabled'):
            self.discord = DiscordAlerter(config=self.config['discord'])
            self.logger.info("Discord alerter enabled")
        
        # PHASE 1: Signal metrics tracker
        self.metrics_tracker = None
        if SIGNAL_METRICS_AVAILABLE:
            try:
                self.metrics_tracker = SignalMetricsTracker()
                self.logger.info("✅ Signal metrics tracking enabled")
            except Exception as e:
                self.logger.warning(f"⚠️ Signal metrics tracker failed: {str(e)}")
        
        self.news_config = self.config.get('news_monitoring', {
            'enabled': True,
            'max_alerts_per_symbol_per_day': 10,
            'check_interval_seconds': 180,
            'min_impact_level': 'MEDIUM'
        })
        
        self.news_alert_counts = defaultdict(int)
        self.seen_news_hashes = set()
        self.last_news_check = {}
        self.last_news_reset = datetime.now().date()
        
        # NEW: Volume spike cooldown tracking
        self._volume_spike_cooldowns = {}
        self.volume_spike_config = {
            'cooldown_minutes': 10,
            'min_classification': 'ELEVATED'
        }
        
        # PHASE 1: Enhanced scan intervals
        self.scan_intervals = {
            'PREMARKET': 300,
            'FIRST_HOUR': 60,
            'MIDDAY': 120,
            'POWER_HOUR': 60,
            'AFTERHOURS': 300
        }
        
        self.stats = {
            'scans_completed': 0,
            'alerts_sent': 0,
            'symbols_analyzed': 0,
            'errors': 0,
            'news_alerts_sent': 0,
            'signals_tracked': 0,
            'volume_spike_alerts': 0,
            'unusual_activity_alerts': 0
        }
        
        self.logger.info("Enhanced Alert Manager (Phase 1 + Volume Spikes) initialized")
        self.logger.info(f"  📊 Volume spike alerts: ENABLED (cooldown: {self.volume_spike_config['cooldown_minutes']}min)")
    
    def get_current_market_phase(self) -> str:
        """
        PHASE 1: Determine current market phase for dynamic scanning
        Returns: PREMARKET, FIRST_HOUR, MIDDAY, POWER_HOUR, AFTERHOURS
        """
        now = datetime.now()
        et_hour = now.hour
        et_minute = now.minute
        
        current_minutes = et_hour * 60 + et_minute
        
        if current_minutes < 4 * 60:
            return 'AFTERHOURS'
        elif current_minutes < 9 * 60 + 30:
            return 'PREMARKET'
        elif current_minutes < 10 * 60 + 30:
            return 'FIRST_HOUR'
        elif current_minutes < 15 * 60:
            return 'MIDDAY'
        elif current_minutes < 16 * 60:
            return 'POWER_HOUR'
        else:
            return 'AFTERHOURS'
    
    def get_scan_interval(self) -> int:
        """PHASE 1: Get scan interval based on market phase"""
        phase = self.get_current_market_phase()
        return self.scan_intervals.get(phase, 300)
    
    def analyze_symbol(self, symbol: str) -> Optional[Dict]:
        """Analyze a single symbol"""
        try:
            self.logger.debug(f"Analyzing {symbol}...")
            analysis = self.analyzer.generate_professional_signal(symbol)
            self.stats['symbols_analyzed'] += 1
            return analysis
        except Exception as e:
            self.logger.error(f"Error analyzing {symbol}: {str(e)}")
            self.stats['errors'] += 1
            return None
    
    def send_alert(self, analysis: Dict):
        """PHASE 1: Send trading signal alert with metrics tracking"""
        symbol = analysis['symbol']
        alert_type = analysis.get('alert_type', 'MONITOR')
        confidence = analysis.get('confidence', 0)
        
        should_send, reason = self.alert_filter.should_send_alert(analysis)
        
        if not should_send:
            self.logger.debug(f"{symbol}: Not sending alert - {reason}")
            return
        
        log_parts = [f"📢 {symbol} - {alert_type} ({confidence:.1f}%)"]
        
        volume_analysis = analysis.get('volume_analysis', {})
        if volume_analysis:
            rvol = volume_analysis.get('rvol', {})
            if rvol.get('rvol', 0) >= 2.0:
                log_parts.append(f"RVOL {rvol['rvol']}x")
        
        key_levels = analysis.get('key_levels', {})
        if key_levels and 'error' not in key_levels:
            confluence = key_levels.get('confluence_score', 0)
            if confluence >= 6:
                log_parts.append(f"Confluence {confluence}/10")
        
        self.logger.info(" | ".join(log_parts))
        
        if self.discord:
            try:
                success = self.discord.send_trading_signal(analysis)
                if success:
                    self.logger.info(f"✅ Alert sent to Discord for {symbol}")
            except Exception as e:
                self.logger.error(f"❌ Discord alert failed: {str(e)}")
                self.stats['errors'] += 1
        
        self.alert_filter.record_alert(analysis)
        self.stats['alerts_sent'] += 1
        
        # PHASE 1: Track signal metrics
        if self.metrics_tracker and alert_type != 'MONITOR':
            try:
                signal_id = self.metrics_tracker.record_signal(analysis)
                if signal_id:
                    self.stats['signals_tracked'] += 1
                    self.logger.debug(f"📊 Tracked signal: {signal_id}")
            except Exception as e:
                self.logger.error(f"Error tracking signal: {str(e)}")
    
    def check_and_send_volume_spike_alert(self, analysis: Dict):
        """
        NEW: Check for volume spikes and send dedicated alerts
        Separate from trading signals - alerts on pure volume action
        """
        symbol = analysis['symbol']
        volume_analysis = analysis.get('volume_analysis', {})
        
        if not volume_analysis or 'error' in volume_analysis:
            return
        
        spike_data = volume_analysis.get('volume_spike', {})
        
        if not spike_data.get('spike_detected'):
            return
        
        classification = spike_data.get('classification', 'UNKNOWN')
        spike_ratio = spike_data.get('spike_ratio', 0)
        alert_urgency = spike_data.get('alert_urgency', 'NONE')
        
        # Check if classification meets minimum threshold
        min_classification = self.volume_spike_config['min_classification']
        allowed_classifications = ['ELEVATED', 'HIGH', 'EXTREME']
        
        if min_classification == 'HIGH':
            allowed_classifications = ['HIGH', 'EXTREME']
        elif min_classification == 'EXTREME':
            allowed_classifications = ['EXTREME']
        
        if classification not in allowed_classifications:
            self.logger.debug(
                f"{symbol}: Volume spike {spike_ratio:.2f}x ({classification}) "
                f"below threshold ({min_classification})"
            )
            return
        
        # Check cooldown
        cooldown_key = f"volume_spike_{symbol}"
        cooldown_minutes = self.volume_spike_config['cooldown_minutes']
        
        last_alert = self._volume_spike_cooldowns.get(cooldown_key)
        if last_alert:
            elapsed_minutes = (datetime.now() - last_alert).total_seconds() / 60
            if elapsed_minutes < cooldown_minutes:
                self.logger.debug(
                    f"{symbol}: Volume spike cooldown active "
                    f"({elapsed_minutes:.0f}min ago, need {cooldown_minutes}min)"
                )
                return
        
        # Send alert
        if self.discord:
            try:
                phase = self.get_current_market_phase()
                if phase == 'PREMARKET':
                    session = 'PREMARKET'
                elif phase == 'AFTERHOURS':
                    session = 'AFTERHOURS'
                else:
                    session = 'REGULAR'
                
                success = self.discord.send_volume_spike_alert(
                    symbol=symbol,
                    volume_data=spike_data,
                    session=session
                )
                
                if success:
                    self.logger.info(
                        f"🔥 Volume spike alert sent: {symbol} "
                        f"({spike_ratio:.2f}x - {classification} - {alert_urgency})"
                    )
                    self._volume_spike_cooldowns[cooldown_key] = datetime.now()
                    self.stats['volume_spike_alerts'] += 1
                    
            except Exception as e:
                self.logger.error(f"Volume spike alert failed for {symbol}: {str(e)}")
                self.stats['errors'] += 1
        else:
            self.logger.warning(f"Discord not configured - cannot send volume spike alert for {symbol}")

    def check_and_send_unusual_activity_alerts(self, analysis: Dict):
        """
        NEW: Check for unusual options activity and send alerts
        Day trader optimized - 5-minute cooldown for frequent updates
        
        Args:
            analysis: Analysis dict containing unusual_activity data
        """
        symbol = analysis['symbol']
        unusual_activity = analysis.get('unusual_activity', {})
        
        if not unusual_activity.get('detected'):
            return
        
        alerts = unusual_activity.get('alerts', [])
        
        for alert in alerts:
            # Send to Discord via unusual activity method
            if self.discord:
                try:
                    success = self.discord.send_unusual_activity_alert(symbol, alert)
                    if success:
                        self.stats['unusual_activity_alerts'] = self.stats.get('unusual_activity_alerts', 0) + 1
                        self.logger.info(
                            f"✅ Unusual activity alert sent: {symbol} "
                            f"${alert['strike']}{alert['option_type'][0].upper()} "
                            f"Score: {alert['score']:.1f}/10"
                        )
                except Exception as e:
                    self.logger.error(f"Error sending unusual activity alert: {str(e)}")

    def run_scan(self) -> List[Dict]:
        """Run complete scan with volume spike detection"""
        symbols = self.scheduler.get_watchlist_for_state(
            self.scheduler.get_current_market_state()
        )
        
        market_state = self.scheduler.get_current_market_state()
        phase = self.get_current_market_phase()
        
        self.logger.info(
            f"Starting scan: {market_state} ({phase}) | {len(symbols)} symbols"
        )
        
        results = []
        
        for symbol in symbols:
            analysis = self.analyze_symbol(symbol)
            
            if analysis:
                results.append(analysis)
                
                # Send trading signal alert
                self.send_alert(analysis)
                
                # NEW: Check for volume spike alerts
                self.check_and_send_volume_spike_alert(analysis)
                
                 # NEW: Check for unusual options activity (day trader mode)
                self.check_and_send_unusual_activity_alerts(analysis)
            
            # Check news if enabled
            if self.news_config.get('enabled'):
                try:
                    self.check_news_for_symbol(symbol)
                except Exception as e:
                    self.logger.error(f"News check failed for {symbol}: {str(e)}")
            
            time.sleep(0.5)
        
        self.stats['scans_completed'] += 1
        
        # Enhanced scan summary
        alerts_sent = sum(1 for r in results if r.get('alert_type') != 'MONITOR')
        high_rvol = sum(1 for r in results 
                       if r.get('volume_analysis', {}).get('rvol', {}).get('classification') in ['HIGH', 'EXTREME'])
        high_confluence = sum(1 for r in results
                             if r.get('key_levels', {}).get('confluence_score', 0) >= 7)
        volume_spikes = sum(1 for r in results
                           if r.get('volume_analysis', {}).get('volume_spike', {}).get('spike_detected'))
        
        self.logger.info(
            f"Scan complete: {len(results)} analyzed | "
            f"{alerts_sent} signals | "
            f"{volume_spikes} volume spikes | "
            f"{high_rvol} high RVOL | "
            f"{high_confluence} high confluence"
        )
        
        return results
    
    def run_continuous(self):
        """PHASE 1: Run continuous scanning with dynamic intervals + volume spike detection"""
        self.logger.info("Starting continuous scanning mode (Phase 1 + Volume Spikes)...")
        self.logger.info(f"Initial phase: {self.get_current_market_phase()}")
        self.logger.info(f"Signal tracking: {'ENABLED' if self.metrics_tracker else 'DISABLED'}")
        self.logger.info(f"Volume spike alerts: ENABLED (cooldown: {self.volume_spike_config['cooldown_minutes']}min)")
        
        try:
            while True:
                if not self.scheduler.should_scan_now():
                    self.logger.debug("Market closed, sleeping...")
                    time.sleep(60)
                    continue
                
                try:
                    phase = self.get_current_market_phase()
                    interval = self.get_scan_interval()
                    
                    scan_start = time.time()
                    results = self.run_scan()
                    scan_duration = time.time() - scan_start
                    
                    alerts_sent = sum(1 for r in results if r.get('alert_type') != 'MONITOR')
                    
                    self.logger.info(
                        f"Scan summary ({scan_duration:.1f}s): "
                        f"{len(results)} analyzed, {alerts_sent} signals, "
                        f"{self.stats.get('volume_spike_alerts', 0)} total volume spikes"
                    )
                
                except Exception as e:
                    self.logger.error(f"Scan failed: {str(e)}")
                    import traceback
                    self.logger.debug(traceback.format_exc())
                    self.stats['errors'] += 1
                
                interval = self.get_scan_interval()
                next_scan = datetime.now() + timedelta(seconds=interval)
                
                self.logger.info(
                    f"Next scan in {interval}s ({self.get_current_market_phase()}) "
                    f"at {next_scan.strftime('%H:%M:%S')}"
                )
                time.sleep(interval)
        
        except KeyboardInterrupt:
            self.logger.info("Stopping continuous mode...")
            self.print_stats()
            
            if self.metrics_tracker:
                print("\n" + self.metrics_tracker.generate_report(days=1))
    
    def check_news_for_symbol(self, symbol: str) -> bool:
        """Check news for a single symbol"""
        current_date = datetime.now().date()
        if current_date != self.last_news_reset:
            self.news_alert_counts.clear()
            self.seen_news_hashes.clear()
            self.last_news_reset = current_date
        
        if self.news_alert_counts[symbol] >= self.news_config['max_alerts_per_symbol_per_day']:
            return False
        
        last_check = self.last_news_check.get(symbol, datetime.min)
        if (datetime.now() - last_check).seconds < self.news_config['check_interval_seconds']:
            return False
        
        try:
            news_data = self.analyzer.get_enhanced_news_sentiment(symbol)
            self.last_news_check[symbol] = datetime.now()
            
            news_impact = news_data.get('news_impact', 'NONE')
            min_impact = self.news_config['min_impact_level']
            
            impact_levels = ['NONE', 'LOW', 'MEDIUM', 'HIGH', 'EXTREME']
            
            try:
                current_impact_idx = impact_levels.index(news_impact)
                min_impact_idx = impact_levels.index(min_impact)
            except ValueError:
                return False
            
            if current_impact_idx < min_impact_idx:
                return False
            
            headlines = news_data.get('headlines', [])
            if headlines:
                news_hash = self._create_news_hash(symbol, headlines[0])
                if news_hash in self.seen_news_hashes:
                    return False
                self.seen_news_hashes.add(news_hash)
            
            if self.discord:
                success = self.discord.send_news_alert(symbol, news_data)
                if success:
                    self.news_alert_counts[symbol] += 1
                    self.stats['news_alerts_sent'] += 1
                    return True
        
        except Exception as e:
            self.logger.error(f"Error checking news for {symbol}: {str(e)}")
        
        return False
    
    def _create_news_hash(self, symbol: str, headline: str) -> str:
        """Create unique hash for news article"""
        hash_str = f"{symbol}_{headline[:50]}_{datetime.now().strftime('%Y%m%d%H')}"
        return hashlib.md5(hash_str.encode()).hexdigest()
    
    def print_stats(self):
        """PHASE 1: Print enhanced statistics"""
        print("\n" + "=" * 60)
        print("PHASE 1 ENHANCED ALERT MANAGER STATISTICS")
        print("=" * 60)
        print(f"Scans Completed: {self.stats['scans_completed']}")
        print(f"Symbols Analyzed: {self.stats['symbols_analyzed']}")
        print(f"Trading Alerts Sent: {self.stats['alerts_sent']}")
        print(f"Volume Spike Alerts: {self.stats.get('volume_spike_alerts', 0)}")
        print(f"News Alerts Sent: {self.stats['news_alerts_sent']}")
        print(f"Signals Tracked: {self.stats['signals_tracked']}")
        print(f"Errors: {self.stats['errors']}")
        print("=" * 60)
        
        if self._volume_spike_cooldowns:
            print("\n📊 Active Volume Spike Cooldowns:")
            now = datetime.now()
            for key, last_alert in self._volume_spike_cooldowns.items():
                symbol = key.replace('volume_spike_', '')
                elapsed = (now - last_alert).total_seconds() / 60
                remaining = self.volume_spike_config['cooldown_minutes'] - elapsed
                if remaining > 0:
                    print(f"  • {symbol}: {remaining:.0f} minutes remaining")
        
        print()


def main():
    """Command-line interface"""
    import sys
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        print("❌ Error: POLYGON_API_KEY not found in environment")
        sys.exit(1)
    
    try:
        manager = AlertManager(polygon_api_key=api_key)
    except Exception as e:
        print(f"❌ Error initializing AlertManager: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'scan':
            print("Running single scan...")
            results = manager.run_scan()
            print(f"\n✅ Scan complete: {len(results)} symbols analyzed")
            manager.print_stats()
        
        elif command == 'run':
            print("Starting continuous mode (Phase 1 + Volume Spikes)...")
            print("Press Ctrl+C to stop")
            manager.run_continuous()
        
        elif command == 'stats':
            manager.print_stats()
        
        elif command == 'metrics':
            if manager.metrics_tracker:
                days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
                print(manager.metrics_tracker.generate_report(days=days))
            else:
                print("❌ Signal metrics not available")
        
        else:
            print(f"Unknown command: {command}")
    
    else:
        print("Running single scan...")
        results = manager.run_scan()
        manager.print_stats()


if __name__ == '__main__':
    main()