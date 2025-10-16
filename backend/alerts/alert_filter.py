"""
Alert Filter - Rate limiting and filtering logic
Fixed for your directory structure
"""

import sys
from pathlib import Path

# ========================================
# PATH SETUP - Add backend to Python path
# ========================================
backend_dir = Path(__file__).parent.parent  # Gets to backend/
sys.path.insert(0, str(backend_dir))

import time
import logging
from typing import Dict, Optional
from collections import defaultdict


class AlertFilter:
    """
    Filters and rate-limits alerts to prevent spam
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize alert filter
        
        Args:
            config: Optional configuration dict
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Get thresholds from config
        thresholds = self.config.get('thresholds', {})
        self.min_confidence = thresholds.get('minimum_confidence', 60)
        self.strong_signal_confidence = thresholds.get('strong_signal_confidence', 85)
        self.regular_signal_confidence = thresholds.get('regular_signal_confidence', 70)
        
        # Get rate limits from config
        rate_limits = self.config.get('rate_limits', {})
        self.max_alerts_per_hour = rate_limits.get('max_alerts_per_symbol_per_hour', 3)
        self.cooldown_seconds = rate_limits.get('cooldown_between_same_alerts', 300)
        
        # Tracking
        self.alert_history = defaultdict(list)  # symbol -> list of timestamps
        self.last_alert_time = {}  # "symbol:alert_type" -> timestamp
        
        self.logger.info("Alert filter initialized")
    
    def should_send_alert(self, analysis: Dict) -> tuple[bool, str]:
        """
        Determine if an alert should be sent
        
        Args:
            analysis: Analysis result dict
        
        Returns:
            Tuple of (should_send, reason)
        """
        symbol = analysis['symbol']
        alert_type = analysis.get('alert_type', 'MONITOR')
        confidence = analysis.get('confidence', 0)
        
        # Skip MONITOR alerts
        if alert_type == 'MONITOR':
            return False, "Alert type is MONITOR"
        
        # Check minimum confidence
        if confidence < self.min_confidence:
            return False, f"Confidence {confidence:.1f}% below minimum {self.min_confidence}%"
        
        # Check STRONG signal threshold
        if 'STRONG' in alert_type:
            if confidence < self.strong_signal_confidence:
                return False, f"STRONG signal needs {self.strong_signal_confidence}%, got {confidence:.1f}%"
        
        # Check regular signal threshold
        elif alert_type in ['BUY', 'SELL']:
            if confidence < self.regular_signal_confidence:
                return False, f"Regular signal needs {self.regular_signal_confidence}%, got {confidence:.1f}%"
        
        # Check cooldown for same alert type
        alert_key = f"{symbol}:{alert_type}"
        last_time = self.last_alert_time.get(alert_key, 0)
        current_time = time.time()
        
        if current_time - last_time < self.cooldown_seconds:
            time_left = int(self.cooldown_seconds - (current_time - last_time))
            return False, f"Alert in cooldown ({time_left}s remaining)"
        
        # Check max alerts per hour
        recent_alerts = [
            t for t in self.alert_history[symbol]
            if current_time - t < 3600
        ]
        
        if len(recent_alerts) >= self.max_alerts_per_hour:
            return False, f"Max alerts per hour reached ({self.max_alerts_per_hour})"
        
        # All checks passed
        return True, "All checks passed"
    
    def record_alert(self, analysis: Dict):
        """
        Record that an alert was sent
        
        Args:
            analysis: Analysis result dict
        """
        symbol = analysis['symbol']
        alert_type = analysis.get('alert_type', 'MONITOR')
        current_time = time.time()
        
        # Record time for cooldown
        alert_key = f"{symbol}:{alert_type}"
        self.last_alert_time[alert_key] = current_time
        
        # Record in history for rate limiting
        self.alert_history[symbol].append(current_time)
        
        # Clean up old history (older than 1 hour)
        self.alert_history[symbol] = [
            t for t in self.alert_history[symbol]
            if current_time - t < 3600
        ]
        
        self.logger.debug(f"Recorded alert: {symbol} - {alert_type}")
    
    def get_stats(self, symbol: Optional[str] = None) -> Dict:
        """
        Get statistics about alerts
        
        Args:
            symbol: Optional symbol to get stats for
        
        Returns:
            Statistics dict
        """
        current_time = time.time()
        
        if symbol:
            # Stats for specific symbol
            recent_alerts = [
                t for t in self.alert_history.get(symbol, [])
                if current_time - t < 3600
            ]
            
            return {
                'symbol': symbol,
                'alerts_last_hour': len(recent_alerts),
                'max_allowed_per_hour': self.max_alerts_per_hour,
                'can_send_more': len(recent_alerts) < self.max_alerts_per_hour
            }
        else:
            # Overall stats
            total_alerts = sum(len(alerts) for alerts in self.alert_history.values())
            symbols_tracked = len(self.alert_history)
            
            return {
                'total_alerts_sent': total_alerts,
                'symbols_tracked': symbols_tracked,
                'min_confidence': self.min_confidence,
                'cooldown_seconds': self.cooldown_seconds
            }
    
    def clear_history(self, symbol: Optional[str] = None):
        """
        Clear alert history
        
        Args:
            symbol: Optional symbol to clear (clears all if None)
        """
        if symbol:
            self.alert_history.pop(symbol, None)
            # Clear last alert times for this symbol
            keys_to_remove = [k for k in self.last_alert_time if k.startswith(f"{symbol}:")]
            for key in keys_to_remove:
                self.last_alert_time.pop(key, None)
            self.logger.info(f"Cleared history for {symbol}")
        else:
            self.alert_history.clear()
            self.last_alert_time.clear()
            self.logger.info("Cleared all history")


# CLI for testing
def main():
    """Command-line interface"""
    import yaml
    
    # Load config
    config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    discord_config = config.get('discord', {})
    
    filter = AlertFilter(discord_config)
    
    # Test alert
    test_analysis = {
        'symbol': 'SPY',
        'alert_type': 'STRONG BUY',
        'confidence': 90
    }
    
    should_send, reason = filter.should_send_alert(test_analysis)
    
    print(f"Test Alert: {test_analysis['symbol']} - {test_analysis['alert_type']}")
    print(f"Should Send: {'YES ✅' if should_send else 'NO ❌'}")
    print(f"Reason: {reason}")
    
    if should_send:
        filter.record_alert(test_analysis)
        print("\nAlert recorded")
    
    print("\nFilter Stats:")
    stats = filter.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == '__main__':
    main()