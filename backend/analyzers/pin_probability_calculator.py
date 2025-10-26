"""
backend/analyzers/pin_probability_calculator.py
0DTE Pin Probability Calculator

Calculates:
- Max Pain (strike with most total OI)
- Pin Probability (likelihood price closes at max pain)
- Expected pin range
- Time decay factor

For 6-figure day trader - optimized for speed
"""

import logging
from typing import Dict, Optional
from datetime import datetime, time
import pytz


class PinProbabilityCalculator:
    def __init__(self):
        """Initialize Pin Probability Calculator"""
        self.logger = logging.getLogger(__name__)
        
        # Pin probability factors
        self.time_decay_factor = {
            'morning': 0.3,      # 9:30-12:00 (low pin probability)
            'midday': 0.5,       # 12:00-14:00 (medium)
            'power_hour': 0.8,   # 14:00-15:00 (high)
            'final_hour': 0.95   # 15:00-16:00 (very high)
        }
        
        self.logger.info("✅ Pin Probability Calculator initialized")
    
    def calculate_max_pain(self, options_data: list) -> Optional[float]:
        """
        Calculate Max Pain - strike where option sellers make most money
        
        Args:
            options_data: List of option contracts with OI
        
        Returns:
            Max pain strike price
        """
        try:
            if not options_data:
                return None
            
            # Aggregate OI by strike
            strike_oi = {}
            
            for option in options_data:
                strike = float(option.get('strike', 0))
                oi = int(option.get('open_interest', 0))
                
                if strike <= 0 or oi <= 0:
                    continue
                
                if strike not in strike_oi:
                    strike_oi[strike] = {'call_oi': 0, 'put_oi': 0}
                
                option_type = option.get('option_type', '').lower()
                if option_type == 'call':
                    strike_oi[strike]['call_oi'] += oi
                else:
                    strike_oi[strike]['put_oi'] += oi
            
            if not strike_oi:
                return None
            
            # Calculate pain at each strike
            pain_by_strike = {}
            
            for test_strike in strike_oi.keys():
                total_pain = 0
                
                # Pain for call sellers
                for strike, oi in strike_oi.items():
                    if test_strike > strike:
                        # Calls are ITM - sellers lose
                        total_pain += oi['call_oi'] * (test_strike - strike) * 100
                
                # Pain for put sellers
                for strike, oi in strike_oi.items():
                    if test_strike < strike:
                        # Puts are ITM - sellers lose
                        total_pain += oi['put_oi'] * (strike - test_strike) * 100
                
                pain_by_strike[test_strike] = total_pain
            
            # Max pain = strike with MINIMUM total pain (best for sellers)
            max_pain_strike = min(pain_by_strike.items(), key=lambda x: x[1])[0]
            
            self.logger.debug(f"Max Pain calculated: ${max_pain_strike:.2f}")
            
            return max_pain_strike
            
        except Exception as e:
            self.logger.error(f"Error calculating max pain: {str(e)}")
            return None
    
    def get_time_period(self) -> str:
        """Get current time period for pin probability"""
        try:
            et_tz = pytz.timezone('America/New_York')
            now = datetime.now(et_tz)
            current_time = now.time()
            
            if time(9, 30) <= current_time < time(12, 0):
                return 'morning'
            elif time(12, 0) <= current_time < time(14, 0):
                return 'midday'
            elif time(14, 0) <= current_time < time(15, 0):
                return 'power_hour'
            elif time(15, 0) <= current_time < time(16, 0):
                return 'final_hour'
            else:
                return 'after_hours'
        except:
            return 'morning'
    
    def calculate_hours_until_expiry(self, expiration_date: str) -> float:
        """
        Calculate hours until expiration
        
        Args:
            expiration_date: Date string (YYYY-MM-DD or YYYYMMDD)
        
        Returns:
            Hours until 4:00 PM ET on expiration date
        """
        try:
            et_tz = pytz.timezone('America/New_York')
            now = datetime.now(et_tz)
            
            # Parse expiration date
            if '-' in expiration_date:
                exp_date = datetime.strptime(expiration_date, '%Y-%m-%d')
            else:
                exp_date = datetime.strptime(expiration_date, '%Y%m%d')
            
            # Set expiration to 4:00 PM ET
            expiry = et_tz.localize(exp_date.replace(hour=16, minute=0, second=0))
            
            # Calculate hours
            delta = expiry - now
            hours = delta.total_seconds() / 3600
            
            return max(hours, 0)
            
        except Exception as e:
            self.logger.error(f"Error calculating hours until expiry: {str(e)}")
            return 0
    
    def calculate_pin_probability(self, symbol: str, current_price: float,
                                  max_pain: float, total_gamma: float,
                                  hours_until_expiry: float) -> Dict:
        """
        Calculate pin probability based on multiple factors
        
        Args:
            symbol: Stock symbol
            current_price: Current stock price
            max_pain: Max pain strike
            total_gamma: Total gamma exposure at max pain
            hours_until_expiry: Hours until expiration
        
        Returns:
            Pin analysis dict
        """
        try:
            # Distance from max pain
            distance_dollars = abs(current_price - max_pain)
            distance_pct = (distance_dollars / current_price) * 100
            
            # Base probability from distance (closer = higher probability)
            if distance_pct <= 0.5:
                base_probability = 0.85
            elif distance_pct <= 1.0:
                base_probability = 0.70
            elif distance_pct <= 1.5:
                base_probability = 0.55
            elif distance_pct <= 2.0:
                base_probability = 0.40
            else:
                base_probability = 0.25
            
            # Time decay factor (closer to expiry = higher probability)
            time_period = self.get_time_period()
            time_factor = self.time_decay_factor.get(time_period, 0.5)
            
            # Gamma strength factor (higher gamma = stronger pin)
            if abs(total_gamma) > 5_000_000_000:  # $5B+
                gamma_factor = 1.2
            elif abs(total_gamma) > 2_000_000_000:  # $2B+
                gamma_factor = 1.1
            elif abs(total_gamma) > 1_000_000_000:  # $1B+
                gamma_factor = 1.0
            else:
                gamma_factor = 0.9
            
            # Calculate final probability
            pin_probability = base_probability * time_factor * gamma_factor
            pin_probability = min(pin_probability, 0.99)  # Cap at 99%
            
            # Calculate expected pin range (tighter as expiry approaches)
            if hours_until_expiry < 1:
                range_pct = 0.25  # ±0.25%
            elif hours_until_expiry < 2:
                range_pct = 0.5   # ±0.5%
            elif hours_until_expiry < 4:
                range_pct = 0.75  # ±0.75%
            else:
                range_pct = 1.0   # ±1.0%
            
            range_dollars = max_pain * (range_pct / 100)
            pin_range_low = max_pain - range_dollars
            pin_range_high = max_pain + range_dollars
            
            # Determine if 0DTE
            is_odte = hours_until_expiry < 8
            
            # Generate interpretation
            if pin_probability >= 0.75:
                strength = "VERY HIGH"
                action = f"Expect strong pin to ${max_pain:.2f}"
            elif pin_probability >= 0.60:
                strength = "HIGH"
                action = f"Likely gravitates toward ${max_pain:.2f}"
            elif pin_probability >= 0.45:
                strength = "MODERATE"
                action = f"May drift toward ${max_pain:.2f}"
            else:
                strength = "LOW"
                action = f"Weak pin effect to ${max_pain:.2f}"
            
            return {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'available': True,
                'is_odte': is_odte,
                'current_price': round(current_price, 2),
                'max_pain': round(max_pain, 2),
                'distance_from_max_pain': {
                    'dollars': round(distance_dollars, 2),
                    'percent': round(distance_pct, 2),
                    'direction': 'above' if current_price > max_pain else 'below'
                },
                'pin_probability': {
                    'percent': round(pin_probability * 100, 1),
                    'strength': strength,
                    'factors': {
                        'base': round(base_probability * 100, 1),
                        'time_decay': round(time_factor * 100, 1),
                        'gamma_strength': round(gamma_factor * 100, 1)
                    }
                },
                'pin_range': {
                    'low': round(pin_range_low, 2),
                    'high': round(pin_range_high, 2),
                    'width': round(range_dollars * 2, 2),
                    'width_pct': round(range_pct * 2, 2)
                },
                'time_analysis': {
                    'hours_until_expiry': round(hours_until_expiry, 1),
                    'time_period': time_period,
                    'time_factor': round(time_factor * 100, 1)
                },
                'gamma_analysis': {
                    'total_gamma': round(total_gamma, 2),
                    'gamma_factor': round(gamma_factor * 100, 1)
                },
                'interpretation': action,
                'trading_action': self._generate_trading_action(
                    current_price, max_pain, pin_probability, hours_until_expiry
                )
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating pin probability: {str(e)}")
            return {
                'symbol': symbol,
                'available': False,
                'error': str(e)
            }
    
    def _generate_trading_action(self, current_price: float, max_pain: float,
                                pin_probability: float, hours_until_expiry: float) -> str:
        """Generate actionable trading advice"""
        
        distance_pct = abs((current_price - max_pain) / current_price) * 100
        
        if pin_probability >= 0.75:
            if hours_until_expiry < 2:
                if current_price > max_pain:
                    return f"FADE: Sell rallies toward ${max_pain:.2f} (strong pin likely)"
                else:
                    return f"BUY DIPS: Buy weakness toward ${max_pain:.2f} (strong pin likely)"
            else:
                return f"RANGE TRADE: Expect price to gravitate toward ${max_pain:.2f}"
        
        elif pin_probability >= 0.60:
            if distance_pct > 1.5:
                return f"WATCH: Monitor for move toward ${max_pain:.2f} (moderate pin)"
            else:
                return f"CONSOLIDATION: Expect range around ${max_pain:.2f}"
        
        else:
            return f"LOW PIN: Other factors may dominate (weak gravitational pull)"
    
    def analyze_pin_probability(self, symbol: str, current_price: float,
                                options_data: list, gamma_data: Dict,
                                expiration_date: str) -> Dict:
        """
        Main analysis method - combines all calculations
        
        Args:
            symbol: Stock symbol
            current_price: Current stock price
            options_data: List of option contracts
            gamma_data: GEX analysis from gex_calculator
            expiration_date: Expiration date string
        
        Returns:
            Complete pin probability analysis
        """
        try:
            # Calculate max pain
            max_pain = self.calculate_max_pain(options_data)
            
            if not max_pain:
                return {
                    'symbol': symbol,
                    'available': False,
                    'reason': 'Unable to calculate max pain'
                }
            
            # Get hours until expiry
            hours_until_expiry = self.calculate_hours_until_expiry(expiration_date)
            
            # Get total gamma from gamma_data
            total_gamma = gamma_data.get('net_gex', {}).get('total', 0)
            
            # Calculate pin probability
            result = self.calculate_pin_probability(
                symbol,
                current_price,
                max_pain,
                total_gamma,
                hours_until_expiry
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error analyzing pin probability: {str(e)}")
            return {
                'symbol': symbol,
                'available': False,
                'error': str(e)
            }


# Testing
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Sample test
    calculator = PinProbabilityCalculator()
    
    sample_options = [
        {'strike': 420, 'open_interest': 10000, 'option_type': 'call'},
        {'strike': 420, 'open_interest': 8000, 'option_type': 'put'},
        {'strike': 425, 'open_interest': 15000, 'option_type': 'call'},
        {'strike': 415, 'open_interest': 12000, 'option_type': 'put'},
    ]
    
    max_pain = calculator.calculate_max_pain(sample_options)
    print(f"Max Pain: ${max_pain}")
    
    sample_gamma = {'net_gex': {'total': 2_300_000_000}}
    
    result = calculator.analyze_pin_probability(
        'SPY',
        420.45,
        sample_options,
        sample_gamma,
        '2025-10-28'
    )
    
    print(f"\nPin Probability: {result['pin_probability']['percent']}%")
    print(f"Pin Range: ${result['pin_range']['low']:.2f} - ${result['pin_range']['high']:.2f}")
    print(f"Action: {result['trading_action']}")
