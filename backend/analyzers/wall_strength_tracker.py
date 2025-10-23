"""
backend/analyzers/wall_strength_tracker.py
Real-Time Gamma Wall Strength Tracker

Tracks OI/Volume changes at gamma walls every 5 minutes
Detects building vs weakening patterns
Generates alerts for institutional positioning momentum

DAY TRADER OPTIMIZED - Sensitive thresholds for intraday wall movement
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
import pytz


class WallStrengthTracker:
    def __init__(self, storage_path: str = 'backend/data/wall_history/'):
        """Initialize Wall Strength Tracker"""
        self.logger = logging.getLogger(__name__)
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # In-memory storage
        self.snapshots = defaultdict(list)
        self.baseline = {}
        self.alerts_generated = defaultdict(list)
        
        # DAY TRADER THRESHOLDS - Optimized for intraday wall movement
        self.building_thresholds = {
            'moderate': 10,   # +10% → 🔥 (was 25% - TOO HIGH)
            'strong': 20,     # +20% → 🔥🔥 (was 50% - TOO HIGH)
            'very_strong': 35 # +35% → 🔥🔥🔥 (was 75% - TOO HIGH)
        }
        
        self.weakening_thresholds = {
            'slight': 8,      # -8% → ⚠️ (was 15% - TOO HIGH)
            'moderate': 15,   # -15% → ⚠️⚠️ (was 25% - TOO HIGH)
            'breaking': 25    # -25% → 🚨 (was 40% - TOO HIGH)
        }
        
        self.logger.info("✅ Wall Strength Tracker initialized (DAY TRADER MODE)")
        self.logger.info(f"   📁 Storage: {self.storage_path}")
        self.logger.info(f"   🔥 Building thresholds: {self.building_thresholds['moderate']}% / {self.building_thresholds['strong']}% / {self.building_thresholds['very_strong']}%")
        self.logger.info(f"   ⚠️ Weakening thresholds: {self.weakening_thresholds['slight']}% / {self.weakening_thresholds['moderate']}% / {self.weakening_thresholds['breaking']}%")
    
    def capture_snapshot(self, symbol: str, current_price: float, gamma_data: Dict) -> Dict:
        """Capture current gamma wall snapshot"""
        try:
            gamma_levels = gamma_data.get('gamma_levels', [])
            
            if not gamma_levels:
                return None
            
            # Get top 5 resistance + top 5 support
            sorted_levels = sorted(gamma_levels, key=lambda x: x['strike'], reverse=True)
            resistance = [l for l in sorted_levels if l['strike'] > current_price][:5]
            support = [l for l in sorted_levels if l['strike'] <= current_price][:5]
            
            walls = resistance + support
            
            snapshot = {
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'current_price': current_price,
                'walls': [
                    {
                        'strike': wall['strike'],
                        'type': wall['type'],
                        'total_oi': wall['total_oi'],
                        'call_oi': wall['call_oi'],
                        'put_oi': wall['put_oi'],
                        'volume': wall['total_volume'],
                        'gamma_exposure': wall['gamma_exposure'],
                        'strength': wall['strength'],
                        'distance_pct': wall['distance_pct']
                    }
                    for wall in walls
                ]
            }
            
            # Store snapshot
            self.snapshots[symbol].append(snapshot)
            
            # Set baseline if first snapshot of the day
            if symbol not in self.baseline:
                self.baseline[symbol] = snapshot
                self.logger.info(f"📊 Baseline set for {symbol}: {len(walls)} walls")
            
            return snapshot
            
        except Exception as e:
            self.logger.error(f"Error capturing snapshot for {symbol}: {str(e)}")
            return None
    
    def calculate_changes(self, symbol: str, current_snapshot: Dict) -> List[Dict]:
        """Calculate changes from baseline for all walls"""
        if symbol not in self.baseline:
            return []
        
        baseline_snapshot = self.baseline[symbol]
        current_walls = {w['strike']: w for w in current_snapshot['walls']}
        baseline_walls = {w['strike']: w for w in baseline_snapshot['walls']}
        
        changes = []
        
        for strike, current_wall in current_walls.items():
            if strike not in baseline_walls:
                continue
            
            baseline_wall = baseline_walls[strike]
            
            # Calculate OI change
            baseline_oi = baseline_wall['total_oi']
            current_oi = current_wall['total_oi']
            
            if baseline_oi == 0:
                continue
            
            change_pct = ((current_oi - baseline_oi) / baseline_oi) * 100
            change_absolute = current_oi - baseline_oi
            
            # Determine pattern
            pattern = self._detect_pattern(change_pct)
            
            # Build timeline
            timeline = self._build_timeline(symbol, strike)
            
            changes.append({
                'strike': strike,
                'type': current_wall['type'],
                'baseline_oi': baseline_oi,
                'current_oi': current_oi,
                'change_pct': round(change_pct, 1),
                'change_absolute': change_absolute,
                'pattern': pattern,
                'strength_change': f"{baseline_wall['strength']} → {current_wall['strength']}",
                'timeline': timeline,
                'distance_pct': current_wall['distance_pct']
            })
        
        return changes
    
    def _detect_pattern(self, change_pct: float) -> str:
        """Detect pattern from % change"""
        if change_pct >= self.building_thresholds['moderate']:
            return 'BUILDING'
        elif change_pct <= -self.weakening_thresholds['slight']:
            return 'WEAKENING'
        else:
            return 'STABLE'
    
    def _build_timeline(self, symbol: str, strike: float) -> List[Dict]:
        """Build timeline of OI changes for specific strike"""
        if symbol not in self.snapshots:
            return []
        
        timeline = []
        baseline_oi = None
        
        for snapshot in self.snapshots[symbol]:
            wall = next((w for w in snapshot['walls'] if w['strike'] == strike), None)
            
            if not wall:
                continue
            
            if baseline_oi is None:
                baseline_oi = wall['total_oi']
            
            change_pct = ((wall['total_oi'] - baseline_oi) / baseline_oi * 100) if baseline_oi > 0 else 0
            
            timeline.append({
                'time': datetime.fromisoformat(snapshot['timestamp']).strftime('%H:%M'),
                'oi': wall['total_oi'],
                'change_pct': round(change_pct, 1)
            })
        
        return timeline
    
    def generate_alerts(self, symbol: str, changes: List[Dict]) -> List[Dict]:
        """Generate alerts for significant wall changes"""
        alerts = []
        
        for change in changes:
            change_pct = change['change_pct']
            pattern = change['pattern']
            
            # Building alerts (LOWERED THRESHOLDS FOR DAY TRADING)
            if pattern == 'BUILDING':
                if change_pct >= self.building_thresholds['very_strong']:
                    urgency = 'VERY_STRONG'
                    emoji = '🔥🔥🔥'
                elif change_pct >= self.building_thresholds['strong']:
                    urgency = 'STRONG'
                    emoji = '🔥🔥'
                elif change_pct >= self.building_thresholds['moderate']:
                    urgency = 'MODERATE'
                    emoji = '🔥'
                else:
                    continue
                
                alert = {
                    'type': 'WALL_BUILDING',
                    'symbol': symbol,
                    'strike': change['strike'],
                    'wall_type': change['type'],
                    'change_pct': change['change_pct'],
                    'urgency': urgency,
                    'emoji': emoji,
                    'message': f"{emoji} ${change['strike']} {change['type']} BUILDING",
                    'timeline': change['timeline'],
                    'distance_pct': change['distance_pct'],
                    'timestamp': datetime.now().isoformat()
                }
                
                alerts.append(alert)
            
            # Weakening alerts (LOWERED THRESHOLDS FOR DAY TRADING)
            elif pattern == 'WEAKENING':
                if abs(change_pct) >= self.weakening_thresholds['breaking']:
                    urgency = 'BREAKING'
                    emoji = '🚨💥'
                elif abs(change_pct) >= self.weakening_thresholds['moderate']:
                    urgency = 'MODERATE'
                    emoji = '⚠️⚠️'
                elif abs(change_pct) >= self.weakening_thresholds['slight']:
                    urgency = 'SLIGHT'
                    emoji = '⚠️'
                else:
                    continue
                
                alert = {
                    'type': 'WALL_WEAKENING',
                    'symbol': symbol,
                    'strike': change['strike'],
                    'wall_type': change['type'],
                    'change_pct': change['change_pct'],
                    'urgency': urgency,
                    'emoji': emoji,
                    'message': f"{emoji} ${change['strike']} {change['type']} DECAYING",
                    'timeline': change['timeline'],
                    'distance_pct': change['distance_pct'],
                    'timestamp': datetime.now().isoformat()
                }
                
                alerts.append(alert)
        
        # Store alerts
        if alerts:
            self.alerts_generated[symbol].extend(alerts)
        
        return alerts
    
    def track_wall_strength(self, symbol: str, current_price: float, gamma_data: Dict) -> Dict:
        """Main tracking method - captures snapshot and returns changes"""
        try:
            # Capture current snapshot
            snapshot = self.capture_snapshot(symbol, current_price, gamma_data)
            
            if not snapshot:
                return {
                    'available': False,
                    'reason': 'No gamma data'
                }
            
            # Calculate changes
            changes = self.calculate_changes(symbol, snapshot)
            
            # Generate alerts
            alerts = self.generate_alerts(symbol, changes)
            
            # Get baseline time
            baseline_time = None
            if symbol in self.baseline:
                baseline_time = datetime.fromisoformat(self.baseline[symbol]['timestamp']).strftime('%H:%M')
            
            return {
                'available': True,
                'symbol': symbol,
                'baseline_time': baseline_time,
                'last_update': datetime.now().strftime('%H:%M:%S'),
                'snapshot_count': len(self.snapshots.get(symbol, [])),
                'walls_tracked': len(snapshot['walls']),
                'changes': changes,
                'alerts': alerts,
                'new_alerts_count': len(alerts)
            }
            
        except Exception as e:
            self.logger.error(f"Error tracking wall strength for {symbol}: {str(e)}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def get_wall_strength_summary(self, symbol: str) -> Dict:
        """Get summary of wall strength for symbol"""
        if symbol not in self.snapshots or not self.snapshots[symbol]:
            return {
                'available': False,
                'reason': 'No snapshots'
            }
        
        latest_snapshot = self.snapshots[symbol][-1]
        changes = self.calculate_changes(symbol, latest_snapshot)
        recent_alerts = self.alerts_generated.get(symbol, [])[-5:]
        
        return {
            'available': True,
            'symbol': symbol,
            'baseline_time': datetime.fromisoformat(self.baseline[symbol]['timestamp']).strftime('%H:%M') if symbol in self.baseline else None,
            'last_update': datetime.fromisoformat(latest_snapshot['timestamp']).strftime('%H:%M:%S'),
            'walls': changes,
            'recent_alerts': recent_alerts
        }
    
    def get_recent_alerts(self, symbol: str, limit: int = 10) -> List[Dict]:
        """Get recent alerts for symbol"""
        return self.alerts_generated.get(symbol, [])[-limit:]
    
    def save_to_disk(self, symbol: str):
        """Save snapshots to disk as JSON"""
        try:
            file_path = self.storage_path / f"{symbol}_{datetime.now().strftime('%Y%m%d')}.json"
            
            data = {
                'symbol': symbol,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'baseline': self.baseline.get(symbol),
                'snapshots': self.snapshots.get(symbol, []),
                'alerts': self.alerts_generated.get(symbol, [])
            }
            
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.logger.debug(f"💾 Saved wall history for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Error saving wall history for {symbol}: {str(e)}")
    
    def load_from_disk(self, symbol: str):
        """Load snapshots from disk"""
        try:
            file_path = self.storage_path / f"{symbol}_{datetime.now().strftime('%Y%m%d')}.json"
            
            if not file_path.exists():
                return
            
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            if data.get('baseline'):
                self.baseline[symbol] = data['baseline']
            
            if data.get('snapshots'):
                self.snapshots[symbol] = data['snapshots']
            
            if data.get('alerts'):
                self.alerts_generated[symbol] = data['alerts']
            
            self.logger.info(f"📥 Loaded wall history for {symbol}: {len(data.get('snapshots', []))} snapshots")
            
        except Exception as e:
            self.logger.error(f"Error loading wall history for {symbol}: {str(e)}")
    
    def reset_daily(self, symbol: str = None):
        """Reset tracking for new day"""
        if symbol:
            # Save before reset
            self.save_to_disk(symbol)
            
            # Clear memory
            if symbol in self.baseline:
                del self.baseline[symbol]
            if symbol in self.snapshots:
                del self.snapshots[symbol]
            if symbol in self.alerts_generated:
                del self.alerts_generated[symbol]
            
            self.logger.info(f"🔄 Daily reset for {symbol}")
        else:
            # Reset all symbols
            for sym in list(self.baseline.keys()):
                self.save_to_disk(sym)
            
            self.baseline.clear()
            self.snapshots.clear()
            self.alerts_generated.clear()
            
            self.logger.info("🔄 Daily reset for all symbols")
    
    def get_statistics(self) -> Dict:
        """Get tracker statistics"""
        total_snapshots = sum(len(snaps) for snaps in self.snapshots.values())
        total_alerts = sum(len(alerts) for alerts in self.alerts_generated.values())
        
        return {
            'symbols_tracked': len(self.baseline),
            'total_snapshots': total_snapshots,
            'total_alerts_generated': total_alerts,
            'storage_path': str(self.storage_path)
        }