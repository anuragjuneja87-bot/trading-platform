"""
backend/analyzers/volume_analyzer.py
Volume Analyzer - Comprehensive Volume Analysis
NOW INCLUDES PRE-MARKET RVOL CALCULATION
"""

import requests
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import logging
from collections import defaultdict


class VolumeAnalyzer:
    def __init__(self, api_key: str):
        """
        Initialize Volume Analyzer
        
        Args:
            api_key: Polygon.io API key
        """
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.lookback_days = 20  # For RVOL calculation
        self.rvol_high_threshold = 2.0  # 2x average
        self.rvol_extreme_threshold = 3.0  # 3x average
        self.spike_threshold = 1.5  # 1.5x recent bars
        
        # Cache for performance
        self.cache = {}
        self.cache_duration = 60  # 1 minute cache
    
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
            self.logger.error(f"API request failed for {endpoint}: {str(e)}")
            return {}
    
    def calculate_premarket_rvol(self, symbol: str) -> Dict:
        """
        NEW: Calculate Pre-Market Relative Volume (RVOL)
        Compares current pre-market volume to 20-day average pre-market volume
        
        Pre-market hours: 4:00 AM - 9:30 AM ET
        
        Returns:
            rvol: Relative volume ratio
            classification: LOW, NORMAL, ELEVATED, HIGH, EXTREME
            current_volume: Current pre-market volume
            avg_premarket_volume: Average pre-market volume
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
                return self._empty_rvol_result('PREMARKET')
            
            today_df = pd.DataFrame(data['results'])
            today_df['timestamp'] = pd.to_datetime(today_df['t'], unit='ms')
            
            # Filter for pre-market hours only (4:00 AM - 9:30 AM ET)
            today_df['hour'] = today_df['timestamp'].dt.hour
            today_df['minute'] = today_df['timestamp'].dt.minute
            
            premarket = today_df[
                ((today_df['hour'] == 4) | 
                 (today_df['hour'] == 5) | 
                 (today_df['hour'] == 6) | 
                 (today_df['hour'] == 7) | 
                 (today_df['hour'] == 8) |
                 ((today_df['hour'] == 9) & (today_df['minute'] < 30)))
            ]
            
            if len(premarket) == 0:
                return self._empty_rvol_result('PREMARKET')
            
            current_premarket_volume = premarket['v'].sum()
            
            # Get historical pre-market volumes
            end_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=self.lookback_days + 5)).strftime('%Y-%m-%d')
            
            # For historical data, we need to get minute data and filter for pre-market
            # This is expensive, so we'll approximate using daily volume
            # A better approach: Store historical pre-market volumes
            
            # SIMPLIFIED: Use proportion of daily volume
            # Typically pre-market is ~5-10% of daily volume
            endpoint = f"/v2/aggs/ticker/{symbol}/range/1/day/{start_date}/{end_date}"
            hist_data = self._make_request(endpoint, {'adjusted': 'true'})
            
            if 'results' not in hist_data or not hist_data['results']:
                return self._empty_rvol_result('PREMARKET')
            
            hist_df = pd.DataFrame(hist_data['results'])
            avg_daily_volume = hist_df['v'].mean()
            
            # Estimate average pre-market volume (typically 5-8% of daily)
            # We'll use 6% as baseline
            estimated_avg_premarket = avg_daily_volume * 0.06
            
            # Calculate RVOL
            if estimated_avg_premarket > 0:
                rvol = current_premarket_volume / estimated_avg_premarket
            else:
                rvol = 0
            
            # Classify RVOL
            if rvol >= self.rvol_extreme_threshold:
                classification = 'EXTREME'
                signal_strength = 4
            elif rvol >= self.rvol_high_threshold:
                classification = 'HIGH'
                signal_strength = 3
            elif rvol >= 1.5:
                classification = 'ELEVATED'
                signal_strength = 2
            elif rvol >= 0.7:
                classification = 'NORMAL'
                signal_strength = 0
            else:
                classification = 'LOW'
                signal_strength = -1
            
            return {
                'rvol': round(rvol, 2),
                'classification': classification,
                'signal_strength': signal_strength,
                'current_volume': int(current_premarket_volume),
                'expected_volume': int(estimated_avg_premarket),
                'avg_daily_volume': int(avg_daily_volume),
                'premarket_bars': len(premarket),
                'session': 'PREMARKET'
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating pre-market RVOL for {symbol}: {str(e)}")
            return self._empty_rvol_result('PREMARKET')
    
    def calculate_rvol(self, symbol: str) -> Dict:
        """
        Calculate Relative Volume (RVOL) - REGULAR HOURS
        Compares current volume to 20-day average at same time
        
        Returns:
            rvol: Relative volume ratio
            classification: LOW, NORMAL, HIGH, EXTREME
            current_volume: Current volume
            avg_volume: Average volume
        """
        try:
            # Get today's volume data
            today = datetime.now().strftime('%Y-%m-%d')
            endpoint = f"/v2/aggs/ticker/{symbol}/range/1/minute/{today}/{today}"
            
            data = self._make_request(endpoint, {
                'adjusted': 'true',
                'sort': 'asc',
                'limit': 50000
            })
            
            if 'results' not in data or not data['results']:
                return self._empty_rvol_result('REGULAR')
            
            today_df = pd.DataFrame(data['results'])
            today_df['timestamp'] = pd.to_datetime(today_df['t'], unit='ms')
            
            # Filter for market hours only (9:30 AM - 4:00 PM ET)
            today_df['hour'] = today_df['timestamp'].dt.hour
            today_df['minute'] = today_df['timestamp'].dt.minute
            
            market_hours = today_df[
                ((today_df['hour'] == 9) & (today_df['minute'] >= 30)) |
                ((today_df['hour'] >= 10) & (today_df['hour'] < 16))
            ]
            
            if len(market_hours) == 0:
                return self._empty_rvol_result('REGULAR')
            
            current_volume = market_hours['v'].sum()
            current_minutes = len(market_hours)
            
            # Get historical average volume
            end_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=self.lookback_days + 5)).strftime('%Y-%m-%d')
            
            endpoint = f"/v2/aggs/ticker/{symbol}/range/1/day/{start_date}/{end_date}"
            hist_data = self._make_request(endpoint, {'adjusted': 'true'})
            
            if 'results' not in hist_data or not hist_data['results']:
                return self._empty_rvol_result('REGULAR')
            
            hist_df = pd.DataFrame(hist_data['results'])
            
            # Calculate average daily volume
            avg_daily_volume = hist_df['v'].mean()
            
            # Estimate what volume should be at this time
            # Assuming 390 minutes in trading day
            expected_volume = (avg_daily_volume / 390) * current_minutes
            
            # Calculate RVOL
            rvol = current_volume / expected_volume if expected_volume > 0 else 0
            
            # Classify RVOL
            if rvol >= self.rvol_extreme_threshold:
                classification = 'EXTREME'
                signal_strength = 4
            elif rvol >= self.rvol_high_threshold:
                classification = 'HIGH'
                signal_strength = 3
            elif rvol >= 1.5:
                classification = 'ELEVATED'
                signal_strength = 2
            elif rvol >= 0.7:
                classification = 'NORMAL'
                signal_strength = 0
            else:
                classification = 'LOW'
                signal_strength = -1
            
            return {
                'rvol': round(rvol, 2),
                'classification': classification,
                'signal_strength': signal_strength,
                'current_volume': int(current_volume),
                'expected_volume': int(expected_volume),
                'avg_daily_volume': int(avg_daily_volume),
                'minutes_into_day': current_minutes,
                'volume_per_minute': int(current_volume / current_minutes) if current_minutes > 0 else 0,
                'session': 'REGULAR'
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating RVOL for {symbol}: {str(e)}")
            return self._empty_rvol_result('REGULAR')
    
    def detect_volume_spike(self, symbol: str, lookback_bars: int = 10) -> Dict:
        """
        Detect volume spikes compared to recent bars
        
        Args:
            symbol: Stock symbol
            lookback_bars: Number of bars to compare against
        
        Returns:
            spike_detected: Boolean
            spike_ratio: Current volume / avg recent volume
            signal_strength: 0-3 points
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
                return {'spike_detected': False, 'spike_ratio': 0, 'signal_strength': 0}
            
            df = pd.DataFrame(data['results'])
            
            if len(df) < lookback_bars + 1:
                return {'spike_detected': False, 'spike_ratio': 0, 'signal_strength': 0}
            
            # Get recent volume average (excluding current bar)
            recent_volume = df['v'].iloc[-(lookback_bars+1):-1].mean()
            current_volume = df['v'].iloc[-1]
            
            spike_ratio = current_volume / recent_volume if recent_volume > 0 else 0
            
            # Detect spike
            if spike_ratio >= 3.0:
                spike_detected = True
                signal_strength = 3
                severity = 'EXTREME'
            elif spike_ratio >= 2.0:
                spike_detected = True
                signal_strength = 2
                severity = 'HIGH'
            elif spike_ratio >= self.spike_threshold:
                spike_detected = True
                signal_strength = 1
                severity = 'MODERATE'
            else:
                spike_detected = False
                signal_strength = 0
                severity = 'NONE'
            
            return {
                'spike_detected': spike_detected,
                'spike_ratio': round(spike_ratio, 2),
                'signal_strength': signal_strength,
                'severity': severity,
                'current_bar_volume': int(current_volume),
                'avg_recent_volume': int(recent_volume)
            }
            
        except Exception as e:
            self.logger.error(f"Error detecting volume spike for {symbol}: {str(e)}")
            return {'spike_detected': False, 'spike_ratio': 0, 'signal_strength': 0}
    
    def detect_volume_dryup(self, symbol: str, threshold: float = 0.5) -> Dict:
        """
        Detect volume dry-up (consolidation pattern)
        Low volume often precedes big moves
        
        Args:
            symbol: Stock symbol
            threshold: Volume ratio considered "dry-up" (0.5 = 50% below average)
        
        Returns:
            dryup_detected: Boolean
            dryup_ratio: Current volume / average volume
            signal_strength: 0-2 points (setup forming)
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
                return {'dryup_detected': False, 'dryup_ratio': 1.0, 'signal_strength': 0}
            
            df = pd.DataFrame(data['results'])
            
            if len(df) < 15:
                return {'dryup_detected': False, 'dryup_ratio': 1.0, 'signal_strength': 0}
            
            # Compare last 5 bars to previous 10 bars
            recent_volume = df['v'].iloc[-5:].mean()
            previous_volume = df['v'].iloc[-15:-5].mean()
            
            dryup_ratio = recent_volume / previous_volume if previous_volume > 0 else 1.0
            
            # Detect dry-up (volume significantly below average)
            if dryup_ratio <= 0.3:
                dryup_detected = True
                signal_strength = 2
                severity = 'EXTREME'
            elif dryup_ratio <= threshold:
                dryup_detected = True
                signal_strength = 1
                severity = 'MODERATE'
            else:
                dryup_detected = False
                signal_strength = 0
                severity = 'NONE'
            
            return {
                'dryup_detected': dryup_detected,
                'dryup_ratio': round(dryup_ratio, 2),
                'signal_strength': signal_strength,
                'severity': severity,
                'recent_avg_volume': int(recent_volume),
                'previous_avg_volume': int(previous_volume),
                'status': 'CONSOLIDATING' if dryup_detected else 'NORMAL'
            }
            
        except Exception as e:
            self.logger.error(f"Error detecting volume dry-up for {symbol}: {str(e)}")
            return {'dryup_detected': False, 'dryup_ratio': 1.0, 'signal_strength': 0}
    
    def detect_block_trades(self, symbol: str, threshold_percentile: float = 95) -> Dict:
        """
        Detect large block trades (institutional activity)
        
        Args:
            symbol: Stock symbol
            threshold_percentile: Percentile to consider "large" trade
        
        Returns:
            block_trades_detected: Boolean
            block_count: Number of block trades
            signal_strength: 0-2 points
        """
        try:
            endpoint = f"/v3/trades/{symbol}"
            params = {'limit': 1000, 'order': 'desc'}
            
            data = self._make_request(endpoint, params)
            
            if 'results' not in data or not data['results']:
                return {'block_trades_detected': False, 'block_count': 0, 'signal_strength': 0}
            
            trades = data['results']
            sizes = [t.get('size', 0) for t in trades]
            
            if len(sizes) < 10:
                return {'block_trades_detected': False, 'block_count': 0, 'signal_strength': 0}
            
            # Calculate threshold for "block" trade
            threshold = np.percentile(sizes, threshold_percentile)
            
            # Count block trades
            block_trades = [s for s in sizes if s >= threshold]
            block_count = len(block_trades)
            
            # Signal strength based on block trade frequency
            if block_count > len(sizes) * 0.1:  # More than 10% are blocks
                signal_strength = 2
                severity = 'HIGH'
            elif block_count > len(sizes) * 0.05:  # More than 5%
                signal_strength = 1
                severity = 'MODERATE'
            else:
                signal_strength = 0
                severity = 'LOW'
            
            block_trades_detected = signal_strength > 0
            
            return {
                'block_trades_detected': block_trades_detected,
                'block_count': block_count,
                'signal_strength': signal_strength,
                'severity': severity,
                'threshold_size': int(threshold),
                'largest_trade': int(max(sizes)) if sizes else 0,
                'avg_trade_size': int(np.mean(sizes)) if sizes else 0
            }
            
        except Exception as e:
            self.logger.error(f"Error detecting block trades for {symbol}: {str(e)}")
            return {'block_trades_detected': False, 'block_count': 0, 'signal_strength': 0}
    
    def analyze_volume_profile(self, symbol: str) -> Dict:
        """
        Analyze volume distribution (where the most volume traded)
        
        Returns:
            volume_weighted_price: VWAP-like metric
            high_volume_price: Price level with most volume
            volume_distribution: Distribution classification
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
            
            # Calculate volume-weighted price
            df['vwap'] = (df['c'] * df['v']).cumsum() / df['v'].cumsum()
            
            # Find price level with most volume (simplified)
            # Group by price ranges
            df['price_bucket'] = (df['c'] / 0.50).round() * 0.50  # $0.50 buckets
            volume_by_price = df.groupby('price_bucket')['v'].sum()
            
            high_volume_price = volume_by_price.idxmax() if len(volume_by_price) > 0 else 0
            
            # Analyze distribution
            current_price = df['c'].iloc[-1]
            price_range = df['c'].max() - df['c'].min()
            
            if price_range > 0:
                position_in_range = (current_price - df['c'].min()) / price_range
                
                if position_in_range > 0.7:
                    distribution = 'UPPER_RANGE'
                elif position_in_range < 0.3:
                    distribution = 'LOWER_RANGE'
                else:
                    distribution = 'MID_RANGE'
            else:
                distribution = 'TIGHT'
            
            return {
                'volume_weighted_price': round(df['vwap'].iloc[-1], 2),
                'high_volume_price': round(high_volume_price, 2),
                'volume_distribution': distribution,
                'current_vs_high_volume': 'AT_VOLUME' if abs(current_price - high_volume_price) < 0.5 else 'AWAY'
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing volume profile for {symbol}: {str(e)}")
            return {}
    
    def generate_volume_analysis(self, symbol: str) -> Dict:
        """
        Complete volume analysis for a symbol
        Combines all volume metrics
        
        Returns:
            Complete volume analysis with signal strengths
        """
        try:
            self.logger.debug(f"Running volume analysis for {symbol}...")
            
            # Get all volume metrics
            rvol = self.calculate_rvol(symbol)
            spike = self.detect_volume_spike(symbol)
            dryup = self.detect_volume_dryup(symbol)
            blocks = self.detect_block_trades(symbol)
            profile = self.analyze_volume_profile(symbol)
            
            # Calculate total volume signal strength
            total_signal = (
                rvol.get('signal_strength', 0) +
                spike.get('signal_strength', 0) +
                dryup.get('signal_strength', 0) +
                blocks.get('signal_strength', 0)
            )
            
            return {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'rvol': rvol,
                'volume_spike': spike,
                'volume_dryup': dryup,
                'block_trades': blocks,
                'volume_profile': profile,
                'total_signal_strength': total_signal,
                'summary': self._generate_volume_summary(rvol, spike, dryup, blocks)
            }
            
        except Exception as e:
            self.logger.error(f"Error in volume analysis for {symbol}: {str(e)}")
            return {'error': str(e)}
    
    def _generate_volume_summary(self, rvol: Dict, spike: Dict, dryup: Dict, blocks: Dict) -> str:
        """Generate human-readable volume summary"""
        summary_parts = []
        
        if rvol.get('classification') in ['HIGH', 'EXTREME']:
            summary_parts.append(f"RVOL {rvol['rvol']}x ({rvol['classification']})")
        
        if spike.get('spike_detected'):
            summary_parts.append(f"Volume spike {spike['spike_ratio']}x")
        
        if dryup.get('dryup_detected'):
            summary_parts.append(f"Volume dry-up (consolidating)")
        
        if blocks.get('block_trades_detected'):
            summary_parts.append(f"{blocks['block_count']} block trades")
        
        return " | ".join(summary_parts) if summary_parts else "Normal volume"
    
    def _empty_rvol_result(self, session: str = 'REGULAR') -> Dict:
        """Return empty RVOL result"""
        return {
            'rvol': 0,
            'classification': 'UNKNOWN',
            'signal_strength': 0,
            'current_volume': 0,
            'expected_volume': 0,
            'avg_daily_volume': 0,
            'session': session
        }


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
    
    analyzer = VolumeAnalyzer(api_key=API_KEY)
    
    # Test with NVDA
    print("=" * 80)
    print("VOLUME ANALYSIS - NVDA")
    print("=" * 80)
    
    # Test pre-market RVOL
    print("\n📊 PRE-MARKET RVOL:")
    premarket = analyzer.calculate_premarket_rvol('NVDA')
    print(f"  RVOL: {premarket['rvol']}x ({premarket['classification']})")
    print(f"  Current Volume: {premarket['current_volume']:,}")
    print(f"  Expected Volume: {premarket['expected_volume']:,}")
    
    # Test regular RVOL
    print("\n📊 REGULAR HOURS RVOL:")
    result = analyzer.generate_volume_analysis('NVDA')
    
    if 'error' in result:
        print(f"❌ Error: {result['error']}")
    else:
        print(f"\nVolume Summary: {result['summary']}")
        
        rvol = result['rvol']
        print(f"\n📈 RVOL Analysis:")
        print(f"  • RVOL: {rvol['rvol']}x ({rvol['classification']})")
        print(f"  • Current Volume: {rvol['current_volume']:,}")
        print(f"  • Expected Volume: {rvol['expected_volume']:,}")
        print(f"  • Signal Strength: {rvol['signal_strength']}/4")
    
    print("\n" + "=" * 80)