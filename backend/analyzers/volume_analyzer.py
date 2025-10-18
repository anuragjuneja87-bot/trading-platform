"""
backend/analyzers/volume_analyzer.py
FIXED Volume Analyzer - Real-time Spike Detection
- Pre-market: 5-min bar vs historical 5-min pre-market average
- Regular hours: Last 1-min bar vs previous 10 bars (instant spike detection)
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
        Initialize Volume Analyzer with REAL-TIME spike detection
        
        Args:
            api_key: Polygon.io API key
        """
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"
        self.logger = logging.getLogger(__name__)
        
        # FIXED Configuration - for REAL spike detection
        self.lookback_days = 20  # Historical comparison
        self.spike_lookback_bars = 10  # Compare last bar to previous 10 bars
        
        # Alert Thresholds
        self.threshold_elevated = 2.5  # 2.5x = Elevated
        self.threshold_high = 3.5      # 3.5x = High  
        self.threshold_extreme = 5.0   # 5.0x = Extreme
        
        # Cache
        self.cache = {}
        self.cache_duration = 30  # 30 seconds
        
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
        FIXED Pre-Market RVOL
        Compares current 5-min pre-market bar to historical 5-min pre-market average
        
        Pre-market hours: 4:00 AM - 9:30 AM ET
        
        Returns:
            rvol: Current bar / Historical average bar
            classification: LOW, NORMAL, ELEVATED, HIGH, EXTREME
            spike_detected: Boolean for Discord alerts
        """
        try:
            # Get today's pre-market data (1-minute bars)
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
            today_df['timestamp'] = pd.to_datetime(today_df['t'], unit='ms', utc=True)
            today_df['timestamp'] = today_df['timestamp'].dt.tz_convert('America/New_York')
            
            # Filter for pre-market hours only (4:00 AM - 9:30 AM ET)
            today_df['hour'] = today_df['timestamp'].dt.hour
            today_df['minute'] = today_df['timestamp'].dt.minute
            
            premarket = today_df[
                ((today_df['hour'] >= 4) & (today_df['hour'] < 9)) |
                ((today_df['hour'] == 9) & (today_df['minute'] < 30))
            ].copy()
            
            if len(premarket) < 5:
                return self._empty_rvol_result('PREMARKET')
            
            # Get LAST 5 bars (last 5 minutes of pre-market activity)
            recent_bars = premarket.tail(5)
            current_5min_volume = recent_bars['v'].sum()
            
            # Get historical pre-market data for comparison
            # We need last 20 days of pre-market 5-min volumes
            historical_5min_volumes = []
            
            for days_ago in range(1, self.lookback_days + 1):
                hist_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
                
                hist_data = self._make_request(
                    f"/v2/aggs/ticker/{symbol}/range/1/minute/{hist_date}/{hist_date}",
                    {'adjusted': 'true', 'sort': 'asc', 'limit': 50000}
                )
                
                if 'results' not in hist_data or not hist_data['results']:
                    continue
                
                hist_df = pd.DataFrame(hist_data['results'])
                hist_df['timestamp'] = pd.to_datetime(hist_df['t'], unit='ms', utc=True)
                hist_df['timestamp'] = hist_df['timestamp'].dt.tz_convert('America/New_York')
                hist_df['hour'] = hist_df['timestamp'].dt.hour
                hist_df['minute'] = hist_df['timestamp'].dt.minute
                
                # Filter pre-market
                hist_premarket = hist_df[
                    ((hist_df['hour'] >= 4) & (hist_df['hour'] < 9)) |
                    ((hist_df['hour'] == 9) & (hist_df['minute'] < 30))
                ]
                
                if len(hist_premarket) >= 5:
                    # Get all 5-min chunks and average them
                    for i in range(0, len(hist_premarket) - 4, 5):
                        chunk_volume = hist_premarket.iloc[i:i+5]['v'].sum()
                        historical_5min_volumes.append(chunk_volume)
            
            if len(historical_5min_volumes) == 0:
                return self._empty_rvol_result('PREMARKET')
            
            # Calculate average historical 5-min volume
            avg_hist_5min = np.mean(historical_5min_volumes)
            
            # Calculate RVOL
            rvol = current_5min_volume / avg_hist_5min if avg_hist_5min > 0 else 0
            
            # Classify and detect spikes
            if rvol >= self.threshold_extreme:
                classification = 'EXTREME'
                spike_detected = True
                signal_strength = 4
            elif rvol >= self.threshold_high:
                classification = 'HIGH'
                spike_detected = True
                signal_strength = 3
            elif rvol >= self.threshold_elevated:
                classification = 'ELEVATED'
                spike_detected = True
                signal_strength = 2
            elif rvol >= 0.7:
                classification = 'NORMAL'
                spike_detected = False
                signal_strength = 0
            else:
                classification = 'LOW'
                spike_detected = False
                signal_strength = -1
            
            return {
                'rvol': round(rvol, 2),
                'classification': classification,
                'spike_detected': spike_detected,
                'signal_strength': signal_strength,
                'current_5min_volume': int(current_5min_volume),
                'avg_hist_5min_volume': int(avg_hist_5min),
                'session': 'PREMARKET',
                'bars_analyzed': len(recent_bars),
                'historical_samples': len(historical_5min_volumes)
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
            today_df['timestamp'] = pd.to_datetime(today_df['t'], unit='ms', utc=True)
            today_df['timestamp'] = today_df['timestamp'].dt.tz_convert('America/New_York')
            
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
            if rvol >= self.threshold_extreme:
                classification = 'EXTREME'
                signal_strength = 4
            elif rvol >= self.threshold_high:
                classification = 'HIGH'
                signal_strength = 3
            elif rvol >= self.threshold_elevated:
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
    
    def calculate_intraday_spike(self, symbol: str) -> Dict:
        """
        FIXED Intraday Volume Spike Detection
        Compares LAST 1-minute bar to PREVIOUS 10 bars
        
        This catches AMD-style breakouts in REAL-TIME!
        
        Returns:
            spike_ratio: Current bar / Average of previous 10 bars
            classification: LOW, NORMAL, ELEVATED, HIGH, EXTREME
            spike_detected: Boolean for Discord alerts
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
                return self._empty_spike_result()
            
            df = pd.DataFrame(data['results'])
            df['timestamp'] = pd.to_datetime(df['t'], unit='ms', utc=True)
            df['timestamp'] = df['timestamp'].dt.tz_convert('America/New_York')
            df['hour'] = df['timestamp'].dt.hour
            df['minute'] = df['timestamp'].dt.minute
            
            # Filter for market hours only (9:30 AM - 4:00 PM ET)
            market_hours = df[
                ((df['hour'] == 9) & (df['minute'] >= 30)) |
                ((df['hour'] >= 10) & (df['hour'] < 16))
            ].copy()
            
            if len(market_hours) < self.spike_lookback_bars + 1:
                return self._empty_spike_result()
            
            # Get LAST bar (current minute)
            current_bar_volume = market_hours.iloc[-1]['v']
            
            # Get PREVIOUS 10 bars
            previous_bars = market_hours.iloc[-(self.spike_lookback_bars + 1):-1]
            avg_previous_volume = previous_bars['v'].mean()
            
            # Calculate spike ratio
            spike_ratio = current_bar_volume / avg_previous_volume if avg_previous_volume > 0 else 0
            
            # Classify spike
            if spike_ratio >= self.threshold_extreme:
                classification = 'EXTREME'
                spike_detected = True
                signal_strength = 4
                alert_urgency = 'CRITICAL'
            elif spike_ratio >= self.threshold_high:
                classification = 'HIGH'
                spike_detected = True
                signal_strength = 3
                alert_urgency = 'HIGH'
            elif spike_ratio >= self.threshold_elevated:
                classification = 'ELEVATED'
                spike_detected = True
                signal_strength = 2
                alert_urgency = 'MEDIUM'
            elif spike_ratio >= 0.7:
                classification = 'NORMAL'
                spike_detected = False
                signal_strength = 0
                alert_urgency = 'NONE'
            else:
                classification = 'LOW'
                spike_detected = False
                signal_strength = -1
                alert_urgency = 'NONE'
            
            # Get current price movement for context
            current_price = market_hours.iloc[-1]['c']
            price_10_bars_ago = market_hours.iloc[-(self.spike_lookback_bars + 1)]['c']
            price_change_pct = ((current_price - price_10_bars_ago) / price_10_bars_ago) * 100
            
            # Determine direction
            if price_change_pct > 0.5:
                direction = 'BREAKOUT'
            elif price_change_pct < -0.5:
                direction = 'BREAKDOWN'
            else:
                direction = 'NEUTRAL'
            
            return {
                'spike_ratio': round(spike_ratio, 2),
                'classification': classification,
                'spike_detected': spike_detected,
                'signal_strength': signal_strength,
                'alert_urgency': alert_urgency,
                'current_bar_volume': int(current_bar_volume),
                'avg_previous_volume': int(avg_previous_volume),
                'direction': direction,
                'price_change_pct': round(price_change_pct, 2),
                'session': 'REGULAR',
                'bars_analyzed': len(previous_bars) + 1,
                'current_time': market_hours.iloc[-1]['timestamp'].strftime('%H:%M:%S')
            }
            
        except Exception as e:
            self.logger.error(f"Error detecting intraday spike for {symbol}: {str(e)}")
            return self._empty_spike_result()
    
    def generate_volume_analysis(self, symbol: str) -> Dict:
        """
        Complete volume analysis for a symbol (used by enhanced_professional_analyzer.py)
        Combines RVOL with spike detection
        
        Returns:
            Complete volume analysis with signal strengths
        """
        try:
            self.logger.debug(f"Running volume analysis for {symbol}...")
            
            # Get RVOL (regular hours)
            rvol = self.calculate_rvol(symbol)
            
            # Get spike detection (regular hours)
            spike = self.calculate_intraday_spike(symbol)
            
            # Calculate total volume signal strength
            total_signal = (
                rvol.get('signal_strength', 0) +
                spike.get('signal_strength', 0)
            )
            
            # Generate summary
            summary_parts = []
            
            if rvol.get('classification') in ['HIGH', 'EXTREME']:
                summary_parts.append(f"RVOL {rvol['rvol']}x ({rvol['classification']})")
            
            if spike.get('spike_detected'):
                summary_parts.append(f"Volume spike {spike['spike_ratio']}x")
            
            summary = " | ".join(summary_parts) if summary_parts else "Normal volume"
            
            return {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'rvol': rvol,
                'volume_spike': spike,
                'total_signal_strength': total_signal,
                'summary': summary
            }
            
        except Exception as e:
            self.logger.error(f"Error in volume analysis for {symbol}: {str(e)}")
            return {'error': str(e)}
    
    def _empty_rvol_result(self, session: str = 'REGULAR') -> Dict:
        """Return empty RVOL result"""
        return {
            'rvol': 0,
            'classification': 'UNKNOWN',
            'spike_detected': False,
            'signal_strength': 0,
            'current_5min_volume': 0,
            'avg_hist_5min_volume': 0,
            'session': session
        }
    
    def _empty_spike_result(self) -> Dict:
        """Return empty spike result"""
        return {
            'spike_ratio': 0,
            'classification': 'UNKNOWN',
            'spike_detected': False,
            'signal_strength': 0,
            'alert_urgency': 'NONE',
            'current_bar_volume': 0,
            'avg_previous_volume': 0,
            'direction': 'UNKNOWN',
            'price_change_pct': 0,
            'session': 'REGULAR'
        }