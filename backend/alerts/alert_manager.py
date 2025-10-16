"""
backend/alerts/alert_manager.py
Enhanced Alert Manager - PHASE 1 UPDATE
- Better scan intervals (60s first hour, 2min mid-day)
- Signal metrics tracking integration
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
        """Initialize Enhanced Alert Manager - PHASE 1"""
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
        
        # PHASE 1: Enhanced scan intervals
        self.scan_intervals = {
            'PREMARKET': 300,  # 5 minutes
            'FIRST_HOUR': 60,  # 1 minute (9:30-10:30)
            'MIDDAY': 120,     # 2 minutes (10:30-15:00)
            'POWER_HOUR': 60,  # 1 minute (15:00-16:00)
            'AFTERHOURS': 300  # 5 minutes
        }
        
        self.stats = {
            'scans_completed': 0,
            'alerts_sent': 0,
            'symbols_analyzed': 0,
            'errors': 0,
            'news_alerts_sent': 0,
            'signals_tracked': 0  # PHASE 1
        }
        
        self.logger.info("Enhanced Alert Manager (Phase 1) initialized")
    
    def get_current_market_phase(self) -> str:
        """
        PHASE 1: Determine current market phase for dynamic scanning
        Returns: PREMARKET, FIRST_HOUR, MIDDAY, POWER_HOUR, AFTERHOURS
        """
        now = datetime.now()
        et_hour = now.hour
        et_minute = now.minute
        
        current_minutes = et_hour * 60 + et_minute
        
        # Market phases (ET)
        if current_minutes < 4 * 60:  # Before 4 AM
            return 'AFTERHOURS'
        elif current_minutes < 9 * 60 + 30:  # 4 AM - 9:30 AM
            return 'PREMARKET'
        elif current_minutes < 10 * 60 + 30:  # 9:30 AM - 10:30 AM
            return 'FIRST_HOUR'
        elif current_minutes < 15 * 60:  # 10:30 AM - 3:00 PM
            return 'MIDDAY'
        elif current_minutes < 16 * 60:  # 3:00 PM - 4:00 PM
            return 'POWER_HOUR'
        else:  # After 4 PM
            return 'AFTERHOURS'
    
    def get_scan_interval(self) -> int:
        """
        PHASE 1: Get scan interval based on market phase
        """
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
        """
        PHASE 1: Send alert with metrics tracking
        """
        symbol = analysis['symbol']
        alert_type = analysis.get('alert_type', 'MONITOR')
        confidence = analysis.get('confidence', 0)
        
        should_send, reason = self.alert_filter.should_send_alert(analysis)
        
        if not should_send:
            self.logger.debug(f"{symbol}: Not sending alert - {reason}")
            return
        
        # PHASE 1: Enhanced logging with volume and level info
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
        
        # Send to Discord
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
    
    def run_scan(self) -> List[Dict]:
        """Run complete scan"""
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
                self.send_alert(analysis)
            
            # News monitoring
            if self.news_config.get('enabled'):
                try:
                    self.check_news_for_symbol(symbol)
                except Exception as e:
                    self.logger.error(f"News check failed for {symbol}: {str(e)}")
            
            time.sleep(0.5)
        
        self.stats['scans_completed'] += 1
        
        # PHASE 1: Enhanced scan summary
        alerts_sent = sum(1 for r in results if r.get('alert_type') != 'MONITOR')
        high_rvol = sum(1 for r in results 
                       if r.get('volume_analysis', {}).get('rvol', {}).get('classification') in ['HIGH', 'EXTREME'])
        high_confluence = sum(1 for r in results
                             if r.get('key_levels', {}).get('confluence_score', 0) >= 7)
        
        self.logger.info(
            f"Scan complete: {len(results)} analyzed | "
            f"{alerts_sent} alerts | "
            f"{high_rvol} high RVOL | "
            f"{high_confluence} high confluence"
        )
        
        return results
    
    def run_continuous(self):
        """
        PHASE 1: Run continuous scanning with dynamic intervals
        """
        self.logger.info("Starting continuous scanning mode (Phase 1)...")
        self.logger.info(f"Initial phase: {self.get_current_market_phase()}")
        self.logger.info(f"Signal tracking: {'ENABLED' if self.metrics_tracker else 'DISABLED'}")
        
        try:
            while True:
                if not self.scheduler.should_scan_now():
                    self.logger.debug("Market closed, sleeping...")
                    time.sleep(60)
                    continue
                
                try:
                    # PHASE 1: Log current phase
                    phase = self.get_current_market_phase()
                    interval = self.get_scan_interval()
                    
                    scan_start = time.time()
                    results = self.run_scan()
                    scan_duration = time.time() - scan_start
                    
                    # PHASE 1: Enhanced scan summary
                    alerts_sent = sum(1 for r in results if r.get('alert_type') != 'MONITOR')
                    
                    self.logger.info(
                        f"Scan summary ({scan_duration:.1f}s): "
                        f"{len(results)} analyzed, {alerts_sent} alerts"
                    )
                
                except Exception as e:
                    self.logger.error(f"Scan failed: {str(e)}")
                    import traceback
                    self.logger.debug(traceback.format_exc())
                    self.stats['errors'] += 1
                
                # PHASE 1: Dynamic interval based on phase
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
            
            # PHASE 1: Show metrics summary
            if self.metrics_tracker:
                print("\n" + self.metrics_tracker.generate_report(days=1))
    
    def check_news_for_symbol(self, symbol: str) -> bool:
        """Check news for a single symbol"""
        # Reset daily counters
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
        print(f"News Alerts Sent: {self.stats['news_alerts_sent']}")
        print(f"Signals Tracked: {self.stats['signals_tracked']}")
        print(f"Errors: {self.stats['errors']}")
        print("=" * 60 + "\n")


# CLI
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
        
        elif command == 'run':
            print("Starting continuous mode (Phase 1)...")
            print("Press Ctrl+C to stop")
            manager.run_continuous()
        
        elif command == 'stats':
            manager.print_stats()
        
        elif command == 'metrics':
            # PHASE 1: Show signal metrics
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