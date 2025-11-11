"""
Opening Range & First Hour Analyzer
Optimized for 9:30-11:30 AM trading window
Catches moves even WITHOUT news - pure price action
"""

import requests
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import Dict, List
import logging

class OpeningRangeAnalyzer:
    def __init__(self, api_key: str):
        """
        Initialize Opening Range Analyzer
        Focuses on first 5-15 minutes for directional bias
        """
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"
        self.logger = logging.getLogger(__name__)
        
        # Track opening range for each symbol
        self.opening_ranges = {}
        self.previous_day_levels = {}
    
    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make API request"""
        if params is None:
            params = {}
        params['apiKey'] = self.api_key
        
        try:
            response = requests.get(f"{self.base_url}{endpoint}", params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"API error: {str(e)}")
            return {}
    
    def get_previous_day_levels(self, symbol: str) -> Dict:
        """
        Get critical levels from previous day
        These become key support/resistance for today
        """
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Skip weekends
        test_date = datetime.now() - timedelta(days=1)
        while test_date.weekday() >= 5:
            test_date -= timedelta(days=1)
        yesterday = test_date.strftime('%Y-%m-%d')
        
        endpoint = f"/v2/aggs/ticker/{symbol}/range/1/day/{yesterday}/{yesterday}"
        data = self._make_request(endpoint, {'adjusted': 'true'})
        
        if 'results' not in data or not data['results']:
            return {}
        
        prev = data['results'][0]
        
        levels = {
            'prev_close': prev['c'],
            'prev_high': prev['h'],
            'prev_low': prev['l'],
            'prev_open': prev['o'],
            'prev_volume': prev['v']
        }
        
        self.previous_day_levels[symbol] = levels
        return levels
    
    def analyze_opening_range(self, symbol: str, range_minutes: int = 5) -> Dict:
        """
        Analyze first 5-15 minutes of trading
        This sets the tone for the day
        
        Args:
            symbol: Stock symbol
            range_minutes: Minutes to analyze (5, 10, or 15)
        
        Returns:
            Opening range analysis with direction and strength
        """
        today = datetime.now().strftime('%Y-%m-%d')
        endpoint = f"/v2/aggs/ticker/{symbol}/range/1/minute/{today}/{today}"
        
        data = self._make_request(endpoint, {
            'adjusted': 'true',
            'sort': 'asc',
            'limit': 50000
        })
        
        if 'results' not in data or not data['results']:
            return {
                'status': 'NO_DATA',
                'direction': 'UNKNOWN'
            }
        
        df = pd.DataFrame(data['results'])
        df['timestamp'] = pd.to_datetime(df['t'], unit='ms')
        
        # Filter for market open (9:30 AM ET onwards)
        df['hour'] = df['timestamp'].dt.hour
        df['minute'] = df['timestamp'].dt.minute
        
        market_open_df = df[
            ((df['hour'] == 9) & (df['minute'] >= 30)) |
            (df['hour'] > 9)
        ].copy()
        
        if len(market_open_df) == 0:
            return {
                'status': 'PRE_MARKET',
                'direction': 'UNKNOWN'
            }
        
        # Get first N minutes
        opening_bars = market_open_df.head(range_minutes)
        
        if len(opening_bars) < range_minutes:
            return {
                'status': 'INCOMPLETE',
                'direction': 'UNKNOWN',
                'bars_available': len(opening_bars)
            }
        
        # Calculate opening range
        or_high = opening_bars['h'].max()
        or_low = opening_bars['l'].min()
        or_open = opening_bars.iloc[0]['o']
        or_close = opening_bars.iloc[-1]['c']
        or_range = or_high - or_low
        
        # Determine direction (AGGRESSIVE thresholds for 7-figure scalping)
        price_change = ((or_close - or_open) / or_open) * 100
        
        if price_change > 0.2:  # LOWERED from 0.3% to 0.2%
            direction = 'BULLISH'
            strength = 'STRONG' if price_change > 0.5 else 'MODERATE'  # LOWERED from 0.8% to 0.5%
        elif price_change < -0.2:  # LOWERED from -0.3% to -0.2%
            direction = 'BEARISH'
            strength = 'STRONG' if price_change < -0.5 else 'MODERATE'  # LOWERED from -0.8% to -0.5%
        else:
            direction = 'NEUTRAL'
            strength = 'WEAK'
        
        # Volume analysis
        total_volume = opening_bars['v'].sum()
        avg_volume_per_min = total_volume / range_minutes
        
        # Get previous day for comparison
        prev_levels = self.get_previous_day_levels(symbol)
        prev_avg_volume = prev_levels.get('prev_volume', 0) / 390 if prev_levels else 0  # 390 minutes in trading day
        
        volume_ratio = avg_volume_per_min / prev_avg_volume if prev_avg_volume > 0 else 1.0
        high_volume = volume_ratio > 1.3  # LOWERED from 1.5x to 1.3x for aggressive detection
        
        # Check if broke/held previous day levels
        prev_close = prev_levels.get('prev_close', or_open)
        prev_high = prev_levels.get('prev_high', or_high)
        prev_low = prev_levels.get('prev_low', or_low)
        
        breakout = None
        if or_high > prev_high:
            breakout = 'BROKE_RESISTANCE'
        elif or_low < prev_low:
            breakout = 'BROKE_SUPPORT'
        elif or_close > prev_close * 1.01:
            breakout = 'GAP_HOLD'
        elif or_close < prev_close * 0.99:
            breakout = 'GAP_FILL'
        
        analysis = {
            'status': 'COMPLETE',
            'direction': direction,
            'strength': strength,
            'or_high': round(or_high, 2),
            'or_low': round(or_low, 2),
            'or_range': round(or_range, 2),
            'or_open': round(or_open, 2),
            'or_close': round(or_close, 2),
            'price_change_pct': round(price_change, 2),
            'volume_ratio': round(volume_ratio, 2),
            'high_volume': high_volume,
            'breakout': breakout,
            'prev_close': round(prev_close, 2),
            'at_resistance': or_close >= prev_close * 0.999 and or_close <= prev_close * 1.001,
            'minutes_analyzed': range_minutes
        }
        
        self.opening_ranges[symbol] = analysis
        return analysis
    
    def detect_opening_range_breakdown(self, symbol: str) -> Dict:
        """
        Detect if price breaks below opening range LOW (bearish signal)
        or breaks above opening range HIGH (bullish signal)
        """
        if symbol not in self.opening_ranges:
            self.analyze_opening_range(symbol)
        
        or_data = self.opening_ranges.get(symbol, {})
        
        if or_data.get('status') != 'COMPLETE':
            return {'breakdown': False, 'breakout': False}
        
        # Get current price
        endpoint = f"/v2/last/trade/{symbol}"
        data = self._make_request(endpoint)
        
        current_price = data.get('results', {}).get('p', 0) if 'results' in data else 0
        
        or_high = or_data['or_high']
        or_low = or_data['or_low']
        
        breakdown = current_price < or_low  # Bearish
        breakout = current_price > or_high  # Bullish
        
        return {
            'breakdown': breakdown,
            'breakout': breakout,
            'current_price': round(current_price, 2),
            'or_high': or_high,
            'or_low': or_low,
            'distance_from_or_low': round(((current_price - or_low) / or_low) * 100, 2),
            'distance_from_or_high': round(((current_price - or_high) / or_high) * 100, 2)
        }
    
    def generate_opening_signal(self, symbol: str) -> Dict:
        """
        Generate trading signal based on opening range analysis
        
        Signal Logic:
        - STRONG SELL: Bearish OR + High Volume + At Resistance
        - SELL: Bearish OR + OR Breakdown
        - STRONG BUY: Bullish OR + High Volume + Above Support
        - BUY: Bullish OR + OR Breakout
        """
        # Analyze opening range
        or_analysis = self.analyze_opening_range(symbol, range_minutes=5)
        
        if or_analysis.get('status') != 'COMPLETE':
            return {
                'signal': None,
                'reason': or_analysis.get('status', 'INCOMPLETE'),
                'confidence': 0
            }
        
        # Check for breakdown/breakout
        breakdown_analysis = self.detect_opening_range_breakdown(symbol)
        
        # Score factors
        bullish_score = 0
        bearish_score = 0
        
        # Opening range direction (strong weight)
        if or_analysis['direction'] == 'BULLISH':
            bullish_score += 3 if or_analysis['strength'] == 'STRONG' else 2
        elif or_analysis['direction'] == 'BEARISH':
            bearish_score += 3 if or_analysis['strength'] == 'STRONG' else 2
        
        # Volume (important for confirmation)
        if or_analysis['high_volume']:
            if or_analysis['direction'] == 'BULLISH':
                bullish_score += 2
            elif or_analysis['direction'] == 'BEARISH':
                bearish_score += 2
        
        # Previous day levels
        if or_analysis.get('at_resistance'):
            bearish_score += 2  # Resistance = potential rejection
        
        if or_analysis.get('breakout') == 'BROKE_RESISTANCE':
            bullish_score += 3
        elif or_analysis.get('breakout') == 'BROKE_SUPPORT':
            bearish_score += 3
        
        # Current breakdown/breakout
        if breakdown_analysis['breakdown']:
            bearish_score += 2
        elif breakdown_analysis['breakout']:
            bullish_score += 2
        
        # Generate signal
        signal = None
        alert_type = 'MONITOR'
        confidence = 0
        
        if bearish_score >= 5:
            signal = 'SELL'
            confidence = min(bearish_score / 10 * 100, 95)
            alert_type = 'STRONG SELL' if bearish_score >= 7 else 'SELL'
        elif bullish_score >= 5:
            signal = 'BUY'
            confidence = min(bullish_score / 10 * 100, 95)
            alert_type = 'STRONG BUY' if bullish_score >= 7 else 'BUY'
        
        return {
            'signal': signal,
            'alert_type': alert_type,
            'confidence': round(confidence, 1),
            'opening_range': or_analysis,
            'breakdown_analysis': breakdown_analysis,
            'bullish_score': bullish_score,
            'bearish_score': bearish_score,
            'reason': self._generate_reason(or_analysis, breakdown_analysis, signal)
        }
    
    def _generate_reason(self, or_analysis: Dict, breakdown: Dict, signal: str) -> str:
        """Generate human-readable reason for signal"""
        reasons = []
        
        if or_analysis['direction'] != 'NEUTRAL':
            reasons.append(f"{or_analysis['strength']} {or_analysis['direction']} opening range")
        
        if or_analysis['high_volume']:
            reasons.append("High volume confirmation")
        
        if or_analysis.get('at_resistance'):
            reasons.append("Opening at previous close (resistance)")
        
        if breakdown['breakdown']:
            reasons.append("BREAKDOWN below opening range low")
        elif breakdown['breakout']:
            reasons.append("BREAKOUT above opening range high")
        
        if or_analysis.get('breakout'):
            reasons.append(or_analysis['breakout'].replace('_', ' '))
        
        return " | ".join(reasons) if reasons else "No clear signal"


# Example usage
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    API_KEY = os.getenv('POLYGON_API_KEY')
    
    analyzer = OpeningRangeAnalyzer(api_key=API_KEY)
    
    # Test with PLTR
    print("=" * 80)
    print("OPENING RANGE ANALYSIS")
    print("=" * 80)
    
    result = analyzer.generate_opening_signal('PLTR')
    
    print(f"\nSymbol: PLTR")
    print(f"Signal: {result.get('signal', 'None')}")
    print(f"Alert Type: {result.get('alert_type')}")
    print(f"Confidence: {result.get('confidence', 0):.1f}%")
    print(f"\nReason: {result.get('reason')}")
    
    or_data = result.get('opening_range', {})
    if or_data.get('status') == 'COMPLETE':
        print(f"\nOpening Range (First {or_data['minutes_analyzed']} min):")
        print(f"  Direction: {or_data['direction']} ({or_data['strength']})")
        print(f"  High: ${or_data['or_high']:.2f}")
        print(f"  Low: ${or_data['or_low']:.2f}")
        print(f"  Range: ${or_data['or_range']:.2f}")
        print(f"  Change: {or_data['price_change_pct']:.2f}%")
        print(f"  Volume Ratio: {or_data['volume_ratio']:.2f}x")
        
        if or_data.get('breakout'):
            print(f"  Breakout Type: {or_data['breakout']}")
    
    bd = result.get('breakdown_analysis', {})
    if bd:
        print(f"\nCurrent Status:")
        print(f"  Price: ${bd.get('current_price', 0):.2f}")
        print(f"  OR Breakdown: {'YES' if bd.get('breakdown') else 'NO'}")
        print(f"  OR Breakout: {'YES' if bd.get('breakout') else 'NO'}")