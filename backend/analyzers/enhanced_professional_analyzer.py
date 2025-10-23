"""
backend/analyzers/enhanced_professional_analyzer.py
Enhanced Professional Analyzer v4.3 - CLEANED VERSION
REMOVED: VWAP, Camarilla, Twitter, Reddit
KEPT: All Gamma features, Wall Strength Tracking, Volume Analysis, News
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
import pytz

# Import GEX Calculator
from analyzers.gex_calculator import GEXCalculator

# Import Wall Strength Tracker
from analyzers.wall_strength_tracker import WallStrengthTracker

# Import Unusual Activity Detector (Feature 3)
try:
    from analyzers.unusual_activity_detector import UnusualActivityDetector
    UNUSUAL_ACTIVITY_AVAILABLE = True
except ImportError:
    UNUSUAL_ACTIVITY_AVAILABLE = False
    logging.warning("Unusual Activity Detector not available")

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
    def __init__(self, polygon_api_key: str, 
                 tradier_api_key: Optional[str] = None, 
                 tradier_account_type: str = 'sandbox',
                 debug_mode: bool = False):
        """
        Initialize Enhanced Professional Analyzer v4.3 - CLEANED
        
        Args:
            polygon_api_key: Polygon.io API key
            tradier_api_key: Tradier API key for real options data (optional)
            tradier_account_type: 'sandbox' or 'production' (default: sandbox)
            debug_mode: Enable detailed diagnostic logging (default: False)
        """
        self.polygon_api_key = polygon_api_key
        self.base_url = "https://api.polygon.io"
        self.logger = logging.getLogger(__name__)
        
        # Tradier API setup
        self.tradier_api_key = tradier_api_key
        self.tradier_account_type = tradier_account_type
        if tradier_api_key:
            self.tradier_base_url = "https://sandbox.tradier.com" if tradier_account_type == 'sandbox' else "https://api.tradier.com"
            self.logger.info(f"✅ Tradier API enabled ({tradier_account_type} mode)")
        else:
            self.tradier_base_url = None
            self.logger.warning("⚠️ Tradier API not configured - gamma walls will use basic Polygon data")
        
        # Debug mode
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
        
        # Configuration
        self.minimum_risk_reward = 2.0
        self.enforce_rr_filter = False
        
        # Configurable thresholds
        self.base_signal_threshold = 8
        self.high_impact_threshold = 6
        self.near_miss_threshold = 5
        
        # Track near-misses
        self.near_misses = []
        
        self.logger.info(f"📊 Signal Thresholds: Base={self.base_signal_threshold}, High Impact={self.high_impact_threshold}")
        self.logger.info(f"💡 Tradier Gamma Walls: {'ENABLED' if tradier_api_key else 'DISABLED (using Polygon fallback)'}")
        
        # Initialize GEX Calculator
        self.gex_calculator = GEXCalculator()
        self.logger.info("✅ GEX Calculator initialized")
        
        # Initialize Wall Strength Tracker
        self.wall_tracker = WallStrengthTracker()
        self.logger.info("✅ Wall Strength Tracker initialized")
        # Initialize Unusual Activity Detector (Feature 3)
        self.unusual_activity_detector = None
        if UNUSUAL_ACTIVITY_AVAILABLE:
            try:
                self.unusual_activity_detector = UnusualActivityDetector()
                self.logger.info("✅ Unusual Activity Detector initialized")
            except Exception as e:
                self.logger.error(f"⚠️ Unusual Activity Detector initialization failed: {str(e)}")
        else:
            self.logger.warning("⚠️ Unusual Activity Detector not available")
    
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
    
    def _make_tradier_request(self, endpoint: str, params: dict = None) -> dict:
        """Make Tradier API request"""
        if not self.tradier_api_key or not self.tradier_base_url:
            return {}
        
        if params is None:
            params = {}
        
        url = f"{self.tradier_base_url}{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.tradier_api_key}',
            'Accept': 'application/json'
        }
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Tradier API request failed for {endpoint}: {str(e)}")
            return {}
    
    def get_tradier_expirations(self, symbol: str) -> List[str]:
        """Get available option expiration dates from Tradier"""
        endpoint = "/v1/markets/options/expirations"
        params = {'symbol': symbol, 'includeAllRoots': 'true', 'strikes': 'false'}
        
        data = self._make_tradier_request(endpoint, params)
        
        if 'expirations' in data and 'date' in data['expirations']:
            dates = data['expirations']['date']
            if isinstance(dates, list):
                return dates
            elif isinstance(dates, str):
                return [dates]
        
        return []
    
    def get_tradier_options_chain(self, symbol: str, expiration: str) -> List[Dict]:
        """Get options chain from Tradier with real OI and Volume"""
        endpoint = "/v1/markets/options/chains"
        params = {
            'symbol': symbol,
            'expiration': expiration,
            'greeks': 'true'
        }
        
        data = self._make_tradier_request(endpoint, params)
        
        if 'options' in data and 'option' in data['options']:
            options = data['options']['option']
            if isinstance(options, dict):
                return [options]
            return options
        
        return []
        
    def get_options_chain(self, symbol: str) -> List[Dict]:
        """
        Get options chain for unusual activity detection
        Uses Tradier if available, falls back to Polygon
        """
        try:
            if self.tradier_api_key:
                expirations = self.get_tradier_expirations(symbol)
                if expirations:
                    et_tz = pytz.timezone('America/New_York')
                    today_str = datetime.now(et_tz).date().strftime('%Y-%m-%d')
                    
                    expiry_date = None
                    if today_str in expirations:
                        expiry_date = today_str
                    else:
                        future_expirations = [exp for exp in expirations if exp > today_str]
                        if future_expirations:
                            expiry_date = sorted(future_expirations)[0]
                    
                    if expiry_date:
                        options_chain = self.get_tradier_options_chain(symbol, expiry_date)
                        if options_chain:
                            self.logger.debug(f"✅ Got {len(options_chain)} options from Tradier for {symbol}")
                            return options_chain
            
            self.logger.warning(f"Tradier not available or no data, trying Polygon for {symbol}")
            
            endpoint = f"/v3/reference/options/contracts"
            params = {
                'underlying_ticker': symbol,
                'limit': 250,
                'expired': 'false'
            }
            
            data = self._make_request(endpoint, params)
            
            if 'results' in data and data['results']:
                options = []
                for contract in data['results']:
                    options.append({
                        'symbol': contract.get('ticker'),
                        'strike': float(contract.get('strike_price', 0)),
                        'option_type': contract.get('contract_type', ''),
                        'expiration_date': contract.get('expiration_date', ''),
                        'open_interest': 0,
                        'volume': 0,
                        'last': 0,
                        'greeks': {}
                    })
                
                self.logger.warning(f"⚠️ Using Polygon data (limited OI/Volume) for {symbol}")
                return options
            
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting options chain for {symbol}: {str(e)}")
            return []
            
    def analyze_gamma_walls_tradier(self, symbol: str, current_price: float) -> Dict:
        """
        Analyze gamma walls using Tradier API with REAL Open Interest and Volume
        Returns ALL gamma_levels for wall strength tracking
        """
        try:
            expirations = self.get_tradier_expirations(symbol)
            
            if not expirations:
                self.logger.warning(f"No options expirations found for {symbol}")
                return {'available': False, 'error': 'No expirations found'}
            
            et_tz = pytz.timezone('America/New_York')
            today = datetime.now(et_tz).date()
            today_str = today.strftime('%Y-%m-%d')
            
            expiry_date = None
            is_0dte = False
            hours_until_expiry = 0
            
            if today_str in expirations:
                expiry_date = today_str
                is_0dte = True
                now_et = datetime.now(et_tz)
                market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
                hours_until_expiry = (market_close - now_et).total_seconds() / 3600
                hours_until_expiry = max(0, hours_until_expiry)
            else:
                future_expirations = [exp for exp in expirations if exp > today_str]
                if future_expirations:
                    expiry_date = sorted(future_expirations)[0]
                    expiry_datetime = datetime.strptime(expiry_date, '%Y-%m-%d')
                    days_until = (expiry_datetime.date() - today).days
                    hours_until_expiry = days_until * 24
            
            if not expiry_date:
                return {'available': False, 'error': 'No valid expiration found'}
            
            options_chain = self.get_tradier_options_chain(symbol, expiry_date)
            
            if not options_chain:
                self.logger.warning(f"No options chain data for {symbol} expiring {expiry_date}")
                return {'available': False, 'error': 'No options chain data'}
            
            strikes_data = defaultdict(lambda: {
                'call_oi': 0,
                'call_volume': 0,
                'call_bid': 0,
                'call_ask': 0,
                'put_oi': 0,
                'put_volume': 0,
                'put_bid': 0,
                'put_ask': 0,
                'gamma': 0
            })
            
            for option in options_chain:
                strike = float(option.get('strike', 0))
                option_type = option.get('option_type', '').lower()
                
                if strike <= 0:
                    continue
                
                oi = int(option.get('open_interest', 0))
                volume = int(option.get('volume', 0))
                bid = float(option.get('bid', 0))
                ask = float(option.get('ask', 0))
                
                greeks = option.get('greeks', {})
                if greeks:
                    gamma = float(greeks.get('gamma', 0))
                else:
                    gamma = 0
                
                if option_type == 'call':
                    strikes_data[strike]['call_oi'] = oi
                    strikes_data[strike]['call_volume'] = volume
                    strikes_data[strike]['call_bid'] = bid
                    strikes_data[strike]['call_ask'] = ask
                    strikes_data[strike]['gamma'] += gamma
                elif option_type == 'put':
                    strikes_data[strike]['put_oi'] = oi
                    strikes_data[strike]['put_volume'] = volume
                    strikes_data[strike]['put_bid'] = bid
                    strikes_data[strike]['put_ask'] = ask
                    strikes_data[strike]['gamma'] += gamma
            
            gamma_levels = []
            
            for strike, data in strikes_data.items():
                total_oi = data['call_oi'] + data['put_oi']
                total_volume = data['call_volume'] + data['put_volume']
                
                if total_oi < 100:
                    continue
                
                distance = strike - current_price
                distance_pct = (distance / current_price) * 100
                
                max_distance = 5 if is_0dte else 10
                if abs(distance_pct) > max_distance:
                    continue
                
                gamma_exposure = total_oi * abs(data['gamma']) if data['gamma'] != 0 else total_oi
                
                strike_type = 'RESISTANCE' if strike > current_price else 'SUPPORT'
                
                if gamma_exposure > 100000 or total_oi > 50000:
                    strength = 'STRONG'
                elif gamma_exposure > 50000 or total_oi > 20000:
                    strength = 'MODERATE'
                else:
                    strength = 'WEAK'
                
                call_premium = (data['call_bid'] + data['call_ask']) / 2 if data['call_bid'] > 0 else 0
                put_premium = (data['put_bid'] + data['put_ask']) / 2 if data['put_bid'] > 0 else 0
                
                gamma_levels.append({
                    'strike': strike,
                    'type': strike_type,
                    'strength': strength,
                    'distance_pct': round(distance_pct, 2),
                    'distance_dollars': round(distance, 2),
                    'call_oi': data['call_oi'],
                    'call_volume': data['call_volume'],
                    'call_premium': round(call_premium, 2),
                    'put_oi': data['put_oi'],
                    'put_volume': data['put_volume'],
                    'put_premium': round(put_premium, 2),
                    'total_oi': total_oi,
                    'total_volume': total_volume,
                    'gamma_exposure': int(gamma_exposure),
                    'direction': '⬆️' if strike > current_price else '⬇️'
                })
            
            gamma_levels.sort(key=lambda x: x['gamma_exposure'], reverse=True)
            
            top_levels = gamma_levels[:3]
            
            if len(top_levels) >= 2:
                strikes = [level['strike'] for level in top_levels]
                expected_low = min(strikes)
                expected_high = max(strikes)
                expected_mid = (expected_low + expected_high) / 2
            else:
                expected_low = current_price * 0.98
                expected_high = current_price * 1.02
                expected_mid = current_price
            
            if is_0dte and hours_until_expiry < 3:
                pinning_effect = 'EXTREME'
            elif is_0dte:
                pinning_effect = 'HIGH'
            elif hours_until_expiry < 48:
                pinning_effect = 'MODERATE'
            else:
                pinning_effect = 'LOW'
            
            dominant_wall = top_levels[0]['strike'] if top_levels else current_price
            
            if len(top_levels) >= 2:
                recommendation = f"Expected range: ${expected_low:.0f}-${expected_high:.0f}"
            else:
                recommendation = "Insufficient options data for range"
            
            if self.debug_mode:
                self.logger.debug(f"{symbol} Gamma Analysis (Tradier):")
                self.logger.debug(f"  Expiration: {expiry_date} ({'0DTE' if is_0dte else f'{hours_until_expiry/24:.1f} days'})")
                self.logger.debug(f"  Total gamma levels found: {len(gamma_levels)}")
                self.logger.debug(f"  Top 3 gamma levels:")
                for level in top_levels:
                    self.logger.debug(f"    ${level['strike']}: {level['total_oi']:,} OI, {level['gamma_exposure']:,} gamma exp")
            
            return {
                'expiration': expiry_date,
                'expires_today': is_0dte,
                'hours_until_expiry': round(hours_until_expiry, 1),
                'current_price': current_price,
                'gamma_levels': gamma_levels,
                'expected_range': {
                    'low': round(expected_low, 2),
                    'high': round(expected_high, 2),
                    'midpoint': round(expected_mid, 2)
                },
                'analysis': {
                    'pinning_effect': pinning_effect,
                    'dominant_wall': round(dominant_wall, 2),
                    'recommendation': recommendation
                },
                'data_source': 'tradier',
                'data_delay': '20min' if self.tradier_account_type == 'sandbox' else 'realtime',
                'available': True
            }
            
        except Exception as e:
            self.logger.error(f"Tradier gamma analysis failed for {symbol}: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return {'available': False, 'error': str(e)}
    
    def analyze_full_gex(self, symbol: str) -> Dict:
        """
        Analyze Net Gamma Exposure (GEX) for symbol
        Uses Tradier to get ALL options, then calculates net GEX
        """
        try:
            quote = self.get_real_time_quote(symbol)
            current_price = quote['price']
            
            if current_price == 0:
                return {
                    'symbol': symbol,
                    'available': False,
                    'error': 'Invalid price'
                }
            
            expirations = self.get_tradier_expirations(symbol)
            
            if not expirations:
                return {
                    'symbol': symbol,
                    'available': False,
                    'error': 'No expirations found'
                }
            
            et_tz = pytz.timezone('America/New_York')
            today = datetime.now(et_tz).date()
            today_str = today.strftime('%Y-%m-%d')
            
            expiry_date = None
            if today_str in expirations:
                expiry_date = today_str
            else:
                future_expirations = [exp for exp in expirations if exp > today_str]
                if future_expirations:
                    expiry_date = sorted(future_expirations)[0]
            
            if not expiry_date:
                return {
                    'symbol': symbol,
                    'available': False,
                    'error': 'No valid expiration found'
                }
            
            options_chain = self.get_tradier_options_chain(symbol, expiry_date)
            
            if not options_chain:
                return {
                    'symbol': symbol,
                    'available': False,
                    'error': 'No options chain data'
                }
            
            gex_result = self.gex_calculator.calculate_net_gex(
                symbol, options_chain, current_price
            )
            
            gex_result['expiration'] = expiry_date
            gex_result['expires_today'] = (expiry_date == today_str)
            
            if self.debug_mode and gex_result.get('available'):
                self.logger.debug(f"{symbol} GEX Analysis:")
                net_gex = gex_result['net_gex']
                self.logger.debug(f"  Net GEX: ${net_gex['total']/1e9:.2f}B ({net_gex['regime']})")
                if gex_result['zero_gamma']['level']:
                    self.logger.debug(f"  Zero Gamma: ${gex_result['zero_gamma']['level']:.2f}")
            
            return gex_result
            
        except Exception as e:
            self.logger.error(f"GEX analysis failed for {symbol}: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return {
                'symbol': symbol,
                'available': False,
                'error': str(e)
            }
    
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
                    
                    if any(word in reasoning for word in ['upgrade', 'beats', 'breakthrough', 'surge']):
                        sentiment_score += 1
                    if any(word in reasoning for word in ['downgrade', 'plunge', 'crash', 'concern']):
                        sentiment_score -= 1
                    
                    break
            
            if not insight_found:
                if any(word in title for word in strong_positive):
                    sentiment_score += 3
                elif any(word in title for word in positive):
                    sentiment_score += 1
                
                if any(word in title for word in strong_negative):
                    sentiment_score -= 4
                elif any(word in title for word in negative):
                    sentiment_score -= 2
            
            if any(word in title for word in strong_negative):
                sentiment_score -= 2
            if any(word in title for word in strong_positive):
                sentiment_score += 1
            
            if any(word in title for word in urgent_keywords):
                urgency = 'HIGH'
        
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
        """Simplified - using Tradier gamma walls instead"""
        return {
            'sentiment': 'NEUTRAL',
            'put_call_ratio': 1.0,
            'note': 'Using Tradier gamma walls for options analysis'
        }
    
    def analyze_open_interest(self, symbol: str, current_price: float) -> Dict:
        """
        Use Tradier if available, fallback to Polygon contract counting
        Returns ALL gamma_levels for wall strength tracking
        """
        if self.tradier_api_key:
            tradier_result = self.analyze_gamma_walls_tradier(symbol, current_price)
            if tradier_result.get('available'):
                return tradier_result
            else:
                self.logger.warning(f"Tradier gamma analysis failed for {symbol}, falling back to Polygon")
        
        try:
            today = datetime.now()
            two_weeks = today + timedelta(days=14)
            
            endpoint = f"/v3/reference/options/contracts"
            params = {
                'underlying_ticker': symbol,
                'expiration_date.gte': today.strftime('%Y-%m-%d'),
                'expiration_date.lte': two_weeks.strftime('%Y-%m-%d'),
                'limit': 250
            }
            
            data = self._make_request(endpoint, params)
            
            if 'results' not in data or not data['results']:
                return {
                    'gamma_walls': [],
                    'nearest_wall': None,
                    'signal_strength': 0,
                    'available': False
                }
            
            oi_by_strike = defaultdict(lambda: {'calls': 0, 'puts': 0, 'total': 0})
            
            for contract in data['results']:
                strike = contract.get('strike_price', 0)
                contract_type = contract.get('contract_type', '').lower()
                
                if strike > 0:
                    if contract_type == 'call':
                        oi_by_strike[strike]['calls'] += 1
                    elif contract_type == 'put':
                        oi_by_strike[strike]['puts'] += 1
                    oi_by_strike[strike]['total'] += 1
            
            strikes_sorted = sorted(
                oi_by_strike.items(),
                key=lambda x: x[1]['total'],
                reverse=True
            )[:10]
            
            gamma_walls = []
            for strike, data in strikes_sorted:
                distance = abs(strike - current_price)
                distance_pct = (distance / current_price) * 100
                
                if distance_pct <= 5:
                    gamma_walls.append({
                        'strike': strike,
                        'distance': round(distance, 2),
                        'distance_pct': round(distance_pct, 2),
                        'contracts_available': data['total'],
                        'type': 'resistance' if strike > current_price else 'support'
                    })
            
            gamma_walls.sort(key=lambda x: x['distance'])
            
            nearest_wall = gamma_walls[0] if gamma_walls else None
            
            signal_strength = 0
            if nearest_wall:
                if nearest_wall['distance_pct'] < 1:
                    signal_strength = 3
                elif nearest_wall['distance_pct'] < 2:
                    signal_strength = 2
                elif nearest_wall['distance_pct'] < 3:
                    signal_strength = 1
            
            return {
                'gamma_walls': gamma_walls[:5],
                'nearest_wall': nearest_wall,
                'signal_strength': signal_strength,
                'available': True,
                'data_source': 'polygon_fallback',
                'note': 'Using contract counting - not real OI'
            }
            
        except Exception as e:
            self.logger.error(f"Open Interest analysis failed for {symbol}: {str(e)}")
            return {
                'gamma_walls': [],
                'nearest_wall': None,
                'signal_strength': 0,
                'available': False,
                'error': str(e)
            }
    
    def detect_dark_pool_activity(self, symbol: str) -> Dict:
        """Enhanced dark pool detection"""
        try:
            endpoint = f"/v3/trades/{symbol}"
            params = {'limit': 1000, 'order': 'desc'}
            
            data = self._make_request(endpoint, params)
            
            if 'results' not in data or not data['results']:
                return {
                    'activity': 'NEUTRAL',
                    'large_trades': 0,
                    'institutional_flow': 'NEUTRAL',
                    'block_trade_value': 0,
                    'signal_strength': 0
                }
            
            trades = data['results']
            
            sizes = [t.get('size', 0) for t in trades]
            prices = [t.get('price', 0) for t in trades]
            
            if not sizes or not prices:
                return {
                    'activity': 'NEUTRAL',
                    'large_trades': 0,
                    'institutional_flow': 'NEUTRAL',
                    'block_trade_value': 0,
                    'signal_strength': 0
                }
            
            avg_size = np.mean(sizes)
            total_volume = sum(sizes)
            
            large_trade_threshold = avg_size * 3
            large_trades = [
                {'size': t.get('size', 0), 'price': t.get('price', 0), 'time': t.get('participant_timestamp', 0)}
                for t in trades
                if t.get('size', 0) > large_trade_threshold
            ]
            
            block_trade_value = sum(t['size'] * t['price'] for t in large_trades)
            
            recent_large_trades = large_trades[:10]
            if len(recent_large_trades) >= 3:
                mid_point = len(recent_large_trades) // 2
                early_avg_price = np.mean([t['price'] for t in recent_large_trades[:mid_point]])
                late_avg_price = np.mean([t['price'] for t in recent_large_trades[mid_point:]])
                
                if late_avg_price > early_avg_price * 1.001:
                    institutional_flow = 'BUYING'
                elif late_avg_price < early_avg_price * 0.999:
                    institutional_flow = 'SELLING'
                else:
                    institutional_flow = 'MIXED'
            else:
                institutional_flow = 'NEUTRAL'
            
            large_trade_pct = len(large_trades) / len(trades) if trades else 0
            large_value_pct = sum(t['size'] for t in large_trades) / total_volume if total_volume > 0 else 0
            
            if large_trade_pct > 0.15 or large_value_pct > 0.5:
                activity = 'HEAVY'
                signal_strength = 4
            elif large_trade_pct > 0.1 or large_value_pct > 0.3:
                activity = 'MODERATE'
                signal_strength = 2
            else:
                activity = 'LIGHT'
                signal_strength = 0
            
            if institutional_flow in ['BUYING', 'SELLING'] and activity in ['HEAVY', 'MODERATE']:
                signal_strength += 2
            
            if self.debug_mode and activity != 'LIGHT':
                self.logger.debug(f"{symbol} Dark Pool:")
                self.logger.debug(f"  Activity: {activity}")
                self.logger.debug(f"  Flow: {institutional_flow}")
                self.logger.debug(f"  Large Trades: {len(large_trades)}")
                self.logger.debug(f"  Block Value: ${block_trade_value:,.0f}")
                self.logger.debug(f"  Signal Strength: {signal_strength}")
            
            return {
                'activity': activity,
                'large_trades': len(large_trades),
                'institutional_flow': institutional_flow,
                'block_trade_value': round(block_trade_value, 2),
                'large_trade_percentage': round(large_trade_pct * 100, 1),
                'signal_strength': signal_strength,
                'recent_flow_direction': institutional_flow
            }
            
        except Exception as e:
            self.logger.error(f"Dark pool analysis failed for {symbol}: {str(e)}")
            return {
                'activity': 'NEUTRAL',
                'large_trades': 0,
                'institutional_flow': 'NEUTRAL',
                'block_trade_value': 0,
                'signal_strength': 0
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
                                    support_resistance: Dict) -> Dict:
        """Calculate entry/TP/SL based on support/resistance"""
        if signal == 'BUY':
            entry = min(current_price, support_resistance['support'] + 0.10)
            # Use 2% above entry for TP1, 4% for TP2
            tp1 = entry * 1.02
            tp2 = entry * 1.04
            stop_loss = support_resistance['support'] - 0.20
        elif signal == 'SELL':
            entry = max(current_price, support_resistance['resistance'] - 0.10)
            # Use 2% below entry for TP1, 4% for TP2
            tp1 = entry * 0.98
            tp2 = entry * 0.96
            stop_loss = support_resistance['resistance'] + 0.20
        else:
            return {}
        
        risk = abs(entry - stop_loss)
        reward = abs(tp1 - entry)
        rr_ratio = reward / risk if risk > 0 else 0
        
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
        """Generate signal with Tradier gamma walls + Wall Strength Tracking integration"""
        try:
            if self.debug_mode:
                self.logger.debug(f"\n{'='*60}")
                self.logger.debug(f"Starting analysis for {symbol}")
                self.logger.debug(f"{'='*60}")
            
            quote = self.get_real_time_quote(symbol)
            current_price = quote['price']
            
            if current_price == 0:
                return {'symbol': symbol, 'error': 'Invalid price', 'signal': None}
            
            # Get all data (NO VWAP OR CAMARILLA)
            gap_data = self.detect_gap(symbol, current_price)
            support_resistance = self.get_support_resistance(symbol, current_price)
            options_flow = self.analyze_options_flow(symbol)
            open_interest = self.analyze_open_interest(symbol, current_price)
            dark_pool = self.detect_dark_pool_activity(symbol)
            news = self.get_enhanced_news_sentiment(symbol)
            bias_1h = self.calculate_timeframe_bias(symbol, '1H')
            bias_daily = self.calculate_timeframe_bias(symbol, '1D')
            
            # Volume Analysis
            volume_analysis = {}
            if self.volume_analyzer:
                try:
                    volume_analysis = self.volume_analyzer.generate_volume_analysis(symbol)
                    if self.debug_mode and volume_analysis:
                        rvol = volume_analysis.get('rvol', {})
                        self.logger.debug(f"Volume: RVOL={rvol.get('rvol', 0):.2f}x ({rvol.get('classification', 'N/A')})")
                except Exception as e:
                    self.logger.error(f"Volume analysis failed: {str(e)}")
            
            # Pre-Market RVOL
            premarket_rvol = {}
            if self.volume_analyzer:
                try:
                    premarket_rvol = self.volume_analyzer.calculate_premarket_rvol(symbol)
                    if self.debug_mode and premarket_rvol and premarket_rvol.get('rvol', 0) > 0:
                        self.logger.debug(f"Pre-Market RVOL: {premarket_rvol.get('rvol', 0):.2f}x ({premarket_rvol.get('classification', 'N/A')})")
                except Exception as e:
                    self.logger.error(f"Pre-market RVOL calculation failed: {str(e)}")
            
            # Key Level Detection
            key_levels = {}
            if self.key_level_detector:
                try:
                    key_levels = self.key_level_detector.detect_key_levels(symbol, current_price)
                    if self.debug_mode and key_levels and 'error' not in key_levels:
                        self.logger.debug(f"Key Levels: Confluence={key_levels.get('confluence_score', 0)}/10")
                except Exception as e:
                    self.logger.error(f"Key level detection failed: {str(e)}")
            
            # Wall Strength Tracking
            wall_strength = {}
            if open_interest.get('available'):
                try:
                    wall_strength = self.wall_tracker.track_wall_strength(
                        symbol, current_price, open_interest
                    )
                    
                    if self.debug_mode and wall_strength.get('tracking_active'):
                        self.logger.debug(f"Wall Strength Tracking: {len(wall_strength.get('tracked_walls', []))} walls monitored")
                        for wall_alert in wall_strength.get('alerts', []):
                            self.logger.debug(f"  ALERT: {wall_alert['alert_type']} at ${wall_alert['strike']}")
                            
                except Exception as e:
                    self.logger.error(f"Wall strength tracking failed: {str(e)}")
            
            momentum_shifted = self.detect_momentum_shift(symbol, bias_1h['bias'])
            
            # Signal scoring
            bullish_factors = 0
            bearish_factors = 0
            
            factor_breakdown = {
                'bullish': [],
                'bearish': []
            }
            
            # Gap factors
            if gap_data['gap_type'] == 'GAP_DOWN' and abs(gap_data['gap_size']) > 2:
                bearish_factors += 4
                factor_breakdown['bearish'].append(f"Large gap down ({gap_data['gap_size']}%) [+4]")
            elif gap_data['gap_type'] == 'GAP_UP' and gap_data['gap_size'] > 2:
                bullish_factors += 4
                factor_breakdown['bullish'].append(f"Large gap up ({gap_data['gap_size']}%) [+4]")
            
            # News factors
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
            
            # Bias factors
            if bias_1h['bias'] == 'BULLISH':
                bullish_factors += 2
                factor_breakdown['bullish'].append("1H bullish bias [+2]")
            if bias_daily['bias'] == 'BULLISH':
                bullish_factors += 1
                factor_breakdown['bullish'].append("Daily bullish bias [+1]")
            
            # Support/Resistance factors (replacing VWAP/Camarilla)
            price_to_support = (current_price - support_resistance['support']) / current_price * 100
            price_to_resistance = (support_resistance['resistance'] - current_price) / current_price * 100
            
            if price_to_support <= 1.0:  # Within 1% of support
                bullish_factors += 2
                factor_breakdown['bullish'].append("At/near support [+2]")
            
            if bias_1h['bias'] == 'BEARISH':
                bearish_factors += 2
                factor_breakdown['bearish'].append("1H bearish bias [+2]")
            if bias_daily['bias'] == 'BEARISH':
                bearish_factors += 1
                factor_breakdown['bearish'].append("Daily bearish bias [+1]")
            
            if price_to_resistance <= 1.0:  # Within 1% of resistance
                bearish_factors += 2
                factor_breakdown['bearish'].append("At/near resistance [+2]")
            
            # Dark pool factors
            dark_pool_strength = dark_pool.get('signal_strength', 0)
            if dark_pool_strength > 0:
                if dark_pool['institutional_flow'] == 'BUYING':
                    bullish_factors += dark_pool_strength
                    factor_breakdown['bullish'].append(f"Institutional buying (${dark_pool.get('block_trade_value', 0):,.0f}) [+{dark_pool_strength}]")
                elif dark_pool['institutional_flow'] == 'SELLING':
                    bearish_factors += dark_pool_strength
                    factor_breakdown['bearish'].append(f"Institutional selling (${dark_pool.get('block_trade_value', 0):,.0f}) [+{dark_pool_strength}]")
            
            # Gamma wall factors
            if open_interest.get('available'):
                gamma_levels = open_interest.get('gamma_levels', [])
                
                if open_interest.get('expires_today') and open_interest.get('hours_until_expiry', 999) < 3:
                    for level in gamma_levels[:3]:
                        if abs(level['distance_pct']) < 1.5:
                            if level['type'] == 'SUPPORT':
                                bullish_factors += 4
                                factor_breakdown['bullish'].append(f"0DTE gamma pin at ${level['strike']} ({level['total_oi']:,} OI) [+4]")
                            else:
                                bearish_factors += 4
                                factor_breakdown['bearish'].append(f"0DTE gamma pin at ${level['strike']} ({level['total_oi']:,} OI) [+4]")
                else:
                    for level in gamma_levels[:5]:
                        if abs(level['distance_pct']) < 2:
                            strength_points = 3 if level['strength'] == 'STRONG' else 2 if level['strength'] == 'MODERATE' else 1
                            if level['type'] == 'SUPPORT':
                                bullish_factors += strength_points
                                factor_breakdown['bullish'].append(f"Gamma wall support at ${level['strike']} [+{strength_points}]")
                            else:
                                bearish_factors += strength_points
                                factor_breakdown['bearish'].append(f"Gamma wall resistance at ${level['strike']} [+{strength_points}]")
            
            # Volume factors
            if volume_analysis:
                rvol_data = volume_analysis.get('rvol', {})
                spike_data = volume_analysis.get('volume_spike', {})
                
                rvol_strength = rvol_data.get('signal_strength', 0)
                if rvol_strength >= 3:
                    if bias_1h['bias'] == 'BULLISH':
                        bullish_factors += 3
                        factor_breakdown['bullish'].append(f"High RVOL confirmation ({rvol_data.get('rvol', 0):.1f}x) [+3]")
                    elif bias_1h['bias'] == 'BEARISH':
                        bearish_factors += 3
                        factor_breakdown['bearish'].append(f"High RVOL confirmation ({rvol_data.get('rvol', 0):.1f}x) [+3]")
                
                if spike_data.get('spike_detected'):
                    spike_strength = spike_data.get('signal_strength', 0)
                    if bias_1h['bias'] == 'BULLISH':
                        bullish_factors += spike_strength
                        factor_breakdown['bullish'].append(f"Volume spike detected [+{spike_strength}]")
                    elif bias_1h['bias'] == 'BEARISH':
                        bearish_factors += spike_strength
                        factor_breakdown['bearish'].append(f"Volume spike detected [+{spike_strength}]")
            
            # Key level factors
            if key_levels and 'error' not in key_levels:
                confluence_score = key_levels.get('confluence_score', 0)
                at_resistance = key_levels.get('at_resistance', False)
                at_support = key_levels.get('at_support', False)
                
                if at_resistance and confluence_score >= 6:
                    bearish_factors += 4
                    factor_breakdown['bearish'].append(f"High confluence resistance ({confluence_score}/10) [+4]")
                elif at_resistance:
                    bearish_factors += 2
                    factor_breakdown['bearish'].append(f"At resistance [+2]")
                
                if at_support and confluence_score >= 6:
                    bullish_factors += 4
                    factor_breakdown['bullish'].append(f"High confluence support ({confluence_score}/10) [+4]")
                elif at_support:
                    bullish_factors += 2
                    factor_breakdown['bullish'].append(f"At support [+2]")
            
            # Debug logging
            if self.debug_mode:
                self.logger.debug(f"\nFactor Breakdown:")
                self.logger.debug(f"Bullish ({bullish_factors} total):")
                for factor in factor_breakdown['bullish']:
                    self.logger.debug(f"  • {factor}")
                self.logger.debug(f"Bearish ({bearish_factors} total):")
                for factor in factor_breakdown['bearish']:
                    self.logger.debug(f"  • {factor}")
            
            # Determine signal threshold
            signal_threshold = self.base_signal_threshold
            
            if news['news_impact'] in ['HIGH', 'EXTREME'] or abs(gap_data.get('gap_size', 0)) > 3:
                signal_threshold = self.high_impact_threshold
                if self.debug_mode:
                    self.logger.debug(f"Using high-impact threshold: {signal_threshold}")
            
            # Determine signal
            signal = None
            confidence = 0.0
            alert_type = 'MONITOR'
            
            if bullish_factors >= signal_threshold:
                signal = 'BUY'
                confidence = min(bullish_factors / 28 * 100, 95)
                alert_type = 'STRONG BUY' if bullish_factors >= signal_threshold + 4 else 'BUY'
            elif bearish_factors >= signal_threshold:
                signal = 'SELL'
                confidence = min(bearish_factors / 28 * 100, 95)
                alert_type = 'STRONG SELL' if bearish_factors >= signal_threshold + 4 else 'SELL'
            
            # Momentum shift override
            if momentum_shifted:
                alert_type = 'MOMENTUM SHIFT - TAKE PROFIT'
            
            # Calculate targets
            entry_targets = self.calculate_entry_and_targets(
                symbol, signal if signal else 'HOLD',
                current_price, support_resistance
            )
            
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
                'support': support_resistance['support'],
                'resistance': support_resistance['resistance'],
                'bias_1h': bias_1h['bias'],
                'bias_daily': bias_daily['bias'],
                'options_sentiment': options_flow['sentiment'],
                'open_interest': open_interest,
                'dark_pool_activity': dark_pool['institutional_flow'],
                'dark_pool_details': dark_pool,
                'gap_data': gap_data,
                'news': news,
                'news_sentiment': news['sentiment'],
                'news_headlines': news['headlines'],
                'volume_analysis': volume_analysis,
                'premarket_rvol': premarket_rvol,
                'key_levels': key_levels,
                'wall_strength': wall_strength,
                'entry_targets': entry_targets,
                'momentum_shifted': momentum_shifted,
                'bullish_score': bullish_factors,
                'bearish_score': bearish_factors,
                'total_factors_analyzed': 26,
                'signal_threshold': signal_threshold,
                'factor_breakdown': factor_breakdown
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing {symbol}: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return {'symbol': symbol, 'error': str(e), 'signal': None}


if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    POLYGON_KEY = os.getenv('POLYGON_API_KEY')
    TRADIER_KEY = os.getenv('TRADIER_API_KEY')
    TRADIER_TYPE = os.getenv('TRADIER_ACCOUNT_TYPE', 'sandbox')
    
    analyzer = EnhancedProfessionalAnalyzer(
        polygon_api_key=POLYGON_KEY,
        tradier_api_key=TRADIER_KEY,
        tradier_account_type=TRADIER_TYPE,
        debug_mode=True
    )
    
    print("=" * 80)
    print("ENHANCED ANALYZER V4.3 - CLEANED (NO VWAP/CAMARILLA/TWITTER/REDDIT)")
    print("=" * 80)
    
    result = analyzer.generate_professional_signal('SPY')
    
    print(f"\n📊 TRADING SIGNAL:")
    print(f"Symbol: {result['symbol']}")
    print(f"Signal: {result.get('signal', 'None')}")
    print(f"Alert Type: {result.get('alert_type')}")
    print(f"Confidence: {result.get('confidence', 0):.1f}%")
    print(f"Current Price: ${result.get('current_price', 0):.2f}")
    print(f"Support: ${result.get('support', 0):.2f}")
    print(f"Resistance: ${result.get('resistance', 0):.2f}")
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS COMPLETE")
    print("=" * 80)