"""
backend/clients/benzinga_client.py
Benzinga News API Client via Polygon.io - FIXED VERSION
Documentation: https://polygon.io/docs/rest/partners/benzinga/news
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging


class BenzingaClient:
    def __init__(self, polygon_api_key: str):
        """Initialize Benzinga client using Polygon API"""
        self.api_key = polygon_api_key
        self.base_url = "https://api.polygon.io"
        self.logger = logging.getLogger(__name__)
        
    def get_news(self, 
                 ticker: Optional[str] = None,
                 limit: int = 50,
                 published_utc_gte: Optional[str] = None,
                 published_utc_lte: Optional[str] = None,
                 categories: Optional[List[str]] = None,
                 tags: Optional[List[str]] = None) -> List[Dict]:
        """
        Get Benzinga news via Polygon
        
        Args:
            ticker: Stock ticker symbol (e.g., 'NVDA')
            limit: Number of results (default 50, max 50)
            published_utc_gte: Published after this time (ISO format)
            published_utc_lte: Published before this time (ISO format)
            categories: List of categories (e.g., ['News', 'Price Target'])
            tags: List of tags (e.g., ['OpenAI', 'AI'])
        
        Returns:
            List of news articles
        """
        endpoint = f"{self.base_url}/benzinga/v1/news"
        
        params = {
            'apiKey': self.api_key,
            'limit': min(limit, 50)  # Max 50 per request
        }
        
        if ticker:
            params['ticker'] = ticker
        
        if published_utc_gte:
            params['published_utc.gte'] = published_utc_gte
        
        if published_utc_lte:
            params['published_utc.lte'] = published_utc_lte
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Handle error response
            if data.get('status') == 'ERROR':
                error_msg = data.get('error', 'Unknown error')
                self.logger.error(f"Benzinga API error: {error_msg}")
                return []
            
            results = data.get('results', [])
            
            # Check if results is actually a list
            if not isinstance(results, list):
                self.logger.error(f"Unexpected results type: {type(results)}")
                return []
            
            # Manual filtering if categories/tags provided
            if categories or tags:
                filtered = []
                for article in results:
                    # Skip if article is not a dict
                    if not isinstance(article, dict):
                        continue
                        
                    # Check categories
                    if categories:
                        article_cats = article.get('categories', [])
                        if any(cat in article_cats for cat in categories):
                            filtered.append(article)
                            continue
                    
                    # Check tags
                    if tags:
                        article_tags = article.get('tags', [])
                        title = article.get('title', '').lower()
                        teaser = article.get('teaser', '').lower()
                        
                        # Check if any tag appears in title, teaser, or tags
                        for tag in tags:
                            tag_lower = tag.lower()
                            if (tag_lower in title or 
                                tag_lower in teaser or 
                                tag_lower in article_tags):
                                filtered.append(article)
                                break
                
                results = filtered
            
            self.logger.debug(f"Benzinga: Found {len(results)} articles for {ticker or 'ALL'}")
            return results
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Benzinga API error: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Benzinga unexpected error: {str(e)}")
            return []
    
    def get_recent_news(self, ticker: Optional[str] = None, hours: int = 2) -> List[Dict]:
        """
        Get recent news from last N hours
        
        Args:
            ticker: Stock ticker (optional)
            hours: How many hours back to search
        
        Returns:
            List of recent news articles
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        published_gte = cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        return self.get_news(
            ticker=ticker,
            published_utc_gte=published_gte,
            limit=50
        )
    
    def search_news(self, keywords: List[str], hours: int = 24) -> List[Dict]:
        """
        Search news by keywords
        
        Args:
            keywords: List of keywords to search for
            hours: How many hours back to search
        
        Returns:
            List of matching articles
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        published_gte = cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Get all recent news
        all_news = self.get_news(
            published_utc_gte=published_gte,
            limit=50
        )
        
        # Filter by keywords
        matching = []
        for article in all_news:
            if not isinstance(article, dict):
                continue
                
            title = article.get('title', '').lower()
            teaser = article.get('teaser', '').lower()
            tags = [str(t).lower() for t in article.get('tags', [])]
            
            # Check if any keyword matches
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if (keyword_lower in title or 
                    keyword_lower in teaser or 
                    keyword_lower in tags):
                    matching.append(article)
                    break
        
        return matching
    
    def normalize_article(self, article: Dict) -> Dict:
        """
        Normalize Benzinga article to standard format
        
        Args:
            article: Raw Benzinga article
        
        Returns:
            Normalized article dict
        """
        # Safety check
        if not isinstance(article, dict):
            self.logger.error(f"Cannot normalize non-dict article: {type(article)}")
            return {
                'id': '',
                'title': 'Error',
                'url': '',
                'published_utc': '',
                'tickers': [],
                'categories': [],
                'tags': [],
                'teaser': '',
                'content': '',
                'author': '',
                'updated': '',
                'source': 'BENZINGA',
                'image_url': ''
            }
        
        # Safe extraction with fallbacks
        return {
            'id': article.get('benzinga_id', article.get('id', '')),
            'title': article.get('title', ''),
            'url': article.get('url', ''),
            'published_utc': article.get('published', article.get('published_utc', '')),
            'tickers': article.get('tickers', []),
            'categories': article.get('categories', []),
            'tags': article.get('tags', []),
            'teaser': article.get('teaser', ''),
            'content': article.get('content', ''),
            'author': article.get('author', ''),
            'updated': article.get('last_updated', article.get('updated', '')),
            'source': 'BENZINGA',
            'image_url': self._extract_image_url(article)
        }
    
    def _extract_image_url(self, article: Dict) -> str:
        """Safely extract image URL from article"""
        try:
            images = article.get('images', [])
            if images and isinstance(images, list) and len(images) > 0:
                first_image = images[0]
                if isinstance(first_image, dict):
                    return first_image.get('url', '')
            return ''
        except:
            return ''


if __name__ == '__main__':
    # Test
    import os
    
    logging.basicConfig(level=logging.DEBUG)
    
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        print("Set POLYGON_API_KEY environment variable")
        exit(1)
    
    client = BenzingaClient(api_key)
    
    # Test 1: Get NVDA news
    print("Test 1: NVDA news (last 24 hours)")
    news = client.get_recent_news('NVDA', hours=24)
    print(f"Found {len(news)} articles")
    if news:
        print(f"Latest: {news[0].get('title', 'No title')}")
    
    # Test 2: Search for OpenAI
    print("\nTest 2: OpenAI keyword search")
    openai_news = client.search_news(['OpenAI', 'ChatGPT', 'GPT'], hours=48)
    print(f"Found {len(openai_news)} OpenAI articles")
    if openai_news:
        for article in openai_news[:3]:
            print(f"  - {article.get('title', 'No title')}")