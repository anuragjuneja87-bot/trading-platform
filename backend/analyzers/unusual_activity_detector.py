"""
backend/analyzers/unusual_activity_detector.py
Unusual OI/Volume Activity Detector - Feature 3

Detects abnormal open interest and volume changes at specific strikes
Identifies smart money positioning and institutional flow
Generates scored alerts for unusual options activity

DAY TRADER OPTIMIZED - Sensitive thresholds for 8-hour monitoring
This is what FlowAlgo charges $299/month for!
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np


class UnusualActivityDetector:
    def __init__(self):
        """Initialize Unusual Activity Detector"""
        self.logger = logging.getLogger(__name__)
        
        # In-memory storage (same pattern as wall_strength_tracker)
        self.snapshots = defaultdict(list)  # {symbol: [snapshot1, snapshot2, ...]}
        self.baseline = {}  # {symbol: {strike_key: baseline_data}}
        self.alerts_generated = defaultdict(list)  # {symbol: [alert1, alert2, ...]}
        
        # DAY TRADER THRESHOLDS - Optimized for intraday activity detection
        # These catch smart money moves EARLY before they become obvious
        self.thresholds = {
            'oi_change': {
                'moderate': 1.15,   # 15% increase (was 50% - TOO HIGH)
                'high': 1.35,       # 35% increase (was 100% - TOO HIGH)
                'extreme': 1.75     # 75% increase (was 200% - TOO HIGH)
            },
            'volume_ratio': {
                'moderate': 1.5,    # 1.5x average (was 2x - more sensitive)
                'high': 2.0,        # 2x average (was 3x)
                'extreme': 3.0      # 3x average (was 5x)
            },
            'premium_swept': {
                'moderate': 250_000,     # $250K (was $500K - catch smaller flows)
                'high': 500_000,         # $500K (was $1M)
                'extreme': 2_000_000     # $2M (was $5M - more realistic)
            },
            'min_oi': 50,               # Lowered from 100 - catch more strikes
            'min_volume': 25,           # Lowered from 50 - catch early activity
            'lookback_minutes': 15,     # Compare to 15 minutes ago
            'alert_threshold': 4.5,     # Score >= 4.5 triggers alert (was 7.0 - TOO HIGH)
            'extreme_threshold': 7.5    # Score >= 7.5 = extreme urgency (was 8.5)
        }
        
        self.logger.info("✅ Unusual Activity Detector initialized (DAY TRADER MODE)")
        self.logger.info(f"   ⚙️ OI threshold: {self.thresholds['oi_change']['moderate']}x (15% change)")
        self.logger.info(f"   ⚙️ Volume threshold: {self.thresholds['volume_ratio']['moderate']}x (1.5x average)")
        self.logger.info(f"   ⚙️ Alert threshold: {self.thresholds['alert_threshold']}/10 (sensitive)")
    
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
                # Safe extraction with null handling
                strike = self._safe_float(option.get('strike'), 0)
                option_type = option.get('option_type', '').lower()
                oi = self._safe_int(option.get('open_interest'), 0)
                volume = self._safe_int(option.get('volume'), 0)
                last_price = self._safe_float(option.get('last'), 0)
                
                # Validate we have minimum required data
                if strike <= 0 or not option_type:
                    continue
                
                # Skip if below minimums (lowered for day trading)
                if oi < self.thresholds['min_oi'] or volume < self.thresholds['min_volume']:
                    continue
                
                # Create unique key for this strike + type
                strike_key = f"{strike}_{option_type}"
                
                # Calculate premium swept
                premium_swept = volume * last_price * 100  # 100 shares per contract
                
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
            
            # If no valid strikes found, return None
            if not snapshot['strikes']:
                self.logger.debug(f"{symbol}: No valid strikes found in options data")
                return None
            
            # Store snapshot
            self.snapshots[symbol].append(snapshot)
            
            # Keep only last hour of snapshots (memory management)
            cutoff_time = datetime.now() - timedelta(hours=1)
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
            # Update rolling average for volume (exponential moving average)
            old_avg = self.baseline[symbol][strike_key]['avg_volume']
            new_volume = current_data['volume']
            alpha = 0.3  # Weight for new data
            self.baseline[symbol][strike_key]['avg_volume'] = (alpha * new_volume) + ((1 - alpha) * old_avg)
    
    def detect_unusual_activity(self, symbol: str, current_snapshot: Dict) -> List[Dict]:
        """Detect unusual activity by comparing current to baseline"""
        if symbol not in self.baseline:
            return []
        
        unusual_activities = []
        
        # Get snapshot from lookback period ago
        lookback_minutes = self.thresholds['lookback_minutes']
        lookback_time = datetime.now() - timedelta(minutes=lookback_minutes)
        
        # Find closest snapshot to lookback time
        lookback_snapshot = None
        for snapshot in reversed(self.snapshots[symbol]):
            snapshot_time = datetime.fromisoformat(snapshot['timestamp'])
            if snapshot_time <= lookback_time:
                lookback_snapshot = snapshot
                break
        
        if not lookback_snapshot:
            # Not enough history yet
            return []
        
        # Analyze each strike
        for strike_key, current_data in current_snapshot['strikes'].items():
            # Get lookback data
            lookback_data = lookback_snapshot['strikes'].get(strike_key)
            if not lookback_data:
                continue
            
            # Get baseline data
            baseline_data = self.baseline[symbol].get(strike_key)
            if not baseline_data:
                continue
            
            # Calculate OI change
            oi_change = current_data['oi'] - lookback_data['oi']
            oi_change_pct = (oi_change / lookback_data['oi'] * 100) if lookback_data['oi'] > 0 else 0
            
            # Calculate volume ratio
            avg_volume = baseline_data['avg_volume']
            volume_ratio = current_data['volume'] / avg_volume if avg_volume > 0 else 0
            
            # Calculate premium swept
            premium_swept = current_data['premium_swept']
            
            # Score this activity (0-10)
            score = self._calculate_unusual_score(
                abs(oi_change_pct),
                volume_ratio,
                premium_swept
            )
            
            # Only alert if score meets threshold (LOWERED for day trading)
            if score < self.thresholds['alert_threshold']:
                continue
            
            # Determine urgency
            if score >= self.thresholds['extreme_threshold']:
                urgency = 'EXTREME'
            elif score >= 6.0:
                urgency = 'HIGH'
            else:
                urgency = 'MODERATE'
            
            # Classify the activity
            classification = self._classify_activity(
                current_data['option_type'],
                oi_change,
                volume_ratio
            )
            
            # Generate alert message
            message = self._generate_alert_message(
                symbol,
                current_data['strike'],
                current_data['option_type'],
                oi_change_pct,
                volume_ratio,
                premium_swept
            )
            
            alert = {
                'symbol': symbol,
                'strike': current_data['strike'],
                'option_type': current_data['option_type'],
                'oi': current_data['oi'],
                'oi_change': oi_change,
                'oi_change_pct': oi_change_pct,
                'volume': current_data['volume'],
                'avg_volume': avg_volume,
                'volume_ratio': volume_ratio,
                'last_price': current_data['last_price'],
                'premium_swept': premium_swept,
                'score': score,
                'urgency': urgency,
                'classification': classification,
                'message': message,
                'distance_from_price': current_data['distance_from_price'],
                'distance_pct': current_data['distance_pct'],
                'greeks': current_data['greeks'],
                'timestamp': datetime.now().isoformat()
            }
            
            unusual_activities.append(alert)
            
            # Update baseline
            self.update_baseline(symbol, strike_key, current_data)
        
        # Store alerts
        if unusual_activities:
            self.alerts_generated[symbol].extend(unusual_activities)
            
            # Keep only last 100 alerts per symbol (memory management)
            self.alerts_generated[symbol] = self.alerts_generated[symbol][-100:]
        
        return unusual_activities
    
    def _calculate_unusual_score(self, oi_change_pct: float, 
                                 volume_ratio: float,
                                 premium_swept: float) -> float:
        """Calculate unusual activity score (0-10) - DAY TRADER OPTIMIZED"""
        score = 0.0
        
        # OI change contribution (0-4 points) - MORE SENSITIVE
        oi_thresholds = self.thresholds['oi_change']
        oi_ratio = (oi_change_pct / 100) + 1  # Convert back to ratio
        
        if oi_ratio >= oi_thresholds['extreme']:
            score += 4.0
        elif oi_ratio >= oi_thresholds['high']:
            score += 3.5
        elif oi_ratio >= oi_thresholds['moderate']:
            score += 2.5
        else:
            # Gradual scoring for smaller changes
            score += (oi_ratio - 1.0) / (oi_thresholds['moderate'] - 1.0) * 2.0
        
        # Volume ratio contribution (0-4 points) - MORE SENSITIVE
        vol_thresholds = self.thresholds['volume_ratio']
        if volume_ratio >= vol_thresholds['extreme']:
            score += 4.0
        elif volume_ratio >= vol_thresholds['high']:
            score += 3.5
        elif volume_ratio >= vol_thresholds['moderate']:
            score += 2.5
        else:
            # Gradual scoring for smaller ratios
            score += (volume_ratio / vol_thresholds['moderate']) * 2.0
        
        # Premium swept contribution (0-2 points) - ADJUSTED FOR REALITY
        prem_thresholds = self.thresholds['premium_swept']
        if premium_swept >= prem_thresholds['extreme']:
            score += 2.0
        elif premium_swept >= prem_thresholds['high']:
            score += 1.5
        elif premium_swept >= prem_thresholds['moderate']:
            score += 1.0
        else:
            # Gradual scoring for smaller premiums
            score += (premium_swept / prem_thresholds['moderate']) * 0.8
        
        # Cap at 10
        return min(score, 10.0)
    
    def _classify_activity(self, option_type: str, oi_change: int, 
                          volume_ratio: float) -> str:
        """Classify the unusual activity"""
        # Determine action (buying vs selling)
        if oi_change > 0:
            action = "BUYING"  # OI increasing = new positions
        else:
            action = "SELLING"  # OI decreasing = closing positions
        
        # Determine sentiment
        if option_type == 'call':
            if action == "BUYING":
                sentiment = "BULLISH"
            else:
                sentiment = "BEARISH"  # Call selling = bearish
        else:  # PUT
            if action == "BUYING":
                sentiment = "BEARISH"
            else:
                sentiment = "BULLISH"  # Put selling = bullish
        
        return f"{sentiment}_{option_type.upper()}_{action}"
    
    def _generate_alert_message(self, symbol: str, strike: float, option_type: str,
                                oi_change_pct: float, volume_ratio: float,
                                premium_swept: float) -> str:
        """Generate human-readable alert message"""
        # Format premium
        if premium_swept >= 1_000_000:
            premium_str = f"${premium_swept/1_000_000:.1f}M"
        elif premium_swept >= 1_000:
            premium_str = f"${premium_swept/1_000:.0f}K"
        else:
            premium_str = f"${premium_swept:.0f}"
        
        # Emoji based on magnitude (adjusted for day trading)
        if oi_change_pct >= 75 or volume_ratio >= 3.0:
            emoji = "🔥🔥"
        elif oi_change_pct >= 35 or volume_ratio >= 2.0:
            emoji = "🔥"
        else:
            emoji = "📊"
        
        return (
            f"{emoji} ${strike}{option_type[0].upper()} "
            f"+{oi_change_pct:.0f}% OI | "
            f"{volume_ratio:.1f}x Vol | "
            f"{premium_str} swept"
        )
    
    def analyze_unusual_activity(self, symbol: str, options_data: List[Dict],
                                current_price: float) -> Dict:
        """Main analysis method - captures snapshot and detects unusual activity"""
        try:
            # Capture current snapshot
            snapshot = self.capture_snapshot(symbol, options_data, current_price)
            
            if not snapshot:
                return {
                    'symbol': symbol,
                    'detected': False,
                    'reason': 'No options data available'
                }
            
            # Detect unusual activity
            alerts = self.detect_unusual_activity(symbol, snapshot)
            
            if not alerts:
                return {
                    'symbol': symbol,
                    'detected': False,
                    'alerts': [],
                    'count': 0,
                    'snapshot_count': len(self.snapshots.get(symbol, []))
                }
            
            # Sort by score (highest first)
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
            self.logger.error(f"Error analyzing unusual activity for {symbol}: {str(e)}", exc_info=True)
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