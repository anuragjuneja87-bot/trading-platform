"""
ThetaData Terminal v3 REST API Client - Optimized for Day Trading
Supports bulk data retrieval with intelligent strike filtering
"""

import logging
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import time
import math


class ThetaDataClientV3:
    """
    ThetaData Terminal v3 REST API Client
    
    Optimized for high-frequency options data retrieval:
    - Bulk API calls with strike=* (all strikes)
    - IV-based dynamic strike filtering
    - 60-second caching for real-time updates
    - Professional subscription support
    """
    
    def __init__(self, base_url: str = "http://localhost:25503", cache_seconds: int = 60):
        """
        Initialize ThetaData v3 client
        
        Args:
            base_url: ThetaData Terminal URL (default: http://localhost:25503)
            cache_seconds: Cache duration in seconds (default: 60 for day trading)
        """
        self.logger = logging.getLogger(__name__)
        self.base_url = base_url.rstrip('/')
        self.cache_seconds = cache_seconds
        
        # Cache for options data
        self._cache = {}
        self._cache_timestamps = {}
        
        # Stats
        self.stats = {
            'api_calls': 0,
            'cache_hits': 0,
            'errors': 0
        }
        
        # Test connection
        self._test_connection()
    
    def _test_connection(self):
        """Test connection to ThetaData Terminal"""
        try:
            response = requests.get(f"{self.base_url}/v3", timeout=15)
            if response.status_code in [200, 404, 410]:  # 404/410 ok, just testing connection
                self.logger.info(f"✅ ThetaData v3 Terminal connected: {self.base_url}")
            else:
                self.logger.warning(f"⚠️ ThetaData Terminal returned status {response.status_code}")
        except Exception as e:
            self.logger.error(f"❌ Cannot connect to ThetaData Terminal: {e}")
            self.logger.error("   Make sure Terminal is running: java -jar ThetaTerminal.jar")
    
    def _make_request(self, endpoint: str, params: Dict) -> Optional[str]:
        """
        Make request to ThetaData API
        
        Args:
            endpoint: API endpoint (e.g., '/v3/option/snapshot/greeks/all')
            params: Query parameters
        
        Returns:
            CSV response as string, or None on error
        """
        try:
            url = f"{self.base_url}{endpoint}"
            response = requests.get(url, params=params, timeout=30)
            
            self.stats['api_calls'] += 1
            
            if response.status_code == 200:
                return response.text
            else:
                self.logger.warning(f"API returned {response.status_code} for {endpoint}")
                return None
                
        except Exception as e:
            self.logger.error(f"API request error: {e}")
            self.stats['errors'] += 1
            return None
    
    def _parse_csv(self, csv_text: str) -> List[Dict]:
        """
        Parse CSV response to list of dicts
        
        Args:
            csv_text: CSV response from API
        
        Returns:
            List of dicts with parsed data
        """
        if not csv_text or not csv_text.strip():
            return []
        
        lines = csv_text.strip().split('\n')
        if len(lines) < 2:
            return []
        
        # Parse header
        header = [h.strip().strip('"') for h in lines[0].split(',')]
        
        # Parse data rows
        result = []
        for line in lines[1:]:
            if not line.strip():
                continue
            
            values = []
            in_quotes = False
            current_value = ""
            
            for char in line:
                if char == '"':
                    in_quotes = not in_quotes
                elif char == ',' and not in_quotes:
                    values.append(current_value.strip().strip('"'))
                    current_value = ""
                else:
                    current_value += char
            
            values.append(current_value.strip().strip('"'))
            
            if len(values) == len(header):
                row = {}
                for i, key in enumerate(header):
                    value = values[i]
                    # Try to convert to number
                    try:
                        if '.' in value:
                            row[key] = float(value)
                        else:
                            row[key] = int(value)
                    except (ValueError, AttributeError):
                        row[key] = value
                
                result.append(row)
        
        return result
    
    def _get_cache_key(self, symbol: str, expiration: str, data_type: str, right: str) -> str:
        """Generate cache key"""
        return f"{symbol}_{expiration}_{data_type}_{right}"
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in self._cache_timestamps:
            return False
        
        age = (datetime.now() - self._cache_timestamps[cache_key]).total_seconds()
        return age < self.cache_seconds
    
    def _get_from_cache(self, cache_key: str) -> Optional[List[Dict]]:
        """Get data from cache if valid"""
        if self._is_cache_valid(cache_key):
            self.stats['cache_hits'] += 1
            return self._cache.get(cache_key)
        return None
    
    def _set_cache(self, cache_key: str, data: List[Dict]):
        """Store data in cache"""
        self._cache[cache_key] = data
        self._cache_timestamps[cache_key] = datetime.now()
    
    def get_greeks_bulk(self, symbol: str, expiration: str, right: str = 'call') -> List[Dict]:
        """
        Get Greeks for ALL strikes (bulk call)
        
        Args:
            symbol: Stock symbol (e.g., 'SPY')
            expiration: Expiration date in YYYY-MM-DD format
            right: 'call' or 'put'
        
        Returns:
            List of option contracts with Greeks data
        """
        cache_key = self._get_cache_key(symbol, expiration, 'greeks', right)
        
        # Check cache
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        # Make API call
        endpoint = '/v3/option/snapshot/greeks/all'
        params = {
            'symbol': symbol,
            'expiration': expiration,
            'strike': '*',  # ALL strikes
            'right': right
        }
        
        csv_data = self._make_request(endpoint, params)
        if not csv_data:
            return []
        
        parsed = self._parse_csv(csv_data)
        
        # Cache and return
        self._set_cache(cache_key, parsed)
        return parsed
    
    def get_open_interest_bulk(self, symbol: str, expiration: str, right: str = 'call') -> List[Dict]:
        """
        Get Open Interest for ALL strikes (bulk call)
        
        Args:
            symbol: Stock symbol
            expiration: Expiration date in YYYY-MM-DD format
            right: 'call' or 'put'
        
        Returns:
            List with OI data per strike
        """
        cache_key = self._get_cache_key(symbol, expiration, 'oi', right)
        
        # Check cache
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        # Make API call
        endpoint = '/v3/option/snapshot/open_interest'
        params = {
            'symbol': symbol,
            'expiration': expiration,
            'strike': '*',  # ALL strikes
            'right': right
        }
        
        csv_data = self._make_request(endpoint, params)
        if not csv_data:
            return []
        
        parsed = self._parse_csv(csv_data)
        
        # Cache and return
        self._set_cache(cache_key, parsed)
        return parsed
    
    def get_quotes_bulk(self, symbol: str, expiration: str, right: str = 'call') -> List[Dict]:
        """
        Get Quotes (including volume) for ALL strikes (bulk call)
        
        Args:
            symbol: Stock symbol
            expiration: Expiration date in YYYY-MM-DD format
            right: 'call' or 'put'
        
        Returns:
            List with quote data per strike
        """
        cache_key = self._get_cache_key(symbol, expiration, 'quote', right)
        
        # Check cache
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        # Make API call
        endpoint = '/v3/option/snapshot/quote'
        params = {
            'symbol': symbol,
            'expiration': expiration,
            'strike': '*',  # ALL strikes
            'right': right
        }
        
        csv_data = self._make_request(endpoint, params)
        if not csv_data:
            return []
        
        parsed = self._parse_csv(csv_data)
        
        # Cache and return
        self._set_cache(cache_key, parsed)
        return parsed
    
    def get_complete_options_chain(self, symbol: str, expiration: str, current_price: float) -> Dict:
        """
        Get complete options chain with Greeks, OI, and Volume
        Uses IV-based strike filtering for efficiency
        
        Args:
            symbol: Stock symbol
            expiration: Expiration date in YYYY-MM-DD format
            current_price: Current stock price for filtering
        
        Returns:
            Dict with filtered options data for calls and puts
        """
        result = {
            'symbol': symbol,
            'expiration': expiration,
            'current_price': current_price,
            'calls': [],
            'puts': [],
            'timestamp': datetime.now().isoformat(),
            'strikes_before_filter': 0,
            'strikes_after_filter': 0
        }
        
        # Get data for both calls and puts
        for right in ['call', 'put']:
            # 1. Get Greeks (includes IV for filtering)
            greeks = self.get_greeks_bulk(symbol, expiration, right)
            
            if not greeks:
                continue
            
            result['strikes_before_filter'] += len(greeks)
            
            # 2. Calculate IV-based strike range
            strike_range = self._calculate_strike_range(greeks, current_price)
            
            # 3. Filter strikes to relevant range
            filtered_greeks = self._filter_strikes(greeks, current_price, strike_range)
            
            result['strikes_after_filter'] += len(filtered_greeks)
            
            # 4. Get OI and Quotes for filtered strikes
            oi_data = self.get_open_interest_bulk(symbol, expiration, right)
            quote_data = self.get_quotes_bulk(symbol, expiration, right)
            
            # 5. Merge all data
            merged = self._merge_option_data(filtered_greeks, oi_data, quote_data)
            
            if right == 'call':
                result['calls'] = merged
            else:
                result['puts'] = merged
        
        self.logger.debug(
            f"{symbol} {expiration}: Filtered {result['strikes_before_filter']} → "
            f"{result['strikes_after_filter']} strikes"
        )
        
        return result
    
    def _calculate_strike_range(self, greeks_data: List[Dict], current_price: float) -> float:
        """
        Calculate strike range based on ATM implied volatility
        
        Args:
            greeks_data: Greeks data from API
            current_price: Current stock price
        
        Returns:
            Strike range as percentage (e.g., 0.015 = 1.5%)
        """
        if not greeks_data:
            return 0.02  # Default 2%
        
        # Find ATM option (closest to current price)
        atm_option = min(greeks_data, key=lambda x: abs(x['strike'] - current_price))
        
        iv = atm_option.get('implied_vol', 0)
        
        if iv <= 0:
            return 0.02  # Default 2%
        
        # Calculate 1-day expected move
        # IV is annualized, convert to daily: IV / sqrt(252)
        # Add 1.5x buffer for safety
        daily_move = (iv / math.sqrt(252)) * 1.5
        
        # Cap at reasonable range (1% to 5%)
        return max(0.01, min(0.05, daily_move))
    
    def _filter_strikes(self, options: List[Dict], current_price: float, range_pct: float) -> List[Dict]:
        """
        Filter strikes to relevant range around current price
        
        Args:
            options: Options data
            current_price: Current stock price
            range_pct: Strike range as percentage
        
        Returns:
            Filtered options list
        """
        min_strike = current_price * (1 - range_pct)
        max_strike = current_price * (1 + range_pct)
        
        return [opt for opt in options if min_strike <= opt['strike'] <= max_strike]
    
    def _merge_option_data(self, greeks: List[Dict], oi: List[Dict], quotes: List[Dict]) -> List[Dict]:
        """
        Merge Greeks, OI, and Quote data by strike
        
        Args:
            greeks: Greeks data
            oi: Open Interest data
            quotes: Quote data
        
        Returns:
            Merged list of options with all data
        """
        # Create lookup dicts by strike
        oi_lookup = {item['strike']: item for item in oi}
        quote_lookup = {item['strike']: item for item in quotes}
        
        result = []
        
        for greek_item in greeks:
            strike = greek_item['strike']
            
            # Start with Greeks data
            merged = greek_item.copy()
            merged['option_type'] = merged.get('right', '').lower()
            
            # Add OI if available
            if strike in oi_lookup:
                merged['open_interest'] = oi_lookup[strike].get('open_interest', 0)
            else:
                merged['open_interest'] = 0
            
            # Add Quote data if available
            if strike in quote_lookup:
                quote = quote_lookup[strike]
                merged['volume'] = quote.get('volume', 0)
                merged['bid_size'] = quote.get('bid_size', 0)
                merged['ask_size'] = quote.get('ask_size', 0)
                # Update bid/ask from quote if more recent
                if 'bid' in quote:
                    merged['bid'] = quote['bid']
                if 'ask' in quote:
                    merged['ask'] = quote['ask']
            else:
                merged['volume'] = 0
                merged['bid_size'] = 0
                merged['ask_size'] = 0
            
            result.append(merged)
        
        return result
    
    def get_expirations(self, symbol: str) -> List[str]:
        """
        Get available expiration dates for symbol
        
        Args:
            symbol: Stock symbol
        
        Returns:
            List of expiration dates in YYYY-MM-DD format
        """
        endpoint = '/v3/option/list/expirations'
        params = {'symbol': symbol}
        
        csv_data = self._make_request(endpoint, params)
        if not csv_data:
            return []
        
        parsed = self._parse_csv(csv_data)
        return [item['expiration'] for item in parsed]
    
    def clear_cache(self):
        """Clear all cached data"""
        self._cache.clear()
        self._cache_timestamps.clear()
        self.logger.info("Cache cleared")
    
    def get_stats(self) -> Dict:
        """Get client statistics"""
        return {
            **self.stats,
            'cache_size': len(self._cache),
            'cache_hit_rate': (
                self.stats['cache_hits'] / max(1, self.stats['api_calls'] + self.stats['cache_hits'])
            ) * 100
        }