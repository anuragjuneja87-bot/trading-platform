"""
backend/analyzers/key_level_detector.py
Key Level Detector - Advanced Support/Resistance Detection
Includes confluence scoring and multi-source level detection
"""

import requests
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging


class KeyLevelDetector:
    def __init__(self, api_key: str):
        """
        Initialize Key Level Detector
        
        Args:
            api_key: Polygon.io API key
        """
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.proximity_threshold = 0.005  # 0.5% proximity to level
        self.confluence_weights = {
            'previous_day_high': 3,
            'previous_day_low': 3,
            'previous_close': 2,
            'vwap': 2,
            'vwap_1sd': 2,
            'vwap_2sd': 3,
            'premarket_high': 2,
            'premarket_low': 2,
            'psychological': 2,
            'pivot': 1
        }
        
        # Cache
        self.cache = {}
        self.cache_duration = 60
    
    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make Polygon API request"""
        if params is None:
            params = {}
        
        params['apiKey'] = self.api_key
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {str(e)}")
            return {}
    
    def get_previous_day_levels(self, symbol: str) -> Dict:
        """
        Get previous day's key levels
        Most important for intraday trading
        
        Returns:
            high, low, close, open from previous trading day
        """
        try:
            # Get previous trading day
            test_date = datetime.now() - timedelta(days=1)
            while test_date.weekday() >= 5:  # Skip weekends
                test_date -= timedelta(days=1)
            yesterday = test_date.strftime('%Y-%m-%d')
            
            endpoint = f"/v2/aggs/ticker/{symbol}/range/1/day/{yesterday}/{yesterday}"
            data = self._make_request(endpoint, {'adjusted': 'true'})
            
            if 'results' not in data or not data['results']:
                return {}
            
            prev = data['results'][0]
            
            return {
                'previous_day_high': round(prev['h'], 2),
                'previous_day_low': round(prev['l'], 2),
                'previous_close': round(prev['c'], 2),
                'previous_open': round(prev['o'], 2),
                'previous_volume': prev['v']
            }
            
        except Exception as e:
            self.logger.error(f"Error getting previous day levels for {symbol}: {str(e)}")
            return {}
    
    def get_premarket_levels(self, symbol: str) -> Dict:
        """
        Get premarket high and low
        Critical for first hour trading
        
        Returns:
            premarket_high, premarket_low
        """
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            endpoint = f"/v2/aggs/ticker/{symbol}/range/1/minute/{today}/{today}"
            
            data = self._make_request(endpoint, {
                'adjusted': 'true',
                'sort': 'asc',
                'limit': 50000
            })
            
            if 'results' not in data or not data['results']:
                return {}
            
            df = pd.DataFrame(data['results'])
            df['timestamp'] = pd.to_datetime(df['t'], unit='ms')
            df['hour'] = df['timestamp'].dt.hour
            df['minute'] = df['timestamp'].dt.minute
            
            # Premarket: 4:00 AM - 9:30 AM
            premarket = df[
                (df['hour'] >= 4) &
                ((df['hour'] < 9) | ((df['hour'] == 9) & (df['minute'] < 30)))
            ]
            
            if len(premarket) == 0:
                return {}
            
            return {
                'premarket_high': round(premarket['h'].max(), 2),
                'premarket_low': round(premarket['l'].min(), 2),
                'premarket_open': round(premarket.iloc[0]['o'], 2),
                'premarket_close': round(premarket.iloc[-1]['c'], 2),
                'premarket_volume': int(premarket['v'].sum())
            }
            
        except Exception as e:
            self.logger.error(f"Error getting premarket levels for {symbol}: {str(e)}")
            return {}
    
    def calculate_vwap_bands(self, symbol: str) -> Dict:
        """
        Calculate VWAP with standard deviation bands
        1σ, 2σ bands act as support/resistance
        
        Returns:
            vwap, vwap_upper_1sd, vwap_lower_1sd, vwap_upper_2sd, vwap_lower_2sd
        """
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            endpoint = f"/v2/aggs/ticker/{symbol}/range/1/minute/{today}/{today}"
            
            data = self._make_request(endpoint, {
                'adjusted': 'true',
                'sort': 'asc',
                'limit': 50000
            })
            
            if 'results' not in data or not data['results']:
                return {}
            
            df = pd.DataFrame(data['results'])
            
            # Calculate VWAP
            df['vwap'] = (df['c'] * df['v']).cumsum() / df['v'].cumsum()
            
            # Calculate typical price for standard deviation
            df['typical_price'] = (df['h'] + df['l'] + df['c']) / 3
            
            # Calculate cumulative standard deviation
            df['cum_volume'] = df['v'].cumsum()
            df['cum_tp_volume'] = (df['typical_price'] * df['v']).cumsum()
            df['cum_tp_sq_volume'] = (df['typical_price']**2 * df['v']).cumsum()
            
            # Variance calculation
            variance = (df['cum_tp_sq_volume'] / df['cum_volume']) - (df['cum_tp_volume'] / df['cum_volume'])**2
            std_dev = np.sqrt(variance.abs())
            
            current_vwap = df['vwap'].iloc[-1]
            current_std = std_dev.iloc[-1]
            
            return {
                'vwap': round(current_vwap, 2),
                'vwap_upper_1sd': round(current_vwap + current_std, 2),
                'vwap_lower_1sd': round(current_vwap - current_std, 2),
                'vwap_upper_2sd': round(current_vwap + (2 * current_std), 2),
                'vwap_lower_2sd': round(current_vwap - (2 * current_std), 2),
                'vwap_upper_3sd': round(current_vwap + (3 * current_std), 2),
                'vwap_lower_3sd': round(current_vwap - (3 * current_std), 2),
                'std_dev': round(current_std, 2)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating VWAP bands for {symbol}: {str(e)}")
            return {}
    
    def get_anchored_vwap(self, symbol: str, anchor_date: str) -> float:
        """
        Calculate VWAP anchored from a specific date
        Useful for earnings, gaps, major news
        
        Args:
            symbol: Stock symbol
            anchor_date: Date to anchor from (YYYY-MM-DD)
        
        Returns:
            Anchored VWAP value
        """
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            endpoint = f"/v2/aggs/ticker/{symbol}/range/1/minute/{anchor_date}/{today}"
            
            data = self._make_request(endpoint, {
                'adjusted': 'true',
                'sort': 'asc',
                'limit': 50000
            })
            
            if 'results' not in data or not data['results']:
                return 0.0
            
            df = pd.DataFrame(data['results'])
            
            # Calculate anchored VWAP
            total_pv = (df['c'] * df['v']).sum()
            total_v = df['v'].sum()
            
            anchored_vwap = total_pv / total_v if total_v > 0 else 0.0
            
            return round(anchored_vwap, 2)
            
        except Exception as e:
            self.logger.error(f"Error calculating anchored VWAP: {str(e)}")
            return 0.0
    
    def get_psychological_levels(self, current_price: float, symbol: str) -> List[float]:
        """
        Get nearby psychological price levels
        Round numbers: $50, $100, $150, $180, $200, etc.
        
        Args:
            current_price: Current stock price
            symbol: Stock symbol (for logging)
        
        Returns:
            List of nearby psychological levels
        """
        levels = []
        
        # Determine increment based on price
        if current_price < 10:
            increment = 1  # $1, $2, $3, etc.
        elif current_price < 50:
            increment = 5  # $5, $10, $15, etc.
        elif current_price < 200:
            increment = 10  # $10, $20, $30, etc.
        else:
            increment = 25  # $25, $50, $75, etc.
        
        # Find closest levels above and below
        lower = (current_price // increment) * increment
        upper = lower + increment
        
        # Add levels within range
        for level in [lower - increment, lower, upper, upper + increment]:
            if level > 0 and abs(level - current_price) / current_price <= 0.05:  # Within 5%
                levels.append(round(level, 2))
        
        return sorted(levels)
    
    def calculate_pivot_points(self, symbol: str) -> Dict:
        """
        Calculate classic pivot points from previous day
        
        Returns:
            R3, R2, R1, PP, S1, S2, S3
        """
        try:
            prev_levels = self.get_previous_day_levels(symbol)
            
            if not prev_levels:
                return {}
            
            high = prev_levels['previous_day_high']
            low = prev_levels['previous_day_low']
            close = prev_levels['previous_close']
            
            # Classic Pivot Point
            pp = (high + low + close) / 3
            
            # Resistance levels
            r1 = (2 * pp) - low
            r2 = pp + (high - low)
            r3 = high + 2 * (pp - low)
            
            # Support levels
            s1 = (2 * pp) - high
            s2 = pp - (high - low)
            s3 = low - 2 * (high - pp)
            
            return {
                'pivot': round(pp, 2),
                'r1': round(r1, 2),
                'r2': round(r2, 2),
                'r3': round(r3, 2),
                's1': round(s1, 2),
                's2': round(s2, 2),
                's3': round(s3, 2)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating pivot points: {str(e)}")
            return {}
    
    def is_near_level(self, current_price: float, level: float, threshold: float = None) -> bool:
        """
        Check if current price is near a key level
        
        Args:
            current_price: Current stock price
            level: Key level to check
            threshold: Proximity threshold (default: 0.5%)
        
        Returns:
            Boolean indicating if price is near level
        """
        if threshold is None:
            threshold = self.proximity_threshold
        
        if level == 0:
            return False
        
        distance = abs(current_price - level) / level
        return distance <= threshold
    
    def calculate_confluence_score(self, current_price: float, all_levels: Dict) -> Tuple[int, List[str]]:
        """
        Calculate confluence score for current price
        Higher score = more significant level
        
        Args:
            current_price: Current stock price
            all_levels: Dictionary of all detected levels
        
        Returns:
            Tuple of (confluence_score, list of confluent levels)
        """
        score = 0
        confluent_levels = []
        
        for level_type, level_value in all_levels.items():
            if isinstance(level_value, (int, float)) and level_value > 0:
                if self.is_near_level(current_price, level_value):
                    weight = self.confluence_weights.get(level_type, 1)
                    score += weight
                    confluent_levels.append(f"{level_type}: ${level_value:.2f}")
        
        return score, confluent_levels
    
    def detect_key_levels(self, symbol: str, current_price: float) -> Dict:
        """
        Complete key level detection for a symbol
        
        Args:
            symbol: Stock symbol
            current_price: Current stock price
        
        Returns:
            Dictionary with all key levels and confluence analysis
        """
        try:
            self.logger.debug(f"Detecting key levels for {symbol} @ ${current_price:.2f}...")
            
            # Get all levels
            prev_day = self.get_previous_day_levels(symbol)
            premarket = self.get_premarket_levels(symbol)
            vwap_bands = self.calculate_vwap_bands(symbol)
            pivots = self.calculate_pivot_points(symbol)
            psychological = self.get_psychological_levels(current_price, symbol)
            
            # Combine all levels
            all_levels = {**prev_day, **premarket, **vwap_bands, **pivots}
            
            # Calculate confluence at current price
            confluence_score, confluent_levels = self.calculate_confluence_score(
                current_price, all_levels
            )
            
            # Determine if at resistance or support
            at_resistance = False
            at_support = False
            
            resistance_levels = [
                prev_day.get('previous_day_high'),
                prev_day.get('previous_close') if prev_day.get('previous_close', 0) > current_price else None,
                premarket.get('premarket_high'),
                vwap_bands.get('vwap_upper_1sd'),
                vwap_bands.get('vwap_upper_2sd')
            ]
            
            support_levels = [
                prev_day.get('previous_day_low'),
                prev_day.get('previous_close') if prev_day.get('previous_close', 0) < current_price else None,
                premarket.get('premarket_low'),
                vwap_bands.get('vwap_lower_1sd'),
                vwap_bands.get('vwap_lower_2sd')
            ]
            
            for level in resistance_levels:
                if level and self.is_near_level(current_price, level):
                    at_resistance = True
                    break
            
            for level in support_levels:
                if level and self.is_near_level(current_price, level):
                    at_support = True
                    break
            
            # Find nearest levels above and below
            all_level_values = [v for v in all_levels.values() if isinstance(v, (int, float)) and v > 0]
            
            above = [l for l in all_level_values if l > current_price]
            below = [l for l in all_level_values if l < current_price]
            
            nearest_resistance = min(above) if above else None
            nearest_support = max(below) if below else None
            
            return {
                'symbol': symbol,
                'current_price': current_price,
                'previous_day': prev_day,
                'premarket': premarket,
                'vwap_bands': vwap_bands,
                'pivots': pivots,
                'psychological_levels': psychological,
                'confluence_score': confluence_score,
                'confluent_levels': confluent_levels,
                'at_resistance': at_resistance,
                'at_support': at_support,
                'nearest_resistance': nearest_resistance,
                'nearest_support': nearest_support,
                'distance_to_resistance': round((nearest_resistance - current_price) / current_price * 100, 2) if nearest_resistance else None,
                'distance_to_support': round((current_price - nearest_support) / current_price * 100, 2) if nearest_support else None
            }
            
        except Exception as e:
            self.logger.error(f"Error detecting key levels for {symbol}: {str(e)}")
            return {'error': str(e)}


# CLI Testing
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    API_KEY = os.getenv('POLYGON_API_KEY')
    if not API_KEY:
        print("❌ Error: POLYGON_API_KEY not found")
        exit(1)
    
    detector = KeyLevelDetector(api_key=API_KEY)
    
    # Test with PLTR (you can change this)
    print("=" * 80)
    print("KEY LEVEL DETECTION - PLTR")
    print("=" * 80)
    
    # First get current price
    endpoint = f"https://api.polygon.io/v2/last/trade/PLTR"
    params = {'apiKey': API_KEY}
    response = requests.get(endpoint, params=params)
    current_price = response.json()['results']['p']
    
    result = detector.detect_key_levels('PLTR', current_price)
    
    if 'error' in result:
        print(f"❌ Error: {result['error']}")
    else:
        print(f"\n💰 Current Price: ${result['current_price']:.2f}")
        print(f"🎯 Confluence Score: {result['confluence_score']}/10")
        
        if result['confluent_levels']:
            print(f"\n📍 Confluent Levels at Current Price:")
            for level in result['confluent_levels']:
                print(f"  • {level}")
        
        print(f"\n📊 Previous Day Levels:")
        prev = result['previous_day']
        print(f"  • High: ${prev.get('previous_day_high', 0):.2f}")
        print(f"  • Low: ${prev.get('previous_day_low', 0):.2f}")
        print(f"  • Close: ${prev.get('previous_close', 0):.2f}")
        
        if result['premarket']:
            print(f"\n🌅 Premarket Levels:")
            pm = result['premarket']
            print(f"  • High: ${pm.get('premarket_high', 0):.2f}")
            print(f"  • Low: ${pm.get('premarket_low', 0):.2f}")
        
        print(f"\n📈 VWAP Bands:")
        vwap = result['vwap_bands']
        print(f"  • VWAP: ${vwap.get('vwap', 0):.2f}")
        print(f"  • +1σ: ${vwap.get('vwap_upper_1sd', 0):.2f}")
        print(f"  • -1σ: ${vwap.get('vwap_lower_1sd', 0):.2f}")
        print(f"  • +2σ: ${vwap.get('vwap_upper_2sd', 0):.2f}")
        print(f"  • -2σ: ${vwap.get('vwap_lower_2sd', 0):.2f}")
        
        print(f"\n🎯 Position Analysis:")
        print(f"  • At Resistance: {'YES ⚠️' if result['at_resistance'] else 'NO'}")
        print(f"  • At Support: {'YES ⚠️' if result['at_support'] else 'NO'}")
        
        if result['nearest_resistance']:
            print(f"  • Next Resistance: ${result['nearest_resistance']:.2f} ({result['distance_to_resistance']:.2f}% away)")
        if result['nearest_support']:
            print(f"  • Next Support: ${result['nearest_support']:.2f} ({result['distance_to_support']:.2f}% away)")
    
    print("\n" + "=" * 80)
