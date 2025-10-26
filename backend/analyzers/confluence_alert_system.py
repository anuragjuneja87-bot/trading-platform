"""
backend/analyzers/confluence_alert_system.py
Confluence Alert System - Feature #5

Combines ALL signals for high-probability setups:
- Gamma walls (support/resistance)
- Dark pool flow (institutional positioning)
- Volume analysis (RVOL, spikes)
- Key level confluence
- Pin probability (0DTE)

Only alerts when 3+ signals align (75%+ confidence)
Optimized for 6-7 figure day trader - don't miss setups
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, date


class ConfluenceAlertSystem:
    def __init__(self):
        """Initialize Confluence Alert System"""
        self.logger = logging.getLogger(__name__)
        
        # Alert thresholds (AGGRESSIVE for 6-7 figure trader)
        self.confidence_thresholds = {
            'alert': 75,      # Alert threshold (3+ signals)
            'high': 85,       # High priority
            'extreme': 90     # Extreme conviction (rare)
        }
        
        # Signal weights (normalized to 100)
        self.signal_weights = {
            'gamma_wall': 25,        # Gamma support/resistance
            'dark_pool': 20,         # Institutional flow
            'volume': 20,            # RVOL + spikes
            'key_levels': 20,        # Confluence scoring
            'pin_probability': 15    # 0DTE pin effect
        }
        
        # Cooldown tracking (prevent spam)
        self.alerts_sent_today = {}  # {symbol: {alert_type: timestamp}}
        self.cooldown_minutes = {
            'CONFLUENCE_BUY': 15,
            'CONFLUENCE_SELL': 15,
            'EXTREME_SETUP': 30
        }
        
        self.logger.info("✅ Confluence Alert System initialized")
        self.logger.info(f"   🎯 Alert threshold: {self.confidence_thresholds['alert']}%")
        self.logger.info(f"   ⚡ Optimized for 6-7 figure day trader")
    
    def analyze_confluence(self, symbol: str, analysis_data: Dict) -> Dict:
        """
        Analyze signal confluence from complete analysis
        
        Args:
            symbol: Stock symbol
            analysis_data: Complete analysis from analyzer.analyze()
        
        Returns:
            Confluence analysis with confidence score
        """
        try:
            current_price = analysis_data.get('current_price', 0)
            
            if current_price == 0:
                return {
                    'symbol': symbol,
                    'available': False,
                    'reason': 'No price data'
                }
            
            # Score each signal component
            signals = {
                'gamma_wall': self._score_gamma_wall(analysis_data),
                'dark_pool': self._score_dark_pool(analysis_data),
                'volume': self._score_volume(analysis_data),
                'key_levels': self._score_key_levels(analysis_data),
                'pin_probability': self._score_pin_probability(analysis_data)
            }
            
            # Calculate weighted confidence
            total_confidence = 0
            active_signals = []
            
            for signal_name, signal_data in signals.items():
                if signal_data['active']:
                    weight = self.signal_weights[signal_name]
                    strength = signal_data['strength']  # 0-1
                    contribution = weight * strength
                    total_confidence += contribution
                    
                    active_signals.append({
                        'name': signal_name,
                        'direction': signal_data['direction'],
                        'strength': strength,
                        'contribution': contribution,
                        'reason': signal_data['reason']
                    })
            
            # Determine overall direction (majority vote weighted by strength)
            bullish_weight = sum(s['contribution'] for s in active_signals if s['direction'] == 'BULLISH')
            bearish_weight = sum(s['contribution'] for s in active_signals if s['direction'] == 'BEARISH')
            
            if bullish_weight > bearish_weight:
                overall_direction = 'BULLISH'
                confidence = total_confidence
            elif bearish_weight > bullish_weight:
                overall_direction = 'BEARISH'
                confidence = total_confidence
            else:
                overall_direction = 'NEUTRAL'
                confidence = total_confidence * 0.5  # Reduce confidence for mixed signals
            
            # Determine priority
            if confidence >= self.confidence_thresholds['extreme']:
                priority = 'EXTREME'
            elif confidence >= self.confidence_thresholds['high']:
                priority = 'HIGH'
            elif confidence >= self.confidence_thresholds['alert']:
                priority = 'MEDIUM'
            else:
                priority = 'LOW'
            
            # Should alert?
            should_alert = confidence >= self.confidence_thresholds['alert']
            
            # Generate setup description
            setup_type = self._determine_setup_type(signals, overall_direction)
            
            # Get entry/exit targets from analysis
            targets = analysis_data.get('entry_targets', {})
            
            return {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'available': True,
                'current_price': current_price,
                'confluence': {
                    'confidence': round(confidence, 1),
                    'direction': overall_direction,
                    'priority': priority,
                    'should_alert': should_alert,
                    'signals_count': len(active_signals),
                    'setup_type': setup_type
                },
                'active_signals': active_signals,
                'all_signals': signals,
                'targets': {
                    'entry': targets.get('entry'),
                    'stop_loss': targets.get('stop_loss'),
                    'tp1': targets.get('tp1'),
                    'tp2': targets.get('tp2'),
                    'risk_reward': targets.get('risk_reward')
                },
                'interpretation': self._generate_interpretation(
                    overall_direction, confidence, active_signals, setup_type
                )
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing confluence: {str(e)}")
            return {
                'symbol': symbol,
                'available': False,
                'error': str(e)
            }
    
    def _score_gamma_wall(self, data: Dict) -> Dict:
        """Score gamma wall signal"""
        try:
            oi_data = data.get('open_interest', {})
            current_price = data.get('current_price', 0)
            
            if not oi_data.get('available'):
                return {'active': False, 'direction': 'NEUTRAL', 'strength': 0, 'reason': 'No gamma data'}
            
            nearest_wall = oi_data.get('nearest_wall')
            
            if not nearest_wall:
                return {'active': False, 'direction': 'NEUTRAL', 'strength': 0, 'reason': 'No nearby walls'}
            
            wall_type = nearest_wall.get('type', '')
            distance_pct = abs(nearest_wall.get('distance_pct', 999))
            strength_label = nearest_wall.get('strength', '')
            
            # Score based on proximity and strength
            if distance_pct > 2.0:
                return {'active': False, 'direction': 'NEUTRAL', 'strength': 0, 'reason': 'Wall too far'}
            
            # Proximity factor (closer = stronger)
            if distance_pct <= 0.5:
                proximity_factor = 1.0
            elif distance_pct <= 1.0:
                proximity_factor = 0.8
            else:
                proximity_factor = 0.6
            
            # Strength factor
            if strength_label in ['VERY_STRONG', 'EXTREME']:
                strength_factor = 1.0
            elif strength_label == 'STRONG':
                strength_factor = 0.8
            else:
                strength_factor = 0.6
            
            final_strength = proximity_factor * strength_factor
            
            # Direction
            if wall_type == 'SUPPORT':
                direction = 'BULLISH'
                reason = f"At {wall_type} ${nearest_wall['strike']:.2f} ({distance_pct:.1f}% away)"
            else:
                direction = 'BEARISH'
                reason = f"At {wall_type} ${nearest_wall['strike']:.2f} ({distance_pct:.1f}% away)"
            
            return {
                'active': True,
                'direction': direction,
                'strength': final_strength,
                'reason': reason
            }
            
        except:
            return {'active': False, 'direction': 'NEUTRAL', 'strength': 0, 'reason': 'Error'}
    
    def _score_dark_pool(self, data: Dict) -> Dict:
        """Score dark pool signal"""
        try:
            dp_data = data.get('dark_pool_details', {})
            
            flow = dp_data.get('institutional_flow', 'NEUTRAL')
            strength = dp_data.get('signal_strength', 0)
            
            if flow == 'NEUTRAL' or strength < 4:
                return {'active': False, 'direction': 'NEUTRAL', 'strength': 0, 'reason': 'Weak dark pool signal'}
            
            # Normalize strength (0-6 scale to 0-1)
            normalized_strength = min(strength / 6.0, 1.0)
            
            direction = 'BULLISH' if flow == 'BUYING' else 'BEARISH'
            reason = f"{flow} detected (strength {strength}/6)"
            
            return {
                'active': True,
                'direction': direction,
                'strength': normalized_strength,
                'reason': reason
            }
            
        except:
            return {'active': False, 'direction': 'NEUTRAL', 'strength': 0, 'reason': 'Error'}
    
    def _score_volume(self, data: Dict) -> Dict:
        """Score volume signal (RVOL + spikes)"""
        try:
            vol_data = data.get('volume_analysis', {})
            rvol_data = vol_data.get('rvol', {})
            spike_data = vol_data.get('volume_spike', {})
            
            rvol = rvol_data.get('rvol', 0)
            classification = rvol_data.get('classification', 'UNKNOWN')
            spike_detected = spike_data.get('spike_detected', False)
            
            # Need either elevated RVOL or spike
            if classification not in ['HIGH', 'EXTREME'] and not spike_detected:
                return {'active': False, 'direction': 'NEUTRAL', 'strength': 0, 'reason': 'Normal volume'}
            
            # Calculate strength
            if classification == 'EXTREME':
                strength = 1.0
                reason = f"Extreme RVOL ({rvol:.1f}x)"
            elif classification == 'HIGH':
                strength = 0.8
                reason = f"High RVOL ({rvol:.1f}x)"
            elif spike_detected:
                strength = 0.7
                reason = "Volume spike detected"
            else:
                strength = 0.6
                reason = f"Elevated RVOL ({rvol:.1f}x)"
            
            # Volume confirms direction from price action
            signal = data.get('signal', 'NEUTRAL')
            if signal in ['BUY', 'STRONG BUY']:
                direction = 'BULLISH'
            elif signal in ['SELL', 'STRONG SELL']:
                direction = 'BEARISH'
            else:
                direction = 'NEUTRAL'
                strength *= 0.5
            
            return {
                'active': True,
                'direction': direction,
                'strength': strength,
                'reason': reason
            }
            
        except:
            return {'active': False, 'direction': 'NEUTRAL', 'strength': 0, 'reason': 'Error'}
    
    def _score_key_levels(self, data: Dict) -> Dict:
        """Score key level confluence"""
        try:
            levels = data.get('key_levels', {})
            
            at_support = levels.get('at_support', False)
            at_resistance = levels.get('at_resistance', False)
            confluence = levels.get('confluence_score', 0)
            
            if not at_support and not at_resistance:
                return {'active': False, 'direction': 'NEUTRAL', 'strength': 0, 'reason': 'Not at key level'}
            
            # Normalize confluence (0-10 scale to 0-1)
            normalized_strength = min(confluence / 10.0, 1.0)
            
            if normalized_strength < 0.6:
                return {'active': False, 'direction': 'NEUTRAL', 'strength': 0, 'reason': 'Weak confluence'}
            
            if at_support:
                direction = 'BULLISH'
                reason = f"At support (confluence {confluence}/10)"
            else:
                direction = 'BEARISH'
                reason = f"At resistance (confluence {confluence}/10)"
            
            return {
                'active': True,
                'direction': direction,
                'strength': normalized_strength,
                'reason': reason
            }
            
        except:
            return {'active': False, 'direction': 'NEUTRAL', 'strength': 0, 'reason': 'Error'}
    
    def _score_pin_probability(self, data: Dict) -> Dict:
        """Score pin probability (0DTE only)"""
        try:
            # This would come from separate pin analysis
            # For now, check if we have 0DTE expiration
            oi_data = data.get('open_interest', {})
            
            # Pin probability not always available
            return {'active': False, 'direction': 'NEUTRAL', 'strength': 0, 'reason': 'Not 0DTE or no pin data'}
            
        except:
            return {'active': False, 'direction': 'NEUTRAL', 'strength': 0, 'reason': 'Error'}
    
    def _determine_setup_type(self, signals: Dict, direction: str) -> str:
        """Determine specific setup type"""
        
        gamma = signals['gamma_wall']
        dark_pool = signals['dark_pool']
        volume = signals['volume']
        levels = signals['key_levels']
        
        if direction == 'BULLISH':
            if gamma['active'] and levels['active']:
                return "BOUNCE_PLAY"
            elif dark_pool['active'] and volume['active']:
                return "ACCUMULATION"
            elif volume['active']:
                return "BREAKOUT_SETUP"
            else:
                return "LONG_BIAS"
        elif direction == 'BEARISH':
            if gamma['active'] and levels['active']:
                return "REJECTION_PLAY"
            elif dark_pool['active'] and volume['active']:
                return "DISTRIBUTION"
            elif volume['active']:
                return "BREAKDOWN_SETUP"
            else:
                return "SHORT_BIAS"
        else:
            return "RANGE_BOUND"
    
    def _generate_interpretation(self, direction: str, confidence: float, 
                                 signals: List[Dict], setup_type: str) -> str:
        """Generate human-readable interpretation"""
        
        signal_names = [s['name'].replace('_', ' ').title() for s in signals]
        
        if confidence >= 90:
            conviction = "EXTREME CONVICTION"
        elif confidence >= 85:
            conviction = "HIGH CONVICTION"
        elif confidence >= 75:
            conviction = "GOOD CONVICTION"
        else:
            conviction = "MODERATE CONVICTION"
        
        interpretation = f"{conviction} {direction} {setup_type}\n\n"
        interpretation += f"✅ {len(signals)} signals aligned: {', '.join(signal_names)}\n\n"
        
        for signal in signals:
            interpretation += f"• {signal['name'].replace('_', ' ').title()}: {signal['reason']}\n"
        
        return interpretation
    
    def check_cooldown(self, symbol: str, alert_type: str) -> bool:
        """Check if alert is in cooldown"""
        try:
            today = date.today().isoformat()
            
            if symbol not in self.alerts_sent_today:
                self.alerts_sent_today[symbol] = {}
            
            if alert_type not in self.alerts_sent_today[symbol]:
                return True
            
            last_alert = self.alerts_sent_today[symbol][alert_type]
            
            # Check if same day
            if last_alert['date'] != today:
                return True
            
            # Check cooldown
            elapsed = (datetime.now() - last_alert['time']).total_seconds() / 60
            cooldown = self.cooldown_minutes.get(alert_type, 15)
            
            return elapsed >= cooldown
            
        except:
            return True
    
    def mark_alert_sent(self, symbol: str, alert_type: str):
        """Mark alert as sent"""
        today = date.today().isoformat()
        
        if symbol not in self.alerts_sent_today:
            self.alerts_sent_today[symbol] = {}
        
        self.alerts_sent_today[symbol][alert_type] = {
            'date': today,
            'time': datetime.now()
        }


# Testing
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    system = ConfluenceAlertSystem()
    
    # Sample analysis data
    sample_data = {
        'symbol': 'SPY',
        'current_price': 420.45,
        'signal': 'BUY',
        'open_interest': {
            'available': True,
            'nearest_wall': {
                'type': 'SUPPORT',
                'strike': 420,
                'distance_pct': 0.5,
                'strength': 'VERY_STRONG'
            }
        },
        'dark_pool_details': {
            'institutional_flow': 'BUYING',
            'signal_strength': 5
        },
        'volume_analysis': {
            'rvol': {
                'rvol': 2.8,
                'classification': 'HIGH'
            },
            'volume_spike': {
                'spike_detected': True
            }
        },
        'key_levels': {
            'at_support': True,
            'at_resistance': False,
            'confluence_score': 8
        }
    }
    
    result = system.analyze_confluence('SPY', sample_data)
    
    print(f"\nConfidence: {result['confluence']['confidence']}%")
    print(f"Direction: {result['confluence']['direction']}")
    print(f"Priority: {result['confluence']['priority']}")
    print(f"Should Alert: {result['confluence']['should_alert']}")
    print(f"\nActive Signals: {result['confluence']['signals_count']}")
    for signal in result['active_signals']:
        print(f"  • {signal['name']}: {signal['reason']}")
