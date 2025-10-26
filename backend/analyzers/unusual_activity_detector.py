"""
backend/analyzers/unusual_activity_detector.py
Unusual OI/Volume Activity Detector - PROFESSIONAL DAY TRADER EDITION

OPTIMIZED FOR:
- 6-figure position sizes
- Speed > Everything else
- First 2 hours focus (9:30-11:30 AM)
- Pre-market awareness
- Real-time decision making

AGGRESSIVE THRESHOLDS for early institutional flow detection
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np


class UnusualActivityDetector:
    def __init__(self):
        """Initialize Unusual Activity Detector - PROFESSIONAL MODE"""
        self.logger = logging.getLogger(__name__)
        
        # In-memory storage
        self.snapshots = defaultdict(list)
        self.baseline = {}
        self.alerts_generated = defaultdict(list)
        
        # PROFESSIONAL DAY TRADER THRESHOLDS
        # Optimized for SPEED and EARLY DETECTION
        self.thresholds = {
            'oi_change': {
                'moderate': 1.05,   # 5% increase (catch EARLY!)
                'high': 1.15,       # 15% increase
                'extreme': 1.35     # 35% increase
            },
            'volume_ratio': {
                'moderate': 1.2,    # 1.2x average (VERY sensitive)
                'high': 1.5,        # 1.5x average
                'extreme': 2.0      # 2x average
            },
            'premium_swept': {
                'moderate': 100_000,     # $100K (catch smaller institutional)
                'high': 250_000,         # $250K
                'extreme': 1_000_000     # $1M
            },
            'min_oi': 25,               # Lower for early detection
            'min_volume': 10,           # Catch first moves
            'lookback_minutes': 5,      # 5 min (FAST detection)
            'alert_threshold': 3.5,     # Score >= 3.5 = ALERT
            'extreme_threshold': 6.0    # Score >= 6.0 = EXTREME
        }
        
        self.logger.info("✅ Unusual Activity Detector - PROFESSIONAL MODE")
        self.logger.info(f"   ⚡ SPEED OPTIMIZED for 6-figure trading")
        self.logger.info(f"   🎯 OI threshold: {self.thresholds['oi_change']['moderate']}x (5% change)")
        self.logger.info(f"   🎯 Volume threshold: {self.thresholds['volume_ratio']['moderate']}x (1.2x average)")
        self.logger.info(f"   🎯 Alert threshold: {self.thresholds['alert_threshold']}/10 (AGGRESSIVE)")
        self.logger.info(f"   ⏱️ Lookback: {self.thresholds['lookback_minutes']} minutes (FAST)")
    
    def _safe_float(self, value, default=0.0) -> float:
        """Safely convert value to float with null handling"""
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    
    def _safe_int(self, value, default=0) -> int:
        """Safely convert value to int with null handling"""
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    
    def capture_snapshot(self, symbol: str, options_data: List[Dict], 
                        current_price: float) -> Optional[Dict]:
        """Capture current snapshot of OI and volume for all strikes"""
        try:
            if not options_data:
                return None
            
            snapshot = {
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'current_price': current_price,
                'strikes': {}
            }
            
            for option in options_data:
                strike = self._safe_float(option.get('strike'), 0)
                option_type = option.get('option_type', '').lower()
                oi = self._safe_int(option.get('open_interest'), 0)
                volume = self._safe_int(option.get('volume'), 0)
                last_price = self._safe_float(option.get('last'), 0)
                
                if strike <= 0 or not option_type:
                    continue
                
                # Lower minimums for early detection
                if oi < self.thresholds['min_oi'] or volume < self.thresholds['min_volume']:
                    continue
                
                strike_key = f"{strike}_{option_type}"
                
                # Calculate premium swept
                premium_swept = volume * last_price * 100
                
                snapshot['strikes'][strike_key] = {
                    'strike': strike,
                    'option_type': option_type,
                    'oi': oi,
                    'volume': volume,
                    'last_price': last_price,
                    'premium_swept': premium_swept,
                    'greeks': option.get('greeks', {}),
                    'distance_from_price': strike - current_price,
                    'distance_pct': ((strike - current_price) / current_price) * 100
                }
            
            if not snapshot['strikes']:
                self.logger.debug(f"{symbol}: No valid strikes found")
                return None
            
            # Store snapshot
            self.snapshots[symbol].append(snapshot)
            
            # Keep only last 30 minutes (memory management)
            cutoff_time = datetime.now() - timedelta(minutes=30)
            self.snapshots[symbol] = [
                s for s in self.snapshots[symbol]
                if datetime.fromisoformat(s['timestamp']) > cutoff_time
            ]
            
            # Set baseline if first snapshot
            if symbol not in self.baseline:
                self.baseline[symbol] = {}
                for strike_key, data in snapshot['strikes'].items():
                    self.baseline[symbol][strike_key] = {
                        'oi': data['oi'],
                        'avg_volume': data['volume']
                    }
                self.logger.info(f"📊 Baseline set for {symbol}: {len(snapshot['strikes'])} strikes")
            
            return snapshot
            
        except Exception as e:
            self.logger.error(f"Error capturing snapshot for {symbol}: {str(e)}", exc_info=True)
            return None
    
    def update_baseline(self, symbol: str, strike_key: str, current_data: Dict):
        """Update baseline with rolling average for volume"""
        if symbol not in self.baseline:
            self.baseline[symbol] = {}
        
        if strike_key not in self.baseline[symbol]:
            self.baseline[symbol][strike_key] = {
                'oi': current_data['oi'],
                'avg_volume': current_data['volume']
            }
        else:
            # Exponential moving average for volume
            old_avg = self.baseline[symbol][strike_key]['avg_volume']
            new_volume = current_data['volume']
            alpha = 0.4  # Higher weight for new data (faster response)
            self.baseline[symbol][strike_key]['avg_volume'] = (alpha * new_volume) + ((1 - alpha) * old_avg)
    
    def detect_unusual_activity(self, symbol: str, current_snapshot: Dict) -> List[Dict]:
        """Detect unusual activity - PROFESSIONAL SPEED MODE"""
        if symbol not in self.baseline:
            return []
        
        unusual_activities = []
        
        lookback_minutes = self.thresholds['lookback_minutes']
        lookback_time = datetime.now() - timedelta(minutes=lookback_minutes)
        
        # Find lookback snapshot
        lookback_snapshot = None
        for snapshot in reversed(self.snapshots[symbol]):
            snapshot_time = datetime.fromisoformat(snapshot['timestamp'])
            if snapshot_time <= lookback_time:
                lookback_snapshot = snapshot
                break
        
        for strike_key, current_data in current_snapshot['strikes'].items():
            try:
                baseline_data = self.baseline[symbol].get(strike_key)
                if not baseline_data:
                    continue
                
                strike = current_data['strike']
                option_type = current_data['option_type']
                current_oi = current_data['oi']
                current_volume = current_data['volume']
                premium_swept = current_data['premium_swept']
                
                # Get OI from lookback (if available)
                lookback_oi = baseline_data['oi']
                if lookback_snapshot and strike_key in lookback_snapshot['strikes']:
                    lookback_oi = lookback_snapshot['strikes'][strike_key]['oi']
                
                # Calculate changes
                oi_change = current_oi - lookback_oi
                oi_change_pct = (oi_change / lookback_oi * 100) if lookback_oi > 0 else 0
                
                avg_volume = baseline_data['avg_volume']
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
                
                # Check if unusual (AGGRESSIVE thresholds)
                oi_ratio = (oi_change_pct / 100) + 1
                
                is_unusual = (
                    (abs(oi_change_pct) >= (self.thresholds['oi_change']['moderate'] - 1) * 100) or
                    (volume_ratio >= self.thresholds['volume_ratio']['moderate']) or
                    (premium_swept >= self.thresholds['premium_swept']['moderate'])
                )
                
                if not is_unusual:
                    continue
                
                # Calculate score
                score = self._calculate_unusual_score(
                    oi_change_pct, volume_ratio, premium_swept
                )
                
                # Filter by score threshold
                if score < self.thresholds['alert_threshold']:
                    continue
                
                # Classify activity
                classification = self._classify_activity(option_type, oi_change, volume_ratio)
                
                # Determine urgency
                if score >= self.thresholds['extreme_threshold']:
                    urgency = 'EXTREME'
                elif score >= (self.thresholds['alert_threshold'] + 1.5):
                    urgency = 'HIGH'
                else:
                    urgency = 'MODERATE'
                
                # Create alert
                alert = {
                    'symbol': symbol,
                    'strike': strike,
                    'option_type': option_type,
                    'oi': current_oi,
                    'oi_change': oi_change,
                    'oi_change_pct': oi_change_pct,
                    'volume': current_volume,
                    'avg_volume': avg_volume,
                    'volume_ratio': volume_ratio,
                    'premium_swept': premium_swept,
                    'last_price': current_data['last_price'],
                    'classification': classification,
                    'urgency': urgency,
                    'score': score,
                    'timestamp': datetime.now().isoformat(),
                    'distance_from_price': current_data['distance_from_price'],
                    'distance_pct': current_data['distance_pct'],
                    'greeks': current_data['greeks']
                }
                
                unusual_activities.append(alert)
                
                self.logger.info(
                    f"🔥 UNUSUAL: {symbol} ${strike}{option_type[0].upper()} | "
                    f"Score: {score:.1f}/10 | {urgency} | "
                    f"OI: {oi_change:+,} ({oi_change_pct:+.0f}%) | "
                    f"Vol: {volume_ratio:.1f}x"
                )
                
            except Exception as e:
                self.logger.error(f"Error analyzing {strike_key}: {str(e)}")
                continue
            
            # Update baseline
            self.update_baseline(symbol, strike_key, current_data)
        
        # Store alerts
        if unusual_activities:
            self.alerts_generated[symbol].extend(unusual_activities)
            self.alerts_generated[symbol] = self.alerts_generated[symbol][-100:]
        
        return unusual_activities
    
    def _calculate_unusual_score(self, oi_change_pct: float, 
                                 volume_ratio: float,
                                 premium_swept: float) -> float:
        """Calculate score - PROFESSIONAL AGGRESSIVE SCORING"""
        score = 0.0
        
        # OI change (0-4 points) - VERY AGGRESSIVE
        oi_thresholds = self.thresholds['oi_change']
        oi_ratio = (oi_change_pct / 100) + 1
        
        if oi_ratio >= oi_thresholds['extreme']:
            score += 4.0
        elif oi_ratio >= oi_thresholds['high']:
            score += 3.5
        elif oi_ratio >= oi_thresholds['moderate']:
            score += 3.0  # Higher base score
        else:
            # Even small changes get points (1% = 0.1 point)
            score += max((oi_ratio - 1.0) * 10, 0)
        
        # Volume (0-4 points) - VERY AGGRESSIVE
        vol_thresholds = self.thresholds['volume_ratio']
        if volume_ratio >= vol_thresholds['extreme']:
            score += 4.0
        elif volume_ratio >= vol_thresholds['high']:
            score += 3.5
        elif volume_ratio >= vol_thresholds['moderate']:
            score += 3.0  # Higher base
        else:
            # Scale proportionally
            score += min(volume_ratio * 2, 2.5)
        
        # Premium (0-2 points) - INSTITUTIONAL FOCUS
        prem_thresholds = self.thresholds['premium_swept']
        if premium_swept >= prem_thresholds['extreme']:
            score += 2.0
        elif premium_swept >= prem_thresholds['high']:
            score += 1.5
        elif premium_swept >= prem_thresholds['moderate']:
            score += 1.0
        else:
            # Any premium gets partial score
            score += min(premium_swept / prem_thresholds['moderate'], 0.8)
        
        return min(score, 10.0)
    
    def _classify_activity(self, option_type: str, oi_change: int, 
                          volume_ratio: float) -> str:
        """Classify the unusual activity"""
        if oi_change > 0:
            action = "BUYING"
        else:
            action = "SELLING"
        
        if option_type == 'call':
            sentiment = "BULLISH" if action == "BUYING" else "BEARISH"
        else:
            sentiment = "BEARISH" if action == "BUYING" else "BULLISH"
        
        return f"{sentiment}_{option_type.upper()}_{action}"
    
    def analyze_unusual_activity(self, symbol: str, options_data: List[Dict],
                                current_price: float) -> Dict:
        """Main analysis method"""
        try:
            snapshot = self.capture_snapshot(symbol, options_data, current_price)
            
            if not snapshot:
                return {
                    'symbol': symbol,
                    'detected': False,
                    'reason': 'No options data available'
                }
            
            alerts = self.detect_unusual_activity(symbol, snapshot)
            
            if not alerts:
                return {
                    'symbol': symbol,
                    'detected': False,
                    'alerts': [],
                    'count': 0,
                    'snapshot_count': len(self.snapshots.get(symbol, []))
                }
            
            alerts.sort(key=lambda x: x['score'], reverse=True)
            
            return {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'detected': True,
                'alerts': alerts,
                'count': len(alerts),
                'highest_score': alerts[0]['score'],
                'highest_urgency': alerts[0]['urgency'],
                'snapshot_count': len(self.snapshots.get(symbol, []))
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing {symbol}: {str(e)}", exc_info=True)
            return {
                'symbol': symbol,
                'detected': False,
                'error': str(e)
            }
    
    def get_recent_alerts(self, symbol: str, limit: int = 10) -> List[Dict]:
        """Get recent alerts for symbol"""
        return self.alerts_generated.get(symbol, [])[-limit:]
    
    def get_statistics(self) -> Dict:
        """Get detector statistics"""
        total_snapshots = sum(len(snaps) for snaps in self.snapshots.values())
        total_alerts = sum(len(alerts) for alerts in self.alerts_generated.values())
        
        return {
            'symbols_tracked': len(self.baseline),
            'total_snapshots': total_snapshots,
            'total_alerts_generated': total_alerts,
            'symbols_with_alerts': len([s for s in self.alerts_generated if self.alerts_generated[s]])
        }
    
    def reset_daily(self, symbol: str = None):
        """Reset tracking for new day"""
        if symbol:
            if symbol in self.baseline:
                del self.baseline[symbol]
            if symbol in self.snapshots:
                del self.snapshots[symbol]
            if symbol in self.alerts_generated:
                del self.alerts_generated[symbol]
            self.logger.info(f"🔄 Daily reset for {symbol}")
        else:
            self.baseline.clear()
            self.snapshots.clear()
            self.alerts_generated.clear()
            self.logger.info("🔄 Daily reset for all symbols")