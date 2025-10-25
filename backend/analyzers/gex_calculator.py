"""
backend/analyzers/gex_calculator.py
Net Gamma Exposure (GEX) Calculator

Calculates total gamma exposure across all option strikes to determine:
- Net GEX (positive = mean reversion, negative = volatility)
- Zero Gamma Level (critical flip point)
- GEX regime classification
- Strike-by-strike gamma exposure

This is what SpotGamma charges $224/month for!
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import numpy as np


class GEXCalculator:
    def __init__(self):
        """Initialize GEX Calculator"""
        self.logger = logging.getLogger(__name__)
        
        # GEX thresholds for classification
        self.regime_thresholds = {
            'EXTREME_POSITIVE': 5_000_000_000,  # $5B+
            'STRONG_POSITIVE': 2_000_000_000,   # $2B+
            'MODERATE_POSITIVE': 500_000_000,   # $500M+
            'NEUTRAL': 100_000_000,             # ±$100M
            'MODERATE_NEGATIVE': -500_000_000,  # -$500M
            'STRONG_NEGATIVE': -2_000_000_000,  # -$2B
            'EXTREME_NEGATIVE': -5_000_000_000  # -$5B
        }
    
    def calculate_strike_gex(self, strike: float, oi: int, delta: float, 
                            gamma: float, stock_price: float, 
                            option_type: str) -> float:
        """
        Calculate GEX for a single strike
        
        Formula: OI × Delta × Gamma × 100 × Stock Price
        
        Dealer perspective:
        - Calls: Dealers SHORT → negative gamma for them → we show as POSITIVE (resistance)
        - Puts: Dealers LONG → positive gamma for them → we show as NEGATIVE (support)
        
        Args:
            strike: Strike price
            oi: Open Interest
            delta: Option delta
            gamma: Option gamma
            stock_price: Current stock price
            option_type: 'call' or 'put'
        
        Returns:
            GEX in dollars (positive or negative)
        """
        if oi == 0 or gamma == 0:
            return 0.0
        
        # Base GEX calculation
        # Multiply by 100 because each contract = 100 shares
        gex = oi * abs(delta) * abs(gamma) * 100 * stock_price
        
        # Apply sign based on option type
        if option_type.lower() == 'call':
            # Calls above price = resistance (positive GEX)
            return gex
        else:  # put
            # Puts below price = support (negative GEX)
            return -gex
    
    def calculate_net_gex(self, symbol: str, options_data: List[Dict], 
                         current_price: float) -> Dict:
        """
        Calculate Net GEX across ALL strikes
        
        Args:
            symbol: Stock symbol
            options_data: List of option contracts with OI, delta, gamma
            current_price: Current stock price
        
        Returns:
            Complete GEX analysis with net GEX, zero gamma level, regime, etc.
        """
        try:
            if not options_data:
                return {
                    'available': False,
                    'error': 'No options data provided'
                }
            
            # Calculate GEX for each strike
            strikes_gex = []
            total_call_gex = 0.0
            total_put_gex = 0.0
            
            for option in options_data:
                strike = float(option.get('strike', 0))
                oi = int(option.get('open_interest', 0))
                option_type = option.get('option_type', '').lower()
                
                if strike <= 0 or oi == 0:
                    continue
                
                # Get greeks (support both nested and top-level)
                greeks = option.get('greeks', {})
                delta = float(greeks.get('delta', 0) if greeks else option.get('delta', 0))
                gamma = float(greeks.get('gamma', 0) if greeks else option.get('gamma', 0))
                
                if gamma == 0:
                    continue
                
                # Calculate GEX for this strike
                strike_gex = self.calculate_strike_gex(
                    strike, oi, delta, gamma, current_price, option_type
                )
                
                # Aggregate by strike (handle both calls and puts at same strike)
                existing = next((s for s in strikes_gex if s['strike'] == strike), None)
                
                if existing:
                    if option_type == 'call':
                        existing['call_oi'] += oi
                        existing['call_gex'] += strike_gex
                    else:
                        existing['put_oi'] += oi
                        existing['put_gex'] += strike_gex
                    existing['net_gex'] = existing['call_gex'] + existing['put_gex']
                else:
                    strikes_gex.append({
                        'strike': strike,
                        'call_oi': oi if option_type == 'call' else 0,
                        'put_oi': oi if option_type == 'put' else 0,
                        'call_gex': strike_gex if option_type == 'call' else 0,
                        'put_gex': strike_gex if option_type == 'put' else 0,
                        'net_gex': strike_gex,
                        'distance_from_price': strike - current_price,
                        'distance_pct': ((strike - current_price) / current_price) * 100
                    })
                
                # Track totals
                if option_type == 'call':
                    total_call_gex += strike_gex
                else:
                    total_put_gex += strike_gex
            
            if not strikes_gex:
                return {
                    'available': False,
                    'error': 'No valid GEX data calculated'
                }
            
            # Sort strikes by price
            strikes_gex.sort(key=lambda x: x['strike'])
            
            # Calculate net GEX
            net_gex = total_call_gex + total_put_gex
            
            # Find zero gamma level (where net GEX crosses zero)
            zero_gamma_level = self._find_zero_gamma_level(strikes_gex, current_price)
            
            # Classify regime
            regime = self._classify_regime(net_gex)
            
            # Determine position relative to zero gamma
            if zero_gamma_level:
                position = 'ABOVE' if current_price > zero_gamma_level else 'BELOW'
                distance_from_zero = current_price - zero_gamma_level
                distance_from_zero_pct = (distance_from_zero / current_price) * 100
            else:
                position = 'UNKNOWN'
                distance_from_zero = 0
                distance_from_zero_pct = 0
            
            # Get top resistance and support levels
            top_resistance = self._get_top_levels(strikes_gex, 'resistance', 3)
            top_support = self._get_top_levels(strikes_gex, 'support', 3)
            
            # Calculate expected range
            expected_range = self._calculate_expected_range(
                strikes_gex, current_price, zero_gamma_level
            )
            
            # Calculate max pain (strike with most OI)
            max_pain = self._calculate_max_pain(strikes_gex)
            
            return {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'current_price': current_price,
                'available': True,
                
                'net_gex': {
                    'total': round(net_gex, 2),
                    'call_gex': round(total_call_gex, 2),
                    'put_gex': round(total_put_gex, 2),
                    'regime': regime,
                    'regime_strength': self._get_regime_strength(net_gex)
                },
                
                'zero_gamma': {
                    'level': round(zero_gamma_level, 2) if zero_gamma_level else None,
                    'position': position,
                    'distance': round(distance_from_zero, 2),
                    'distance_pct': round(distance_from_zero_pct, 2),
                    'approaching': abs(distance_from_zero_pct) < 1.0  # Within 1%
                },
                
                'strikes': strikes_gex,
                
                'top_levels': {
                    'resistance': top_resistance,
                    'support': top_support
                },
                
                'expected_range': expected_range,
                'max_pain': round(max_pain, 2) if max_pain else None,
                
                'summary': self._generate_summary(
                    net_gex, regime, zero_gamma_level, current_price
                )
            }
            
        except Exception as e:
            self.logger.error(f"GEX calculation failed for {symbol}: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return {
                'available': False,
                'error': str(e)
            }
    
    def _find_zero_gamma_level(self, strikes_gex: List[Dict], 
                               current_price: float) -> Optional[float]:
        """
        Find the strike where net GEX crosses from positive to negative
        This is the critical flip point for regime change
        """
        try:
            # Look for sign change in net GEX
            for i in range(len(strikes_gex) - 1):
                current_strike = strikes_gex[i]
                next_strike = strikes_gex[i + 1]
                
                current_gex = current_strike['net_gex']
                next_gex = next_strike['net_gex']
                
                # Check for sign change
                if current_gex * next_gex < 0:  # Different signs
                    # Interpolate between the two strikes
                    strike1 = current_strike['strike']
                    strike2 = next_strike['strike']
                    gex1 = current_gex
                    gex2 = next_gex
                    
                    # Linear interpolation
                    zero_level = strike1 - (gex1 * (strike2 - strike1)) / (gex2 - gex1)
                    return zero_level
            
            # If no crossing found, estimate based on net GEX
            if strikes_gex:
                # Find strike closest to zero GEX
                closest = min(strikes_gex, key=lambda x: abs(x['net_gex']))
                return closest['strike']
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding zero gamma level: {str(e)}")
            return None
    
    def _classify_regime(self, net_gex: float) -> str:
        """Classify GEX regime based on net GEX value"""
        if net_gex >= self.regime_thresholds['EXTREME_POSITIVE']:
            return 'EXTREME_MEAN_REVERSION'
        elif net_gex >= self.regime_thresholds['STRONG_POSITIVE']:
            return 'STRONG_MEAN_REVERSION'
        elif net_gex >= self.regime_thresholds['MODERATE_POSITIVE']:
            return 'MEAN_REVERSION'
        elif abs(net_gex) < self.regime_thresholds['NEUTRAL']:
            return 'NEUTRAL'
        elif net_gex <= self.regime_thresholds['EXTREME_NEGATIVE']:
            return 'EXTREME_VOLATILITY'
        elif net_gex <= self.regime_thresholds['STRONG_NEGATIVE']:
            return 'STRONG_VOLATILITY'
        elif net_gex <= self.regime_thresholds['MODERATE_NEGATIVE']:
            return 'VOLATILITY'
        else:
            return 'NEUTRAL'
    
    def _get_regime_strength(self, net_gex: float) -> str:
        """Get regime strength label"""
        if abs(net_gex) >= 5_000_000_000:
            return 'EXTREME'
        elif abs(net_gex) >= 2_000_000_000:
            return 'STRONG'
        elif abs(net_gex) >= 500_000_000:
            return 'MODERATE'
        else:
            return 'WEAK'
    
    def _get_top_levels(self, strikes_gex: List[Dict], 
                       level_type: str, count: int = 3) -> List[Dict]:
        """Get top resistance or support levels by GEX magnitude"""
        if level_type == 'resistance':
            # Positive GEX (calls above price)
            levels = [s for s in strikes_gex if s['net_gex'] > 0]
            levels.sort(key=lambda x: x['net_gex'], reverse=True)
        else:  # support
            # Negative GEX (puts below price)
            levels = [s for s in strikes_gex if s['net_gex'] < 0]
            levels.sort(key=lambda x: abs(x['net_gex']), reverse=True)
        
        return levels[:count]
    
    def _calculate_expected_range(self, strikes_gex: List[Dict], 
                                  current_price: float,
                                  zero_gamma: Optional[float]) -> Dict:
        """Calculate expected price range based on GEX"""
        try:
            # Get top resistance and support
            resistance_levels = [s for s in strikes_gex if s['net_gex'] > 0]
            support_levels = [s for s in strikes_gex if s['net_gex'] < 0]
            
            if resistance_levels:
                resistance_levels.sort(key=lambda x: x['net_gex'], reverse=True)
                expected_high = resistance_levels[0]['strike']
            else:
                expected_high = current_price * 1.02
            
            if support_levels:
                support_levels.sort(key=lambda x: abs(x['net_gex']), reverse=True)
                expected_low = support_levels[0]['strike']
            else:
                expected_low = current_price * 0.98
            
            expected_mid = (expected_high + expected_low) / 2
            range_width = expected_high - expected_low
            range_width_pct = (range_width / current_price) * 100
            
            return {
                'low': round(expected_low, 2),
                'high': round(expected_high, 2),
                'midpoint': round(expected_mid, 2),
                'width': round(range_width, 2),
                'width_pct': round(range_width_pct, 2)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating expected range: {str(e)}")
            return {}
    
    def _calculate_max_pain(self, strikes_gex: List[Dict]) -> Optional[float]:
        """
        Calculate max pain (strike with highest total OI)
        This is where option sellers make the most money
        """
        try:
            if not strikes_gex:
                return None
            
            # Find strike with highest total OI
            max_oi_strike = max(
                strikes_gex,
                key=lambda x: x['call_oi'] + x['put_oi']
            )
            
            return max_oi_strike['strike']
            
        except Exception as e:
            self.logger.error(f"Error calculating max pain: {str(e)}")
            return None
    
    def _generate_summary(self, net_gex: float, regime: str,
                         zero_gamma: Optional[float], 
                         current_price: float) -> str:
        """Generate human-readable summary of GEX situation"""
        try:
            gex_billions = net_gex / 1_000_000_000
            
            if 'MEAN_REVERSION' in regime:
                direction = "upward" if current_price < zero_gamma else "downward"
                summary = (
                    f"Net GEX: ${gex_billions:+.2f}B (POSITIVE). "
                    f"Mean reversion regime active. "
                    f"Dealers will resist moves and push price back toward {direction} levels. "
                )
                if zero_gamma:
                    summary += f"Zero gamma at ${zero_gamma:.2f}. "
            elif 'VOLATILITY' in regime:
                summary = (
                    f"Net GEX: ${gex_billions:+.2f}B (NEGATIVE). "
                    f"Volatility regime active. "
                    f"Dealers will amplify moves - breakouts more likely. "
                )
                if zero_gamma:
                    summary += f"Zero gamma at ${zero_gamma:.2f}. "
            else:
                summary = f"Net GEX: ${gex_billions:+.2f}B. Neutral regime."
            
            return summary
            
        except Exception as e:
            return "GEX summary unavailable"


# Testing function
if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Create sample options data for testing
    sample_options = [
        {
            'strike': 420,
            'open_interest': 10000,
            'option_type': 'call',
            'greeks': {'delta': 0.5, 'gamma': 0.015}
        },
        {
            'strike': 420,
            'open_interest': 8000,
            'option_type': 'put',
            'greeks': {'delta': -0.5, 'gamma': 0.015}
        },
        {
            'strike': 425,
            'open_interest': 15000,
            'option_type': 'call',
            'greeks': {'delta': 0.3, 'gamma': 0.012}
        },
        {
            'strike': 415,
            'open_interest': 12000,
            'option_type': 'put',
            'greeks': {'delta': -0.3, 'gamma': 0.012}
        }
    ]
    
    calculator = GEXCalculator()
    result = calculator.calculate_net_gex('SPY', sample_options, 420.45)
    
    print("=" * 60)
    print("GEX CALCULATOR TEST")
    print("=" * 60)
    print(f"\nSymbol: {result['symbol']}")
    print(f"Current Price: ${result['current_price']:.2f}")
    print(f"\nNet GEX: ${result['net_gex']['total']:,.0f}")
    print(f"  Call GEX: ${result['net_gex']['call_gex']:,.0f}")
    print(f"  Put GEX: ${result['net_gex']['put_gex']:,.0f}")
    print(f"  Regime: {result['net_gex']['regime']}")
    print(f"\nZero Gamma Level: ${result['zero_gamma']['level']:.2f}")
    print(f"Position: {result['zero_gamma']['position']}")
    print(f"\nSummary: {result['summary']}")
    print("=" * 60)
