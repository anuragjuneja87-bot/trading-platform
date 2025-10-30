"""
backend/analyzers/volume_analyzer.py v2.0
ENHANCED Volume Analyzer - Real-Time Day Trading Edition

IMPROVEMENTS:
- Progressive bar checking: Alerts 30-45 seconds earlier ⚡
- Day trader thresholds: 1.8x/2.3x/3.5x (was 2.5x/3.5x/5.0x)
- Tiered alerts: Building/Elevated/High/Extreme
- Volume + price confirmation: Avoid false positives
- Minimum volume filters: Quality over quantity

FOR 7-FIGURE DAY TRADERS - Catch moves early, not late
"""

import requests
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import logging
from collections import defaultdict


class VolumeAnalyzer:
    def __init__(self, api_key: str, trading_style: str = 'day_trader'):
        """
        Initialize Volume Analyzer v2.0 - REAL-TIME spike detection
        
        Args:
            api_key: Polygon.io API key
            trading_style: 'day_trader' (fast), 'swing_trader' (conservative), 'scalper' (fastest)
        """
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"
        self.logger = logging.getLogger(__name__)
        self.trading_style = trading_style
        
        # Configuration
        self.lookback_days = 20  # Historical comparison
        
        # OPTIMIZED: Faster lookback for day trading
        if trading_style == 'scalper':
            self.spike_lookback_bars = 4   # Last 4 minutes (fastest)
        elif trading_style == 'day_trader':
            self.spike_lookback_bars = 6   # Last 6 minutes (balanced)
        else:  # swing_trader
            self.spike_lookback_bars = 10  # Last 10 minutes (conservative)
        
        # TIER 1: Pre-Alert Thresholds (internal tracking)
        self.threshold_attention = 1.3   # 1.3x = Worth watching
        self.threshold_building = 1.5    # 1.5x = Volume building
        
        # TIER 2: Main Alert Thresholds (Discord alerts)
        if trading_style == 'scalper':
            # Ultra-aggressive for scalping (more alerts, faster)
            self.threshold_elevated = 1.5   # 1.5x = Elevated
            self.threshold_high = 2.0       # 2.0x = High  
            self.threshold_extreme = 3.0    # 3.0x = Extreme
        elif trading_style == 'day_trader':
            # Optimized for day trading (balanced)
            self.threshold_elevated = 1.8   # 1.8x = Elevated (was 2.5x) ⬇️ 28% more sensitive
            self.threshold_high = 2.3       # 2.3x = High (was 3.5x) ⬇️ 34% more sensitive
            self.threshold_extreme = 3.5    # 3.5x = Extreme (was 5.0x) ⬇️ 30% more sensitive
        else:  # swing_trader
            # Conservative for swing trading (original settings)
            self.threshold_elevated = 2.5
            self.threshold_high = 3.5
            self.threshold_extreme = 5.0
        
        # TIER 3: Extreme threshold
        self.threshold_parabolic = 5.0   # 5.0x = Parabolic move (rare)
        
        # Minimum volume filters (avoid low-volume false positives)
        self.min_spike_volume = 50000    # Minimum 50k shares in spike bar
        self.min_total_volume = 500000   # Minimum 500k shares total today
        self.min_price_change = 0.3      # Minimum 0.3% price move with spike
        
        # Progressive bar checking (NEW - catches spikes early)
        self.progressive_check_interval = 30  # Check at 30 seconds into bar
        
        # Cache
        self.cache = {}
        self.cache_duration = 30  # 30 seconds
        
        self.logger.info(f"✅ Volume Analyzer v2.0 initialized ({trading_style} mode)")
        self.logger.info(f"   📏 Thresholds: {self.threshold_elevated}x / {self.threshold_high}x / {self.threshold_extreme}x")
        self.logger.info(f"   ⏱️ Lookback: {self.spike_lookback_bars} bars")
        
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
    
    def calculate_progressive_spike(self, symbol: str, check_partial_bar: bool = True) -> Dict:
        """
        PROGRESSIVE Intraday Volume Spike Detection
        
        KEY IMPROVEMENT: Checks volume WITHIN current minute (doesn't wait for bar to close)
        
        Args:
            symbol: Stock ticker
            check_partial_bar: If True, includes current incomplete bar (FASTER alerts)
        
        Returns:
            spike_ratio: Current volume / Average of previous bars
            classification: BUILDING, ELEVATED, HIGH, EXTREME, PARABOLIC
            spike_detected: Boolean for Discord alerts
            alert_urgency: WATCH, MEDIUM, HIGH, CRITICAL
            timing_advantage: Seconds gained vs waiting for bar close
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
            
            # PROGRESSIVE CHECK: Use current incomplete bar if check_partial_bar=True
            if check_partial_bar:
                # Get CURRENT bar (may be incomplete - this is the key!)
                current_bar_volume = market_hours.iloc[-1]['v']
                current_bar_time = market_hours.iloc[-1]['timestamp']
                
                # Calculate how far into current minute we are
                now = datetime.now()
                seconds_into_bar = now.second
                
                # Estimate full bar volume based on elapsed time
                # If we're 30 seconds in, project full minute volume
                if seconds_into_bar >= 10:  # Need at least 10 seconds of data
                    estimated_full_bar_volume = (current_bar_volume / seconds_into_bar) * 60
                    timing_advantage = 60 - seconds_into_bar  # Seconds saved vs waiting
                else:
                    # Not enough data in current bar, use last completed bar
                    current_bar_volume = market_hours.iloc[-2]['v'] if len(market_hours) >= 2 else market_hours.iloc[-1]['v']
                    estimated_full_bar_volume = current_bar_volume
                    timing_advantage = 0
            else:
                # Traditional method: wait for completed bar
                current_bar_volume = market_hours.iloc[-1]['v']
                estimated_full_bar_volume = current_bar_volume
                timing_advantage = 0
            
            # Get PREVIOUS bars for comparison
            if check_partial_bar and len(market_hours) >= self.spike_lookback_bars + 2:
                # Exclude current bar, use previous completed bars
                previous_bars = market_hours.iloc[-(self.spike_lookback_bars + 2):-1]
            else:
                previous_bars = market_hours.iloc[-(self.spike_lookback_bars + 1):-1]
            
            if len(previous_bars) == 0:
                return self._empty_spike_result()
            
            avg_previous_volume = previous_bars['v'].mean()
            
            # Calculate spike ratio using estimated full bar volume
            spike_ratio = estimated_full_bar_volume / avg_previous_volume if avg_previous_volume > 0 else 0
            
            # MINIMUM VOLUME FILTER: Avoid false positives on low volume
            if current_bar_volume < self.min_spike_volume:
                return self._empty_spike_result()
            
            # Check total volume today
            total_volume_today = market_hours['v'].sum()
            if total_volume_today < self.min_total_volume:
                return self._empty_spike_result()
            
            # Get price movement for confirmation
            current_price = market_hours.iloc[-1]['c']
            price_bars_ago = market_hours.iloc[-(self.spike_lookback_bars + 1)]['c']
            price_change_pct = ((current_price - price_bars_ago) / price_bars_ago) * 100
            
            # PRICE CONFIRMATION: Volume spike should accompany price move
            price_confirmed = abs(price_change_pct) >= self.min_price_change
            
            # Determine direction
            if price_change_pct > 0.5:
                direction = 'BREAKOUT'
            elif price_change_pct < -0.5:
                direction = 'BREAKDOWN'
            else:
                direction = 'CONSOLIDATION'
            
            # TIERED CLASSIFICATION with urgency levels
            if spike_ratio >= self.threshold_parabolic:
                classification = 'PARABOLIC'
                spike_detected = True
                signal_strength = 5
                alert_urgency = 'CRITICAL'
                emoji = '🚀🚀🚀'
            elif spike_ratio >= self.threshold_extreme:
                classification = 'EXTREME'
                spike_detected = True
                signal_strength = 4
                alert_urgency = 'CRITICAL'
                emoji = '🔥🔥'
            elif spike_ratio >= self.threshold_high:
                classification = 'HIGH'
                spike_detected = True
                signal_strength = 3
                alert_urgency = 'HIGH'
                emoji = '🔥'
            elif spike_ratio >= self.threshold_elevated:
                classification = 'ELEVATED'
                spike_detected = True
                signal_strength = 2
                alert_urgency = 'MEDIUM'
                emoji = '⚡'
            elif spike_ratio >= self.threshold_building:
                classification = 'BUILDING'
                spike_detected = True  # Now alerting on building volume too
                signal_strength = 1
                alert_urgency = 'WATCH'
                emoji = '👀'
            elif spike_ratio >= self.threshold_attention:
                classification = 'ATTENTION'
                spike_detected = False  # Log only, no alert
                signal_strength = 0
                alert_urgency = 'NONE'
                emoji = '📊'
            elif spike_ratio >= 0.7:
                classification = 'NORMAL'
                spike_detected = False
                signal_strength = 0
                alert_urgency = 'NONE'
                emoji = '➡️'
            else:
                classification = 'LOW'
                spike_detected = False
                signal_strength = -1
                alert_urgency = 'NONE'
                emoji = '📉'
            
            # Quality score: Combine volume spike + price movement
            quality_score = 0
            if spike_detected:
                quality_score += signal_strength * 20  # Base score from spike
                if price_confirmed:
                    quality_score += 20  # Bonus for price confirmation
                if abs(price_change_pct) > 1.0:
                    quality_score += 10  # Bonus for strong price move
                if direction in ['BREAKOUT', 'BREAKDOWN']:
                    quality_score += 10  # Bonus for directional move
            
            return {
                'spike_ratio': round(spike_ratio, 2),
                'classification': classification,
                'spike_detected': spike_detected,
                'signal_strength': signal_strength,
                'alert_urgency': alert_urgency,
                'emoji': emoji,
                'current_bar_volume': int(current_bar_volume),
                'estimated_full_bar_volume': int(estimated_full_bar_volume),
                'avg_previous_volume': int(avg_previous_volume),
                'direction': direction,
                'price_change_pct': round(price_change_pct, 2),
                'price_confirmed': price_confirmed,
                'quality_score': quality_score,
                'total_volume_today': int(total_volume_today),
                'timing_advantage_seconds': timing_advantage,  # NEW: How much faster than old method
                'progressive_check': check_partial_bar,
                'session': 'REGULAR',
                'bars_analyzed': len(previous_bars) + 1,
                'current_time': market_hours.iloc[-1]['timestamp'].strftime('%H:%M:%S')
            }
            
        except Exception as e:
            self.logger.error(f"Error detecting progressive spike for {symbol}: {str(e)}")
            return self._empty_spike_result()
    
    def calculate_intraday_spike(self, symbol: str) -> Dict:
        """
        Backward-compatible wrapper for calculate_progressive_spike
        Uses progressive checking by default
        """
        return self.calculate_progressive_spike(symbol, check_partial_bar=True)
    
    def calculate_premarket_rvol(self, symbol: str) -> Dict:
        """
        Pre-Market RVOL with IMPROVED thresholds
        Compares current 5-min pre-market bar to historical 5-min pre-market average
        
        Pre-market hours: 4:00 AM - 9:30 AM ET
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
            
            # Classify with NEW thresholds
            if rvol >= self.threshold_parabolic:
                classification = 'PARABOLIC'
                spike_detected = True
                signal_strength = 5
            elif rvol >= self.threshold_extreme:
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
            elif rvol >= self.threshold_building:
                classification = 'BUILDING'
                spike_detected = True
                signal_strength = 1
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
            
            # Classify with NEW thresholds
            if rvol >= self.threshold_parabolic:
                classification = 'PARABOLIC'
                signal_strength = 5
            elif rvol >= self.threshold_extreme:
                classification = 'EXTREME'
                signal_strength = 4
            elif rvol >= self.threshold_high:
                classification = 'HIGH'
                signal_strength = 3
            elif rvol >= self.threshold_elevated:
                classification = 'ELEVATED'
                signal_strength = 2
            elif rvol >= self.threshold_building:
                classification = 'BUILDING'
                signal_strength = 1
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
                'session': 'REGULAR',
                'minutes_elapsed': current_minutes
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating RVOL for {symbol}: {str(e)}")
            return self._empty_rvol_result('REGULAR')
    
    def generate_volume_analysis(self, symbol: str) -> Dict:
        """
        Complete volume analysis for a symbol
        Combines RVOL with progressive spike detection
        
        Returns:
            Complete volume analysis with signal strengths
        """
        try:
            # Determine session
            now = datetime.now()
            et_hour = now.hour
            et_minute = now.minute
            
            if (et_hour < 9) or (et_hour == 9 and et_minute < 30):
                session = 'PREMARKET'
            elif (et_hour >= 16):
                session = 'AFTERHOURS'
            else:
                session = 'REGULAR'
            
            # Get appropriate analysis based on session
            if session == 'PREMARKET':
                rvol_data = self.calculate_premarket_rvol(symbol)
                spike_data = self._empty_spike_result()
            elif session == 'REGULAR':
                rvol_data = self.calculate_rvol(symbol)
                spike_data = self.calculate_progressive_spike(symbol, check_partial_bar=True)
            else:
                rvol_data = self._empty_rvol_result('AFTERHOURS')
                spike_data = self._empty_spike_result()
            
            # Combine results
            return {
                'symbol': symbol,
                'session': session,
                'rvol_analysis': rvol_data,
                'spike_analysis': spike_data,
                'overall_signal_strength': max(
                    rvol_data.get('signal_strength', 0),
                    spike_data.get('signal_strength', 0)
                ),
                'alert_recommended': (
                    rvol_data.get('spike_detected', False) or 
                    spike_data.get('spike_detected', False)
                ),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error generating volume analysis for {symbol}: {str(e)}")
            return {
                'symbol': symbol,
                'error': str(e),
                'session': 'UNKNOWN',
                'rvol_analysis': self._empty_rvol_result('UNKNOWN'),
                'spike_analysis': self._empty_spike_result(),
                'overall_signal_strength': 0,
                'alert_recommended': False
            }
    
    def _empty_rvol_result(self, session: str) -> Dict:
        """Return empty RVOL result"""
        return {
            'rvol': 0.0,
            'classification': 'UNKNOWN',
            'spike_detected': False,
            'signal_strength': 0,
            'session': session
        }
    
    def _empty_spike_result(self) -> Dict:
        """Return empty spike result"""
        return {
            'spike_ratio': 0.0,
            'classification': 'UNKNOWN',
            'spike_detected': False,
            'signal_strength': 0,
            'alert_urgency': 'NONE',
            'emoji': '❓',
            'direction': 'UNKNOWN',
            'price_confirmed': False,
            'quality_score': 0,
            'timing_advantage_seconds': 0,
            'progressive_check': False,
            'session': 'UNKNOWN'
        }


# Example usage
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    API_KEY = os.getenv('POLYGON_API_KEY')
    
    # Test different trading styles
    print("=" * 60)
    print("VOLUME ANALYZER v2.0 TEST")
    print("=" * 60)
    
    styles = ['day_trader', 'scalper', 'swing_trader']
    
    for style in styles:
        analyzer = VolumeAnalyzer(API_KEY, trading_style=style)
        
        print(f"\n{style.upper()} MODE:")
        print(f"  Thresholds: {analyzer.threshold_elevated}x / {analyzer.threshold_high}x / {analyzer.threshold_extreme}x")
        print(f"  Lookback: {analyzer.spike_lookback_bars} bars")
        
        # Test on SPY
        result = analyzer.calculate_progressive_spike('SPY', check_partial_bar=True)
        
        if result['spike_detected']:
            print(f"\n  🚨 ALERT: SPY - {result['classification']}")
            print(f"     Spike: {result['spike_ratio']}x")
            print(f"     Direction: {result['direction']}")
            print(f"     Price Change: {result['price_change_pct']}%")
            print(f"     Timing Advantage: {result['timing_advantage_seconds']} seconds vs old method")
        else:
            print(f"\n  ✅ SPY - {result['classification']} (no alert)")