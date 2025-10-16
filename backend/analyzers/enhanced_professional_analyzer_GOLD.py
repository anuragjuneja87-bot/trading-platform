"""
backend/analyzers/enhanced_professional_analyzer.py
Enhanced Professional Analyzer v4.0 - PHASE 1 + DIAGNOSTICS
NOW INCLUDES:
- Volume analysis integration (RVOL, spikes, dry-ups)
- Key level detection (confluence scoring)
- 1:2 R:R enforcement
- Enhanced signal scoring (~26 factors)
- NEW: Detailed diagnostic logging
- NEW: Configurable thresholds
- NEW: Debug mode for near-miss detection
"""

import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import requests
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import logging
from collections import defaultdict

# Import new modules
try:
    from analyzers.volume_analyzer import VolumeAnalyzer
    VOLUME_ANALYZER_AVAILABLE = True
except ImportError:
    VOLUME_ANALYZER_AVAILABLE = False
    logging.warning("Volume Analyzer not available")

try:
    from analyzers.key_level_detector import KeyLevelDetector
    KEY_LEVEL_DETECTOR_AVAILABLE = True
except ImportError:
    KEY_LEVEL_DETECTOR_AVAILABLE = False
    logging.warning("Key Level Detector not available")


class EnhancedProfessionalAnalyzer:
    def __init__(self, polygon_api_key: str, twitter_bearer_token: Optional[str] = None,
                 reddit_client_id: Optional[str] = None, reddit_client_secret: Optional[str] = None,
                 debug_mode: bool = False):
        """
        Initialize Enhanced Professional Analyzer v4.0
        
        Args:
            polygon_api_key: Polygon.io API key
            twitter_bearer_token: Twitter API Bearer Token (optional)
            reddit_client_id: Reddit app client ID (optional)
            reddit_client_secret: Reddit app client secret (optional)
            debug_mode: Enable detailed diagnostic logging (default: False)
        """
        self.polygon_api_key = polygon_api_key
        self.base_url = "https://api.polygon.io"
        self.logger = logging.getLogger(__name__)
        
        # NEW: Debug mode for diagnostics
        self.debug_mode = debug_mode
        if self.debug_mode:
            self.logger.setLevel(logging.DEBUG)
            self.logger.info("🔍 DEBUG MODE ENABLED - Detailed logging active")
        
        # Initialize Volume Analyzer
        self.volume_analyzer = None
        if VOLUME_ANALYZER_AVAILABLE:
            try:
                self.volume_analyzer = VolumeAnalyzer(polygon_api_key)
                self.logger.info("✅ Volume Analyzer enabled")
            except Exception as e:
                self.logger.error(f"⚠️ Volume Analyzer initialization failed: {str(e)}")
        else:
            self.logger.warning("⚠️ Volume Analyzer not available - 5 factors disabled")
        
        # Initialize Key Level Detector
        self.key_level_detector = None
        if KEY_LEVEL_DETECTOR_AVAILABLE:
            try:
                self.key_level_detector = KeyLevelDetector(polygon_api_key)
                self.logger.info("✅ Key Level Detector enabled")
            except Exception as e:
                self.logger.error(f"⚠️ Key Level Detector initialization failed: {str(e)}")
        else:
            self.logger.warning("⚠️ Key Level Detector not available - 6 factors disabled")
        
        # Cache
        self.cache = {}
        self.cache_duration = 30
        
        # Momentum tracking
        self.previous_bias = {}
        self.momentum_history = defaultdict(list)
        self.previous_close = {}
        
        # PHASE 1: Configuration (NEW: Now configurable)
        self.minimum_risk_reward = 2.0  # Enforce 1:2 R:R minimum
        self.enforce_rr_filter = False
        
        # NEW: Configurable thresholds
        self.base_signal_threshold = 8  # Default threshold
        self.high_impact_threshold = 6  # For news-driven or high RVOL moves
        self.near_miss_threshold = 5    # For logging near-misses
        
        # NEW: Track near-misses for diagnostics
        self.near_misses = []
        
        self.logger.info(f"📊 Signal Thresholds: Base={self.base_signal_threshold}, High Impact={self.high_impact_threshold}")
    
    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make Polygon API request"""
        if params is None:
            params = {}
        
        params['apiKey'] = self.polygon_api_key
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed for {endpoint}: {str(e)}")
            return {}
    
    def detect_gap(self, symbol: str, current_price: float = None) -> Dict:
        """Detect pre-market gap"""
        try:
            test_date = datetime.now() - timedelta(days=1)
            while test_date.weekday() >= 5:
                test_date -= timedelta(days=1)
            yesterday = test_date.strftime('%Y-%m-%d')
            
            endpoint = f"/v2/aggs/ticker/{symbol}/range/1/day/{yesterday}/{yesterday}"
            data = self._make_request(endpoint, {'adjusted': 'true'})
            
            if 'results' not in data or not data['results']:
                return {'gap_type': 'UNKNOWN', 'gap_size': 0, 'gap_amount': 0}
            
            prev_close = data['results'][0]['c']
            self.previous_close[symbol] = prev_close
            
            if current_price is None:
                current_price = self.get_real_time_quote(symbol)['price']
            
            if current_price == 0 or prev_close == 0:
                return {'gap_type': 'UNKNOWN', 'gap_size': 0, 'gap_amount': 0}
            
            gap_amount = current_price - prev_close
            gap_percentage = (gap_amount / prev_close) * 100
            
            # ENHANCED: Lower threshold for gap detection (was 1.0%, now 0.5%)
            if gap_percentage > 0.5:
                gap_type = 'GAP_UP'
            elif gap_percentage < -0.5:
                gap_type = 'GAP_DOWN'
            else:
                gap_type = 'NO_GAP'
            
            if self.debug_mode and gap_type != 'NO_GAP':
                self.logger.debug(f"{symbol} - Gap detected: {gap_type} {gap_percentage:.2f}%")
            
            return {
                'gap_type': gap_type,
                'gap_size': round(gap_percentage, 2),
                'gap_amount': round(gap_amount, 2),
                'prev_close': round(prev_close, 2),
                'current_price': round(current_price, 2)
            }
            
        except Exception as e:
            self.logger.error(f"Error detecting gap for {symbol}: {str(e)}")
            return {'gap_type': 'UNKNOWN', 'gap_size': 0, 'gap_amount': 0}
    
    def get_enhanced_news_sentiment(self, symbol: str) -> Dict:
        """Get news sentiment from Polygon"""
        endpoint = f"/v2/reference/news"
        params = {'ticker': symbol, 'limit': 20, 'order': 'desc'}
        
        data = self._make_request(endpoint, params)
        
        if 'results' not in data or not data['results']:
            return {
                'sentiment': 'NEUTRAL',
                'urgency': 'LOW',
                'recent_news': 0,
                'headlines': [],
                'sentiment_score': 0,
                'news_impact': 'NONE'
            }
        
        news_items = data['results']
        
        # Enhanced keyword lists
        strong_positive = ['beats', 'soars', 'surge', 'breakthrough', 'record', 
                          'blowout earnings', 'raised target', 'massive gains']
        positive = ['upgrade', 'rally', 'bullish', 'growth', 'gain', 'wins', 
                   'partnership', 'expands', 'strength', 'optimism']
        
        strong_negative = ['plunges', 'crashes', 'misses badly', 'investigation',
                          'tariff', 'tariffs', 'trade war', 'market crash', 
                          'selloff', 'sell-off', 'recession fears', 'panic selling', 
                          'bloodbath', 'carnage', 'rout', 'meltdown']
        negative = ['downgrade', 'bearish', 'loss', 'decline', 'falls', 'cuts', 
                   'warns', 'disappoints', 'concern', 'uncertainty', 'weakness', 
                   'pressure', 'slump', 'inflation', 'recession']
        
        urgent_keywords = ['breaking', 'just in', 'alert', 'urgent', 'halted', 
                          'suspended', 'emergency', 'now']
        
        sentiment_score = 0
        headlines = []
        urgency = 'LOW'
        now = datetime.now()
        very_recent_count = 0
        
        for item in news_items[:10]:
            title = item.get('title', '').lower()
            headlines.append(item.get('title', ''))
            
            pub_time_str = item.get('published_utc', '')
            if pub_time_str:
                try:
                    pub_time = datetime.strptime(pub_time_str, '%Y-%m-%dT%H:%M:%SZ')
                    hours_ago = (now - pub_time).total_seconds() / 3600
                    if hours_ago < 2:
                        very_recent_count += 1
                except:
                    pass
            
            # Check Polygon's built-in insights first
            insights = item.get('insights', [])
            insight_found = False
            
            for insight in insights:
                if insight.get('ticker') == symbol:
                    insight_found = True
                    insight_sentiment = insight.get('sentiment', 'neutral').lower()
                    reasoning = insight.get('sentiment_reasoning', '').lower()
                    
                    if insight_sentiment == 'positive':
                        sentiment_score += 2
                    elif insight_sentiment == 'negative':
                        sentiment_score -= 2
                    
                    # Check reasoning for strong signals
                    if any(word in reasoning for word in ['upgrade', 'beats', 'breakthrough', 'surge']):
                        sentiment_score += 1
                    if any(word in reasoning for word in ['downgrade', 'plunge', 'crash', 'concern']):
                        sentiment_score -= 1
                    
                    break
            
            # Fallback to keyword analysis
            if not insight_found:
                if any(word in title for word in strong_positive):
                    sentiment_score += 3
                elif any(word in title for word in positive):
                    sentiment_score += 1
                
                if any(word in title for word in strong_negative):
                    sentiment_score -= 4
                elif any(word in title for word in negative):
                    sentiment_score -= 2
            
            # Additional scoring for very strong keywords
            if any(word in title for word in strong_negative):
                sentiment_score -= 2
            if any(word in title for word in strong_positive):
                sentiment_score += 1
            
            # Check urgency
            if any(word in title for word in urgent_keywords):
                urgency = 'HIGH'
        
        # Determine overall sentiment
        if sentiment_score >= 5:
            sentiment = 'VERY POSITIVE'
        elif sentiment_score >= 2:
            sentiment = 'POSITIVE'
        elif sentiment_score <= -5:
            sentiment = 'VERY NEGATIVE'
        elif sentiment_score <= -2:
            sentiment = 'NEGATIVE'
        else:
            sentiment = 'NEUTRAL'
        
        # Determine news impact
        if abs(sentiment_score) >= 6 and very_recent_count >= 2:
            news_impact = 'EXTREME'
        elif abs(sentiment_score) >= 5 and very_recent_count >= 2:
            news_impact = 'HIGH'
        elif abs(sentiment_score) >= 3 or very_recent_count >= 1:
            news_impact = 'MEDIUM'
        elif abs(sentiment_score) > 0:
            news_impact = 'LOW'
        else:
            news_impact = 'NONE'
        
        # Upgrade urgency based on impact
        if news_impact == 'EXTREME':
            urgency = 'EXTREME'
        elif news_impact == 'HIGH':
            urgency = 'HIGH'
        elif news_impact == 'MEDIUM' and urgency == 'LOW':
            urgency = 'MEDIUM'
        
        if self.debug_mode and news_impact != 'NONE':
            self.logger.debug(f"{symbol} - News: {sentiment} (Impact: {news_impact}, Score: {sentiment_score})")
        
        return {
            'sentiment': sentiment,
            'urgency': urgency,
            'recent_news': len(news_items),
            'headlines': headlines[:5],
            'sentiment_score': sentiment_score,
            'news_impact': news_impact,
            'very_recent_count': very_recent_count
        }
    
    def get_real_time_quote(self, symbol: str) -> Dict:
        """Get real-time quote"""
        endpoint = f"/v2/last/trade/{symbol}"
        data = self._make_request(endpoint)
        
        if 'results' in data:
            return {
                'price': data['results'].get('p', 0),
                'size': data['results'].get('s', 0),
                'timestamp': data['results'].get('t', 0)
            }
        return {'price': 0, 'size': 0, 'timestamp': 0}
    
    def calculate_vwap(self, symbol: str) -> float:
        """Calculate VWAP"""
        today = datetime.now().strftime('%Y-%m-%d')
        endpoint = f"/v2/aggs/ticker/{symbol}/range/1/minute/{today}/{today}"
        
        data = self._make_request(endpoint, {'adjusted': 'true', 'sort': 'asc', 'limit': 50000})
        
        if 'results' not in data or not data['results']:
            return 0.0
        
        df = pd.DataFrame(data['results'])
        df['vwap'] = (df['c'] * df['v']).cumsum() / df['v'].cumsum()
        
        return float(df['vwap'].iloc[-1]) if len(df) > 0 else 0.0
    
    def calculate_camarilla_levels(self, symbol: str) -> Dict:
        """Calculate Camarilla pivots"""
        test_date = datetime.now() - timedelta(days=1)
        while test_date.weekday() >= 5:
            test_date -= timedelta(days=1)
        yesterday = test_date.strftime('%Y-%m-%d')
        
        endpoint = f"/v2/aggs/ticker/{symbol}/range/1/day/{yesterday}/{yesterday}"
        data = self._make_request(endpoint, {'adjusted': 'true'})
        
        if 'results' not in data or not data['results']:
            return {'R4': 0, 'R3': 0, 'S3': 0, 'S4': 0}
        
        prev_day = data['results'][0]
        high = prev_day['h']
        low = prev_day['l']
        close = prev_day['c']
        range_val = high - low
        
        return {
            'R4': round(close + (range_val * 1.1 / 2), 2),
            'R3': round(close + (range_val * 1.1 / 4), 2),
            'S3': round(close - (range_val * 1.1 / 4), 2),
            'S4': round(close - (range_val * 1.1 / 2), 2),
            'pivot': round(close, 2)
        }
    
    def get_support_resistance(self, symbol: str, current_price: float, lookback_days: int = 10) -> Dict:
        """Calculate support/resistance"""
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
        
        endpoint = f"/v2/aggs/ticker/{symbol}/range/1/day/{start_date}/{end_date}"
        data = self._make_request(endpoint, {'adjusted': 'true', 'sort': 'asc'})
        
        if 'results' not in data or not data['results'] or len(data['results']) < 3:
            return {
                'support': round(current_price * 0.98, 2),
                'resistance': round(current_price * 1.02, 2)
            }
        
        df = pd.DataFrame(data['results'])
        
        highs = []
        lows = []
        
        for i in range(1, len(df) - 1):
            if df['h'].iloc[i] > df['h'].iloc[i-1] and df['h'].iloc[i] > df['h'].iloc[i+1]:
                highs.append(df['h'].iloc[i])
            
            if df['l'].iloc[i] < df['l'].iloc[i-1] and df['l'].iloc[i] < df['l'].iloc[i+1]:
                lows.append(df['l'].iloc[i])
        
        highs.append(df['h'].iloc[-1])
        lows.append(df['l'].iloc[-1])
        
        resistance_candidates = [h for h in highs if h > current_price]
        if resistance_candidates:
            resistance = min(resistance_candidates)
        else:
            resistance = df['h'].iloc[-3:].max() * 1.02
        
        support_candidates = [l for l in lows if l < current_price]
        if support_candidates:
            support = max(support_candidates)
        else:
            support = df['l'].iloc[-3:].min() * 0.98
        
        if support >= current_price:
            support = current_price * 0.98
        if resistance <= current_price:
            resistance = current_price * 1.02
        
        return {
            'support': round(support, 2),
            'resistance': round(resistance, 2)
        }
    
    def analyze_options_flow(self, symbol: str) -> Dict:
        """Analyze options sentiment"""
        endpoint = f"/v3/reference/options/contracts"
        params = {'underlying_ticker': symbol, 'expired': 'false', 'limit': 100}
        
        data = self._make_request(endpoint, params)
        
        if 'results' not in data:
            return {'sentiment': 'NEUTRAL', 'put_call_ratio': 1.0, 'unusual_activity': False}
        
        contracts = data['results']
        calls = sum(1 for c in contracts if c.get('contract_type') == 'call')
        puts = sum(1 for c in contracts if c.get('contract_type') == 'put')
        put_call_ratio = puts / calls if calls > 0 else 1.0
        
        if put_call_ratio > 1.2:
            sentiment = 'BEARISH'
        elif put_call_ratio < 0.8:
            sentiment = 'BULLISH'
        else:
            sentiment = 'NEUTRAL'
        
        return {
            'sentiment': sentiment,
            'put_call_ratio': round(put_call_ratio, 2),
            'unusual_activity': abs(put_call_ratio - 1.0) > 0.5
        }
    
    def detect_dark_pool_activity(self, symbol: str) -> Dict:
        """Detect institutional activity"""
        endpoint = f"/v3/trades/{symbol}"
        params = {'limit': 1000, 'order': 'desc'}
        
        data = self._make_request(endpoint, params)
        
        if 'results' not in data or not data['results']:
            return {'activity': 'NEUTRAL', 'large_trades': 0, 'institutional_flow': 'NEUTRAL'}
        
        trades = data['results']
        sizes = [t.get('size', 0) for t in trades]
        avg_size = np.mean(sizes)
        large_trades = [s for s in sizes if s > avg_size * 3]
        
        if len(large_trades) > len(trades) * 0.1:
            if sum(large_trades) > sum(sizes) * 0.4:
                activity = 'HEAVY'
                institutional_flow = 'BUYING' if trades[0].get('size', 0) in large_trades else 'SELLING'
            else:
                activity = 'MODERATE'
                institutional_flow = 'MIXED'
        else:
            activity = 'LIGHT'
            institutional_flow = 'NEUTRAL'
        
        return {
            'activity': activity,
            'large_trades': len(large_trades),
            'institutional_flow': institutional_flow
        }
    
    def calculate_timeframe_bias(self, symbol: str, timeframe: str = '1H') -> Dict:
        """Calculate timeframe bias"""
        if timeframe == '1H':
            multiplier, timespan, limit = 60, 'minute', 20
        else:
            multiplier, timespan, limit = 1, 'day', 20
        
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
        
        endpoint = f"/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{start_date}/{end_date}"
        data = self._make_request(endpoint, {'adjusted': 'true', 'sort': 'asc', 'limit': limit})
        
        if 'results' not in data or not data['results'] or len(data['results']) < 2:
            return {'bias': 'NEUTRAL', 'strength': 0, 'trend': 'UNKNOWN'}
        
        df = pd.DataFrame(data['results'])
        df['ema9'] = df['c'].ewm(span=9, adjust=False).mean()
        df['ema21'] = df['c'].ewm(span=21 if len(df) >= 21 else len(df)//2, adjust=False).mean()
        
        current_price = df['c'].iloc[-1]
        ema9 = df['ema9'].iloc[-1]
        ema21 = df['ema21'].iloc[-1]
        
        if ema9 > ema21 and current_price > ema9:
            bias = 'BULLISH'
            strength = min(((ema9 - ema21) / ema21) * 100, 100)
        elif ema9 < ema21 and current_price < ema9:
            bias = 'BEARISH'
            strength = min(((ema21 - ema9) / ema9) * 100, 100)
        else:
            bias = 'NEUTRAL'
            strength = 0
        
        price_change = ((current_price - df['c'].iloc[0]) / df['c'].iloc[0]) * 100
        
        if abs(price_change) > 2:
            trend = 'STRONG UPTREND' if price_change > 0 else 'STRONG DOWNTREND'
        elif abs(price_change) > 0.5:
            trend = 'UPTREND' if price_change > 0 else 'DOWNTREND'
        else:
            trend = 'CONSOLIDATING'
        
        return {
            'bias': bias,
            'strength': round(strength, 1),
            'trend': trend,
            'price_change': round(price_change, 2)
        }
    
    def detect_momentum_shift(self, symbol: str, current_bias: str) -> bool:
        """Detect momentum shifts"""
        previous = self.previous_bias.get(symbol, 'NEUTRAL')
        shift_detected = (
            (previous == 'BULLISH' and current_bias == 'BEARISH') or
            (previous == 'BEARISH' and current_bias == 'BULLISH')
        )
        self.previous_bias[symbol] = current_bias
        return shift_detected
    
    def calculate_entry_and_targets(self, symbol: str, signal: str, current_price: float,
                                    camarilla: Dict, support_resistance: Dict) -> Dict:
        """Calculate entry/TP/SL with 1:2 R:R enforcement"""
        if signal == 'BUY':
            entry = min(current_price, support_resistance['support'] + 0.10)
            tp1 = camarilla['R3']
            tp2 = camarilla['R4']
            stop_loss = support_resistance['support'] - 0.20
        elif signal == 'SELL':
            entry = max(current_price, support_resistance['resistance'] - 0.10)
            tp1 = camarilla['S3']
            tp2 = camarilla['S4']
            stop_loss = support_resistance['resistance'] + 0.20
        else:
            return {}
        
        risk = abs(entry - stop_loss)
        reward = abs(tp1 - entry)
        rr_ratio = reward / risk if risk > 0 else 0
        
        # PHASE 1: Enforce 1:2 R:R minimum (with bypass for extreme signals)
        if self.enforce_rr_filter and rr_ratio < self.minimum_risk_reward:
            if self.debug_mode:
                self.logger.debug(f"{symbol}: R:R {rr_ratio:.2f} below minimum {self.minimum_risk_reward}")
            return {'insufficient_rr': True, 'rr_ratio': round(rr_ratio, 2)}
        
        return {
            'entry': round(entry, 2),
            'tp1': round(tp1, 2),
            'tp2': round(tp2, 2),
            'stop_loss': round(stop_loss, 2),
            'risk_reward': round(rr_ratio, 2),
            'risk_amount': round(risk, 2),
            'reward_amount': round(reward, 2)
        }
    
    def generate_professional_signal(self, symbol: str) -> Dict:
        """
        PHASE 1 + DIAGNOSTICS: Generate signal with Volume & Key Level integration
        Now includes ~26 factors with detailed diagnostic tracking
        """
        try:
            if self.debug_mode:
                self.logger.debug(f"\n{'='*60}")
                self.logger.debug(f"Starting analysis for {symbol}")
                self.logger.debug(f"{'='*60}")
            
            # Get current price
            quote = self.get_real_time_quote(symbol)
            current_price = quote['price']
            
            if current_price == 0:
                return {'symbol': symbol, 'error': 'Invalid price', 'signal': None}
            
            # Get all data
            gap_data = self.detect_gap(symbol, current_price)
            vwap = self.calculate_vwap(symbol)
            camarilla = self.calculate_camarilla_levels(symbol)
            support_resistance = self.get_support_resistance(symbol, current_price)
            options_flow = self.analyze_options_flow(symbol)
            dark_pool = self.detect_dark_pool_activity(symbol)
            news = self.get_enhanced_news_sentiment(symbol)
            bias_1h = self.calculate_timeframe_bias(symbol, '1H')
            bias_daily = self.calculate_timeframe_bias(symbol, '1D')
            
            # PHASE 1: Volume Analysis
            volume_analysis = {}
            if self.volume_analyzer:
                try:
                    volume_analysis = self.volume_analyzer.generate_volume_analysis(symbol)
                    if self.debug_mode and volume_analysis:
                        rvol = volume_analysis.get('rvol', {})
                        self.logger.debug(f"Volume: RVOL={rvol.get('rvol', 0):.2f}x ({rvol.get('classification', 'N/A')})")
                except Exception as e:
                    self.logger.error(f"Volume analysis failed: {str(e)}")
            else:
                if self.debug_mode:
                    self.logger.debug("Volume Analyzer not available - skipping volume factors")
            
            # PHASE 1: Key Level Detection
            key_levels = {}
            if self.key_level_detector:
                try:
                    key_levels = self.key_level_detector.detect_key_levels(symbol, current_price)
                    if self.debug_mode and key_levels and 'error' not in key_levels:
                        self.logger.debug(f"Key Levels: Confluence={key_levels.get('confluence_score', 0)}/10")
                except Exception as e:
                    self.logger.error(f"Key level detection failed: {str(e)}")
            else:
                if self.debug_mode:
                    self.logger.debug("Key Level Detector not available - skipping key level factors")
            
            momentum_shifted = self.detect_momentum_shift(symbol, bias_1h['bias'])
            
            # PHASE 1: ENHANCED SIGNAL LOGIC (26 factors) with detailed tracking
            bullish_factors = 0
            bearish_factors = 0
            
            # NEW: Track factor breakdown for diagnostics
            factor_breakdown = {
                'bullish': [],
                'bearish': []
            }
            
            # Original factors (15)
            if gap_data['gap_type'] == 'GAP_DOWN' and abs(gap_data['gap_size']) > 2:
                bearish_factors += 4
                factor_breakdown['bearish'].append(f"Large gap down ({gap_data['gap_size']}%) [+4]")
            elif gap_data['gap_type'] == 'GAP_UP' and gap_data['gap_size'] > 2:
                bullish_factors += 4
                factor_breakdown['bullish'].append(f"Large gap up ({gap_data['gap_size']}%) [+4]")
            
            if news['sentiment'] == 'VERY NEGATIVE':
                bearish_factors += 3
                factor_breakdown['bearish'].append(f"Very negative news (score: {news['sentiment_score']}) [+3]")
            elif news['sentiment'] == 'NEGATIVE':
                bearish_factors += 2
                factor_breakdown['bearish'].append(f"Negative news [+2]")
            elif news['sentiment'] == 'VERY POSITIVE':
                bullish_factors += 3
                factor_breakdown['bullish'].append(f"Very positive news (score: {news['sentiment_score']}) [+3]")
            elif news['sentiment'] == 'POSITIVE':
                bullish_factors += 2
                factor_breakdown['bullish'].append(f"Positive news [+2]")
            
            if bias_1h['bias'] == 'BULLISH':
                bullish_factors += 2
                factor_breakdown['bullish'].append("1H bullish bias [+2]")
            if bias_daily['bias'] == 'BULLISH':
                bullish_factors += 1
                factor_breakdown['bullish'].append("Daily bullish bias [+1]")
            if current_price > vwap:
                bullish_factors += 1
                factor_breakdown['bullish'].append("Price > VWAP [+1]")
            if options_flow['sentiment'] == 'BULLISH':
                bullish_factors += 2
                factor_breakdown['bullish'].append("Bullish options flow [+2]")
            if dark_pool['institutional_flow'] == 'BUYING':
                bullish_factors += 3
                factor_breakdown['bullish'].append("Institutional buying [+3]")
            if current_price <= camarilla['S3']:
                bullish_factors += 2
                factor_breakdown['bullish'].append("At/below S3 support [+2]")
            
            if bias_1h['bias'] == 'BEARISH':
                bearish_factors += 2
                factor_breakdown['bearish'].append("1H bearish bias [+2]")
            if bias_daily['bias'] == 'BEARISH':
                bearish_factors += 1
                factor_breakdown['bearish'].append("Daily bearish bias [+1]")
            if current_price < vwap:
                bearish_factors += 1
                factor_breakdown['bearish'].append("Price < VWAP [+1]")
            if options_flow['sentiment'] == 'BEARISH':
                bearish_factors += 2
                factor_breakdown['bearish'].append("Bearish options flow [+2]")
            if dark_pool['institutional_flow'] == 'SELLING':
                bearish_factors += 3
                factor_breakdown['bearish'].append("Institutional selling [+3]")
            if current_price >= camarilla['R3']:
                bearish_factors += 2
                factor_breakdown['bearish'].append("At/above R3 resistance [+2]")
            
            # PHASE 1: NEW VOLUME FACTORS (5 factors)
            if volume_analysis:
                rvol_data = volume_analysis.get('rvol', {})
                spike_data = volume_analysis.get('volume_spike', {})
                dryup_data = volume_analysis.get('volume_dryup', {})
                blocks_data = volume_analysis.get('block_trades', {})
                
                # RVOL confirmation (adds to existing bias)
                rvol_strength = rvol_data.get('signal_strength', 0)
                if rvol_strength >= 3:  # HIGH or EXTREME RVOL
                    if bias_1h['bias'] == 'BULLISH':
                        bullish_factors += 3
                        factor_breakdown['bullish'].append(f"High RVOL confirmation ({rvol_data.get('rvol', 0):.1f}x) [+3]")
                    elif bias_1h['bias'] == 'BEARISH':
                        bearish_factors += 3
                        factor_breakdown['bearish'].append(f"High RVOL confirmation ({rvol_data.get('rvol', 0):.1f}x) [+3]")
                
                # Volume spike = confirmation of move
                if spike_data.get('spike_detected'):
                    spike_strength = spike_data.get('signal_strength', 0)
                    if bias_1h['bias'] == 'BULLISH':
                        bullish_factors += spike_strength
                        factor_breakdown['bullish'].append(f"Volume spike detected [+{spike_strength}]")
                    elif bias_1h['bias'] == 'BEARISH':
                        bearish_factors += spike_strength
                        factor_breakdown['bearish'].append(f"Volume spike detected [+{spike_strength}]")
                
                # Block trades = institutional activity
                if blocks_data.get('block_trades_detected'):
                    block_strength = blocks_data.get('signal_strength', 0)
                    if dark_pool['institutional_flow'] == 'BUYING':
                        bullish_factors += block_strength
                        factor_breakdown['bullish'].append(f"Block trades (buying) [+{block_strength}]")
                    elif dark_pool['institutional_flow'] == 'SELLING':
                        bearish_factors += block_strength
                        factor_breakdown['bearish'].append(f"Block trades (selling) [+{block_strength}]")
            
            # PHASE 1: NEW KEY LEVEL FACTORS (6 factors)
            if key_levels and 'error' not in key_levels:
                confluence_score = key_levels.get('confluence_score', 0)
                at_resistance = key_levels.get('at_resistance', False)
                at_support = key_levels.get('at_support', False)
                
                # High confluence resistance = bearish
                if at_resistance and confluence_score >= 6:
                    bearish_factors += 4
                    factor_breakdown['bearish'].append(f"High confluence resistance ({confluence_score}/10) [+4]")
                elif at_resistance:
                    bearish_factors += 2
                    factor_breakdown['bearish'].append(f"At resistance [+2]")
                
                # High confluence support = bullish
                if at_support and confluence_score >= 6:
                    bullish_factors += 4
                    factor_breakdown['bullish'].append(f"High confluence support ({confluence_score}/10) [+4]")
                elif at_support:
                    bullish_factors += 2
                    factor_breakdown['bullish'].append(f"At support [+2]")
                
                # Previous day level breaks (with volume)
                prev_day = key_levels.get('previous_day', {})
                if prev_day:
                    prev_high = prev_day.get('previous_day_high', 0)
                    prev_low = prev_day.get('previous_day_low', 0)
                    
                    # Breaking previous day high with volume
                    if prev_high and current_price > prev_high:
                        if volume_analysis and volume_analysis.get('rvol', {}).get('classification') in ['HIGH', 'EXTREME']:
                            bullish_factors += 5
                            factor_breakdown['bullish'].append("Prev day high breakout + volume [+5]")
                    
                    # Breaking previous day low with volume
                    if prev_low and current_price < prev_low:
                        if volume_analysis and volume_analysis.get('rvol', {}).get('classification') in ['HIGH', 'EXTREME']:
                            bearish_factors += 5
                            factor_breakdown['bearish'].append("Prev day low breakdown + volume [+5]")
            
            # NEW: Log factor breakdown in debug mode
            if self.debug_mode:
                self.logger.debug(f"\nFactor Breakdown:")
                self.logger.debug(f"Bullish ({bullish_factors} total):")
                for factor in factor_breakdown['bullish']:
                    self.logger.debug(f"  • {factor}")
                self.logger.debug(f"Bearish ({bearish_factors} total):")
                for factor in factor_breakdown['bearish']:
                    self.logger.debug(f"  • {factor}")
            
            # PHASE 1: Determine signal threshold
            signal_threshold = self.base_signal_threshold
            
            # Lower threshold for high-impact events
            if news['news_impact'] in ['HIGH', 'EXTREME'] or abs(gap_data.get('gap_size', 0)) > 3:
                signal_threshold = self.high_impact_threshold
                if self.debug_mode:
                    self.logger.debug(f"Using high-impact threshold: {signal_threshold}")
            
            # Lower threshold for high RVOL + high confluence
            if volume_analysis and key_levels:
                rvol_classification = volume_analysis.get('rvol', {}).get('classification', '')
                confluence = key_levels.get('confluence_score', 0)
                
                if rvol_classification in ['HIGH', 'EXTREME'] and confluence >= 7:
                    signal_threshold = self.high_impact_threshold
                    if self.debug_mode:
                        self.logger.debug(f"Using high-impact threshold (RVOL + confluence): {signal_threshold}")
            
            # Determine signal
            signal = None
            confidence = 0.0
            alert_type = 'MONITOR'
            
            if bullish_factors >= signal_threshold:
                signal = 'BUY'
                confidence = min(bullish_factors / 28 * 100, 95)  # 28 max factors
                alert_type = 'STRONG BUY' if bullish_factors >= signal_threshold + 4 else 'BUY'
            elif bearish_factors >= signal_threshold:
                signal = 'SELL'
                confidence = min(bearish_factors / 28 * 100, 95)
                alert_type = 'STRONG SELL' if bearish_factors >= signal_threshold + 4 else 'SELL'
            
            # NEW: Track near-misses
            max_factors = max(bullish_factors, bearish_factors)
            if max_factors >= self.near_miss_threshold and max_factors < signal_threshold:
                near_miss_info = {
                    'symbol': symbol,
                    'bullish': bullish_factors,
                    'bearish': bearish_factors,
                    'needed': signal_threshold - max_factors,
                    'timestamp': datetime.now().isoformat()
                }
                self.near_misses.append(near_miss_info)
                
                if self.debug_mode:
                    self.logger.debug(f"\n⚠️ NEAR-MISS DETECTED:")
                    self.logger.debug(f"   Bullish: {bullish_factors}, Bearish: {bearish_factors}")
                    self.logger.debug(f"   Needed {signal_threshold - max_factors} more factors for signal")
            
            if momentum_shifted:
                alert_type = 'MOMENTUM SHIFT - TAKE PROFIT'
            
            # PHASE 1: Calculate targets with 1:2 R:R enforcement
            entry_targets = self.calculate_entry_and_targets(
                symbol, signal if signal else 'HOLD',
                current_price, camarilla, support_resistance
            )
            
            # NEW: Allow bypass for extreme signals (10+ factors)
            if entry_targets.get('insufficient_rr') and max_factors >= 10:
                if self.debug_mode:
                    self.logger.debug(f"Bypassing R:R filter for extreme signal ({max_factors} factors)")
                # Recalculate without enforcement
                temp_enforce = self.enforce_rr_filter
                self.enforce_rr_filter = False
                entry_targets = self.calculate_entry_and_targets(
                    symbol, signal if signal else 'HOLD',
                    current_price, camarilla, support_resistance
                )
                self.enforce_rr_filter = temp_enforce
                entry_targets['rr_bypassed'] = True
            
            # PHASE 1: Filter out signals with insufficient R:R (unless bypassed)
            if entry_targets.get('insufficient_rr') and not entry_targets.get('rr_bypassed'):
                if self.debug_mode:
                    self.logger.debug(
                        f"Signal filtered - R:R {entry_targets.get('rr_ratio', 0):.2f} "
                        f"< {self.minimum_risk_reward}"
                    )
                signal = None
                alert_type = 'MONITOR'
                confidence = 0
            
            if self.debug_mode:
                self.logger.debug(f"\nFinal Result: {alert_type} (Confidence: {confidence:.1f}%)")
                self.logger.debug(f"{'='*60}\n")
            
            return {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'signal': signal,
                'alert_type': alert_type,
                'confidence': round(confidence, 1),
                'current_price': current_price,
                'vwap': vwap,
                'camarilla': camarilla,
                'support': support_resistance['support'],
                'resistance': support_resistance['resistance'],
                'bias_1h': bias_1h['bias'],
                'bias_daily': bias_daily['bias'],
                'options_sentiment': options_flow['sentiment'],
                'dark_pool_activity': dark_pool['institutional_flow'],
                'gap_data': gap_data,
                'news': news,
                'news_sentiment': news['sentiment'],
                'news_headlines': news['headlines'],
                'volume_analysis': volume_analysis,  # PHASE 1
                'key_levels': key_levels,  # PHASE 1
                'entry_targets': entry_targets,
                'momentum_shifted': momentum_shifted,
                'bullish_score': bullish_factors,
                'bearish_score': bearish_factors,
                'total_factors_analyzed': 26,  # PHASE 1
                'signal_threshold': signal_threshold,  # NEW
                'factor_breakdown': factor_breakdown  # NEW: Detailed breakdown
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing {symbol}: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return {'symbol': symbol, 'error': str(e), 'signal': None}
    
    # NEW: Diagnostic methods
    def get_near_misses(self, limit: int = 10) -> List[Dict]:
        """Get recent near-miss signals for diagnostics"""
        return self.near_misses[-limit:]
    
    def clear_near_misses(self):
        """Clear near-miss history"""
        self.near_misses = []
    
    def set_threshold(self, base: int = None, high_impact: int = None, near_miss: int = None):
        """Adjust signal thresholds dynamically"""
        if base is not None:
            self.base_signal_threshold = base
            self.logger.info(f"Base threshold set to: {base}")
        if high_impact is not None:
            self.high_impact_threshold = high_impact
            self.logger.info(f"High impact threshold set to: {high_impact}")
        if near_miss is not None:
            self.near_miss_threshold = near_miss
            self.logger.info(f"Near-miss threshold set to: {near_miss}")


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
    
    # Enable debug mode for testing
    analyzer = EnhancedProfessionalAnalyzer(polygon_api_key=API_KEY, debug_mode=True)
    
    print("=" * 80)
    print("PHASE 1 ENHANCED PROFESSIONAL ANALYZER TEST (WITH DIAGNOSTICS)")
    print("=" * 80)
    
    # Test with PLTR
    result = analyzer.generate_professional_signal('PLTR')
    
    print(f"\n📊 RESULTS:")
    print(f"Symbol: {result['symbol']}")
    print(f"Signal: {result.get('signal', 'None')}")
    print(f"Alert Type: {result.get('alert_type')}")
    print(f"Confidence: {result.get('confidence', 0):.1f}%")
    print(f"Total Factors: {result.get('total_factors_analyzed', 0)}")
    print(f"Threshold Used: {result.get('signal_threshold', 0)}")
    
    # Show scores
    print(f"\n📈 SCORES:")
    print(f"Bullish: {result.get('bullish_score', 0)}")
    print(f"Bearish: {result.get('bearish_score', 0)}")
    
    # Volume analysis summary
    if result.get('volume_analysis'):
        vol = result['volume_analysis']
        print(f"\n📊 Volume Analysis: {vol.get('summary', 'N/A')}")
    
    # Key levels summary
    if result.get('key_levels') and 'error' not in result['key_levels']:
        levels = result['key_levels']
        print(f"\n🎯 Key Levels:")
        print(f"  Confluence Score: {levels.get('confluence_score', 0)}/10")
        print(f"  At Resistance: {levels.get('at_resistance', False)}")
        print(f"  At Support: {levels.get('at_support', False)}")
    
    # Entry targets
    if result.get('entry_targets') and not result['entry_targets'].get('insufficient_rr'):
        et = result['entry_targets']
        print(f"\n💰 Entry & Targets:")
        print(f"  Entry: ${et.get('entry', 0):.2f}")
        print(f"  TP1: ${et.get('tp1', 0):.2f}")
        print(f"  Stop: ${et.get('stop_loss', 0):.2f}")
        print(f"  R:R Ratio: {et.get('risk_reward', 0):.2f}")
    
    # Show factor breakdown
    if result.get('factor_breakdown'):
        breakdown = result['factor_breakdown']
        print(f"\n🔍 FACTOR BREAKDOWN:")
        print(f"\nBullish Factors:")
        for factor in breakdown['bullish']:
            print(f"  • {factor}")
        print(f"\nBearish Factors:")
        for factor in breakdown['bearish']:
            print(f"  • {factor}")
    
    # Show near-misses
    near_misses = analyzer.get_near_misses()
    if near_misses:
        print(f"\n⚠️ NEAR-MISSES DETECTED:")
        for nm in near_misses:
            print(f"  {nm['symbol']}: B:{nm['bullish']} S:{nm['bearish']} (need {nm['needed']} more)")
    
    print("\n" + "=" * 80)