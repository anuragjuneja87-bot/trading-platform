"""
Leveraged ETF Calculator
Calculates projected prices for leveraged ETFs based on underlying movement
"""
import requests
import json
from pathlib import Path
from typing import Dict, List, Optional
import logging
from datetime import datetime
import sys

# Ensure backend directory is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.cache_manager import cache
from config import config

logger = logging.getLogger(__name__)

class LeveragedCalculator:
    def __init__(self, api_key: str = None):
        """
        Initialize leveraged calculator
        
        Args:
            api_key: Polygon.io API key (uses config if not provided)
        """
        self.api_key = api_key or config.POLYGON_API_KEY
        self.base_url = "https://api.polygon.io"
        self.pairs_file = Path('backend/data/leveraged_pairs.json')
        
        # Load pairs configuration
        self.pairs = self._load_pairs()
        logger.info(f"Loaded {len(self.pairs)} leveraged pairs")
    
    def _load_pairs(self) -> List[Dict]:
        """Load leveraged pairs from JSON file"""
        if not self.pairs_file.exists():
            # Create default pairs
            default_pairs = [
                {
                    "id": "nvda-nvdl",
                    "underlying": "NVDA",
                    "leveraged": "NVDL",
                    "name": "NVIDIA 1.5x",
                    "active": True
                },
                {
                    "id": "pltr-pltu",
                    "underlying": "PLTR",
                    "leveraged": "PLTU",
                    "name": "Palantir 2x",
                    "active": True
                }
            ]
            
            self._save_pairs(default_pairs)
            return default_pairs
        
        try:
            with open(self.pairs_file, 'r') as f:
                data = json.load(f)
                return data.get('pairs', [])
        except Exception as e:
            logger.error(f"Error loading pairs: {str(e)}")
            return []
    
    def _save_pairs(self, pairs: List[Dict]) -> None:
        """Save leveraged pairs to JSON file"""
        try:
            # Ensure directory exists
            self.pairs_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'pairs': pairs,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.pairs_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved {len(pairs)} pairs to {self.pairs_file}")
        except Exception as e:
            logger.error(f"Error saving pairs: {str(e)}")
    
    def get_current_price(self, symbol: str) -> float:
        """
        Get current price for a symbol (with caching)
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Current price or 0 if error
        """
        cache_key = f"price_{symbol}"
        
        # Check cache first
        cached_price = cache.get(cache_key)
        if cached_price is not None:
            return cached_price
        
        # Fetch from API
        try:
            endpoint = f"{self.base_url}/v2/last/trade/{symbol}"
            params = {'apiKey': self.api_key}
            
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'results' in data:
                price = data['results'].get('p', 0)
                
                # Cache for 30 seconds
                cache.set(cache_key, price, ttl=30)
                
                return price
            
            return 0
            
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {str(e)}")
            return 0
    
    def calculate_leveraged_price(self, underlying: str, leveraged: str, 
                                  projected_underlying_price: float) -> Dict:
        """
        Calculate projected leveraged ETF price
        
        Args:
            underlying: Underlying symbol (e.g., NVDA)
            leveraged: Leveraged ETF symbol (e.g., NVDL)
            projected_underlying_price: Projected price for underlying
            
        Returns:
            Dictionary with calculation results
        """
        try:
            # Get current prices
            underlying_current = self.get_current_price(underlying)
            leveraged_current = self.get_current_price(leveraged)
            
            if underlying_current == 0 or leveraged_current == 0:
                return {
                    'error': 'Could not fetch current prices',
                    'underlying_current': underlying_current,
                    'leveraged_current': leveraged_current
                }
            
            # Calculate current ratio
            current_ratio = leveraged_current / underlying_current
            
            # Calculate percentage change in underlying
            percent_change = ((projected_underlying_price - underlying_current) / underlying_current) * 100
            
            # Project leveraged price
            projected_leveraged_price = projected_underlying_price * current_ratio
            
            # Calculate leveraged change
            leveraged_change = projected_leveraged_price - leveraged_current
            leveraged_percent_change = (leveraged_change / leveraged_current) * 100
            
            return {
                'underlying': underlying,
                'leveraged': leveraged,
                'underlying_current': round(underlying_current, 2),
                'leveraged_current': round(leveraged_current, 2),
                'projected_underlying': round(projected_underlying_price, 2),
                'projected_leveraged': round(projected_leveraged_price, 2),
                'current_ratio': round(current_ratio, 4),
                'underlying_change_pct': round(percent_change, 2),
                'leveraged_change_amount': round(leveraged_change, 2),
                'leveraged_change_pct': round(leveraged_percent_change, 2),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating leveraged price: {str(e)}")
            return {'error': str(e)}
    
    def get_pairs(self) -> List[Dict]:
        """Get all configured leveraged pairs"""
        return [pair for pair in self.pairs if pair.get('active', True)]
    
    def add_pair(self, underlying: str, leveraged: str, name: str) -> Dict:
        """
        Add a new leveraged pair
        
        Args:
            underlying: Underlying symbol
            leveraged: Leveraged ETF symbol
            name: Display name
            
        Returns:
            Result dictionary
        """
        pair_id = f"{underlying.lower()}-{leveraged.lower()}"
        
        # Check if exists
        existing = next((p for p in self.pairs if p['id'] == pair_id), None)
        if existing:
            return {'error': 'Pair already exists', 'pair_id': pair_id}
        
        # Add new pair
        new_pair = {
            'id': pair_id,
            'underlying': underlying.upper(),
            'leveraged': leveraged.upper(),
            'name': name,
            'active': True
        }
        
        self.pairs.append(new_pair)
        self._save_pairs(self.pairs)
        
        logger.info(f"Added new pair: {pair_id}")
        
        return {'success': True, 'pair': new_pair}
    
    def update_pair(self, pair_id: str, updates: Dict) -> Dict:
        """Update an existing pair"""
        pair = next((p for p in self.pairs if p['id'] == pair_id), None)
        
        if not pair:
            return {'error': 'Pair not found'}
        
        # Update fields
        for key, value in updates.items():
            if key in ['underlying', 'leveraged', 'name', 'active']:
                pair[key] = value
        
        self._save_pairs(self.pairs)
        
        logger.info(f"Updated pair: {pair_id}")
        
        return {'success': True, 'pair': pair}
    
    def delete_pair(self, pair_id: str) -> Dict:
        """Delete a leveraged pair"""
        self.pairs = [p for p in self.pairs if p['id'] != pair_id]
        self._save_pairs(self.pairs)
        
        logger.info(f"Deleted pair: {pair_id}")
        
        return {'success': True}

# Global instance
leveraged_calculator = LeveragedCalculator()
