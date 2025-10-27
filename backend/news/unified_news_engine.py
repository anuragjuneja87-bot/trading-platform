"""
backend/news/unified_news_engine.py
Unified News Engine - Merges Benzinga + Polygon feeds
Routes to appropriate Discord channels
"""

import sys
from pathlib import Path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from collections import defaultdict
import hashlib


class UnifiedNewsEngine:
    def __init__(self, 
                 polygon_api_key: str,
                 use_benzinga: bool = True,
                 use_polygon: bool = True):
        """
        Initialize unified news engine
        
        Args:
            polygon_api_key: Polygon API key
            use_benzinga: Enable Benzinga feed
            use_polygon: Enable Polygon feed (backup)
        """
        self.logger = logging.getLogger(__name__)
        self.use_benzinga = use_benzinga
        self.use_polygon = use_polygon
        
        # Initialize clients
        if use_benzinga:
            from clients.benzinga_client import BenzingaClient
            self.benzinga = BenzingaClient(polygon_api_key)
            self.logger.info("✅ Benzinga client initialized")
        else:
            self.benzinga = None
        
        # Polygon client (already exists)
        self.polygon_api_key = polygon_api_key
        
        # Deduplication cache
        self.seen_urls = set()
        self.seen_hashes = set()
    
    def get_unified_news(self, 
                        ticker: Optional[str] = None,
                        hours: int = 2,
                        limit: int = 50) -> List[Dict]:
        """
        Get unified news from both Benzinga and Polygon
        
        Args:
            ticker: Stock ticker (optional)
            hours: How many hours back
            limit: Max results
        
        Returns:
            Merged and deduplicated news list
        """
        all_news = []
        
        # Priority 1: Benzinga (faster, better quality)
        if self.use_benzinga and self.benzinga:
            try:
                benzinga_news = self.benzinga.get_recent_news(ticker, hours=hours)
                for article in benzinga_news:
                    normalized = self.benzinga.normalize_article(article)
                    all_news.append(normalized)
                self.logger.debug(f"Benzinga: {len(benzinga_news)} articles")
            except Exception as e:
                self.logger.error(f"Benzinga fetch error: {str(e)}")
        
        # Priority 2: Polygon (backup/supplement)
        if self.use_polygon:
            try:
                polygon_news = self._get_polygon_news(ticker, hours=hours)
                for article in polygon_news:
                    all_news.append(article)
                self.logger.debug(f"Polygon: {len(polygon_news)} articles")
            except Exception as e:
                self.logger.error(f"Polygon fetch error: {str(e)}")
        
        # Deduplicate by URL
        deduplicated = self._deduplicate_news(all_news)
        
        # Sort by timestamp (newest first)
        deduplicated.sort(key=lambda x: x['published_utc'], reverse=True)
        
        return deduplicated[:limit]
    
    def _get_polygon_news(self, ticker: Optional[str], hours: int) -> List[Dict]:
        """Get news from Polygon (existing API)"""
        import requests
        
        endpoint = "https://api.polygon.io/v2/reference/news"
        
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        published_gte = cutoff.strftime('%Y-%m-%d')
        
        params = {
            'apiKey': self.polygon_api_key,
            'limit': 50,
            'order': 'desc'
        }
        
        if ticker:
            params['ticker'] = ticker
        
        params['published_utc.gte'] = published_gte
        
        response = requests.get(endpoint, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = data.get('results', [])
        
        # Normalize Polygon format
        normalized = []
        for article in results:
            normalized.append({
                'id': article.get('id', ''),
                'title': article.get('title', ''),
                'url': article.get('article_url', ''),
                'published_utc': article.get('published_utc', ''),
                'tickers': article.get('tickers', []),
                'categories': [],
                'tags': article.get('keywords', []),
                'teaser': article.get('description', ''),
                'content': '',
                'author': article.get('author', ''),
                'updated': '',
                'source': 'POLYGON',
                'image_url': article.get('image_url', '')
            })
        
        return normalized
    
    def _deduplicate_news(self, articles: List[Dict]) -> List[Dict]:
        """
        Deduplicate news by URL and content hash
        
        Args:
            articles: List of articles
        
        Returns:
            Deduplicated list
        """
        deduplicated = []
        seen_urls = set()
        seen_hashes = set()
        
        for article in articles:
            url = article.get('url', '')
            title = article.get('title', '')
            
            # Skip if URL already seen
            if url and url in seen_urls:
                continue
            
            # Create content hash (title + first 100 chars)
            content_hash = hashlib.md5(
                f"{title[:100]}".encode()
            ).hexdigest()
            
            # Skip if content hash already seen
            if content_hash in seen_hashes:
                continue
            
            # Add to deduplicated list
            deduplicated.append(article)
            
            if url:
                seen_urls.add(url)
            seen_hashes.add(content_hash)
        
        return deduplicated
    
    def classify_news(self, article: Dict) -> Tuple[str, str]:
        """
        Classify news article for routing
        
        Args:
            article: News article
        
        Returns:
            Tuple of (channel, priority)
            channel: 'watchlist', 'critical', 'ai', 'skip'
            priority: 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
        """
        title = article.get('title', '').lower()
        teaser = article.get('teaser', '').lower()
        categories = [c.lower() for c in article.get('categories', [])]
        tags = [t.lower() for t in article.get('tags', [])]
        
        full_text = f"{title} {teaser}"
        
        # CRITICAL: Macro/Fed/Tariff news
        critical_keywords = [
            'fed ', 'fomc', 'federal reserve', 'powell', 'jerome powell',
            'interest rate decision', 'rate cut', 'rate hike',
            'tariff', 'trade war', 'china tariff', 'trump tariff',
            'cpi ', 'inflation data', 'jobs report', 'unemployment',
            'gdp ', 'pce ', 'economic data',
            'market halt', 'circuit breaker', 'trading halt'
        ]
        
        for keyword in critical_keywords:
            if keyword in full_text:
                return ('critical', 'CRITICAL')
        
        # HIGH: M&A, Major Analyst Actions
        high_keywords = [
            'acquires', 'acquisition', 'merger', 'takeover',
            'buyout', 'deal worth', 'billion deal',
            'price target', 'downgrade', 'upgrade'
        ]
        
        for keyword in high_keywords:
            if keyword in full_text:
                # Check if mega move (>20% PT change or >$1B deal)
                if ('price target' in full_text and 
                    any(x in full_text for x in ['raises', 'lowers', 'cuts'])):
                    return ('critical', 'HIGH')
                if any(x in full_text for x in ['billion', '$1b', '$ 1b']):
                    return ('critical', 'HIGH')
        
        # AI SECTOR: OpenAI, AI-specific news
        ai_keywords = [
            'openai', 'chatgpt', 'gpt-4', 'gpt-5', 'sam altman',
            'anthropic', 'claude', 'ai model', 'llm ',
            'artificial intelligence', 'machine learning',
            'ai chip', 'ai infrastructure'
        ]
        
        for keyword in ai_keywords:
            if keyword in full_text or keyword in tags:
                return ('ai', 'MEDIUM')
        
        # WATCHLIST: Will be filtered by ticker later
        return ('watchlist', 'MEDIUM')
    
    def search_with_keywords(self, 
                            keywords: List[str], 
                            hours: int = 24) -> List[Dict]:
        """
        Search news with specific keywords
        
        Args:
            keywords: List of keywords
            hours: Hours back to search
        
        Returns:
            Matching articles
        """
        all_news = []
        
        # Search Benzinga
        if self.use_benzinga and self.benzinga:
            benzinga_results = self.benzinga.search_news(keywords, hours=hours)
            for article in benzinga_results:
                normalized = self.benzinga.normalize_article(article)
                all_news.append(normalized)
        
        # Search Polygon
        if self.use_polygon:
            # Get all recent news and filter
            polygon_news = self._get_polygon_news(ticker=None, hours=hours)
            for article in polygon_news:
                title = article.get('title', '').lower()
                teaser = article.get('teaser', '').lower()
                
                for keyword in keywords:
                    if keyword.lower() in title or keyword.lower() in teaser:
                        all_news.append(article)
                        break
        
        # Deduplicate
        deduplicated = self._deduplicate_news(all_news)
        
        return deduplicated


if __name__ == '__main__':
    import os
    
    logging.basicConfig(level=logging.DEBUG)
    
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        print("Set POLYGON_API_KEY")
        exit(1)
    
    engine = UnifiedNewsEngine(api_key)
    
    # Test 1: Get NVDA news
    print("Test 1: NVDA news (unified)")
    news = engine.get_unified_news('NVDA', hours=24)
    print(f"Found {len(news)} articles")
    for article in news[:3]:
        print(f"  [{article['source']}] {article['title'][:70]}...")
    
    # Test 2: Search OpenAI
    print("\nTest 2: OpenAI keyword search")
    openai_news = engine.search_with_keywords(['OpenAI', 'ChatGPT'], hours=48)
    print(f"Found {len(openai_news)} OpenAI articles")
    
    # Test 3: Classification
    print("\nTest 3: News classification")
    for article in news[:5]:
        channel, priority = engine.classify_news(article)
        print(f"  {channel.upper()} ({priority}): {article['title'][:50]}...")
