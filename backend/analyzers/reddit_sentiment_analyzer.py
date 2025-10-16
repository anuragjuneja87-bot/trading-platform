"""
backend/analyzers/reddit_sentiment_analyzer.py
Reddit Sentiment Analyzer for Trading System
FREE and way better rate limits than Twitter!
"""

import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from collections import defaultdict

class RedditSentimentAnalyzer:
    def __init__(self, client_id: str, client_secret: str, user_agent: str = "TradingBot/1.0"):
        """
        Initialize Reddit Sentiment Analyzer
        
        Args:
            client_id: Reddit app client ID
            client_secret: Reddit app client secret
            user_agent: User agent string
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.logger = logging.getLogger(__name__)
        
        # OAuth token
        self.access_token = None
        self.token_expires = 0
        
        # Cache
        self.cache = {}
        self.cache_duration = 300  # 5 minutes (Reddit is slower than Twitter)
        
        # Subreddits to monitor
        self.trading_subreddits = [
            'wallstreetbets',
            'stocks',
            'options',
            'investing',
            'StockMarket'
        ]
        
        # Sentiment keywords
        self.bullish_keywords = [
            'moon', 'calls', 'bullish', 'buy', 'long', 'yolo',
            'rocket', 'squeeze', 'breakout', 'rally', 'pump',
            'to the moon', 'tendies', 'diamond hands', 'hold',
            'lfg', 'lets go', 'huge', 'massive'
        ]
        
        self.bearish_keywords = [
            'puts', 'bearish', 'sell', 'short', 'crash', 'dump',
            'overvalued', 'bubble', 'puts printing', 'drill',
            'tank', 'dead', 'rip', 'baghold', 'loss porn'
        ]
        
        # Get initial token
        self._get_access_token()
    
    def _get_access_token(self):
        """Get OAuth2 access token from Reddit"""
        try:
            auth = requests.auth.HTTPBasicAuth(self.client_id, self.client_secret)
            data = {'grant_type': 'client_credentials'}
            headers = {'User-Agent': self.user_agent}
            
            response = requests.post(
                'https://www.reddit.com/api/v1/access_token',
                auth=auth,
                data=data,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            self.token_expires = time.time() + token_data['expires_in'] - 60  # Refresh 1 min early
            
            self.logger.info("✅ Reddit OAuth token obtained")
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to get Reddit token: {str(e)}")
            self.access_token = None
    
    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make Reddit API request with OAuth"""
        # Check if token needs refresh
        if not self.access_token or time.time() >= self.token_expires:
            self._get_access_token()
        
        if not self.access_token:
            return {}
        
        # Check cache
        cache_key = f"{endpoint}_{str(params)}"
        if cache_key in self.cache:
            cache_time, cache_data = self.cache[cache_key]
            if time.time() - cache_time < self.cache_duration:
                return cache_data
        
        # Make request
        url = f"https://oauth.reddit.com{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'User-Agent': self.user_agent
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 401:  # Unauthorized - token expired
                self._get_access_token()
                headers['Authorization'] = f'Bearer {self.access_token}'
                response = requests.get(url, headers=headers, params=params, timeout=10)
            
            response.raise_for_status()
            data = response.json()
            
            # Cache result
            self.cache[cache_key] = (time.time(), data)
            return data
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Reddit API request failed: {str(e)}")
            if cache_key in self.cache:
                return self.cache[cache_key][1]
            return {}
    
    def search_posts(self, symbol: str, subreddit: str = 'wallstreetbets', limit: int = 100) -> List[Dict]:
        """
        Search for posts mentioning a symbol
        
        Args:
            symbol: Stock ticker
            subreddit: Subreddit to search
            limit: Max posts to return
        """
        endpoint = f"/r/{subreddit}/search"
        params = {
            'q': f'${symbol} OR {symbol}',
            'restrict_sr': 'true',
            'sort': 'new',
            'limit': min(limit, 100),
            't': 'day'  # Last 24 hours
        }
        
        data = self._make_request(endpoint, params)
        
        if 'data' not in data or 'children' not in data['data']:
            return []
        
        posts = []
        for post in data['data']['children']:
            post_data = post['data']
            posts.append({
                'title': post_data.get('title', ''),
                'text': post_data.get('selftext', ''),
                'score': post_data.get('score', 0),
                'upvote_ratio': post_data.get('upvote_ratio', 0),
                'num_comments': post_data.get('num_comments', 0),
                'created_utc': post_data.get('created_utc', 0),
                'awards': post_data.get('total_awards_received', 0),
                'subreddit': post_data.get('subreddit', ''),
                'author': post_data.get('author', ''),
                'url': post_data.get('url', '')
            })
        
        return posts
    
    def analyze_post_sentiment(self, text: str) -> Dict:
        """Analyze sentiment of a post"""
        text_lower = text.lower()
        
        bullish_count = sum(1 for keyword in self.bullish_keywords if keyword in text_lower)
        bearish_count = sum(1 for keyword in self.bearish_keywords if keyword in text_lower)
        
        # Check for emojis
        rocket_emojis = text.count('🚀') + text.count('📈') + text.count('💎')
        bearish_emojis = text.count('📉') + text.count('💩') + text.count('🔻')
        
        bullish_count += rocket_emojis
        bearish_count += bearish_emojis
        
        total = bullish_count + bearish_count
        if total == 0:
            return {'sentiment': 'NEUTRAL', 'score': 0}
        
        score = (bullish_count - bearish_count) / total
        
        if score > 0.3:
            sentiment = 'BULLISH'
        elif score < -0.3:
            sentiment = 'BEARISH'
        else:
            sentiment = 'NEUTRAL'
        
        return {'sentiment': sentiment, 'score': score}
    
    def get_reddit_sentiment(self, symbol: str) -> Dict:
        """
        Get comprehensive Reddit sentiment for a symbol
        
        Returns:
            overall_sentiment: Sentiment classification
            volume: Post volume
            engagement: Engagement metrics
            top_posts: Most popular posts
        """
        try:
            all_posts = []
            
            # Search multiple subreddits
            for subreddit in ['wallstreetbets', 'stocks', 'options']:
                posts = self.search_posts(symbol, subreddit, limit=50)
                all_posts.extend(posts)
            
            if not all_posts:
                return {
                    'overall_sentiment': 'NEUTRAL',
                    'volume': 'LOW',
                    'post_count': 0,
                    'engagement_score': 0,
                    'top_posts': [],
                    'urgency': 'LOW'
                }
            
            # Analyze sentiments
            sentiments = []
            total_engagement = 0
            top_posts = []
            
            for post in all_posts:
                # Combine title and text
                full_text = f"{post['title']} {post['text']}"
                sentiment_data = self.analyze_post_sentiment(full_text)
                
                # Calculate engagement (score is upvotes - downvotes)
                engagement = (
                    post['score'] * 1.0 +
                    post['num_comments'] * 2.0 +
                    post['awards'] * 10.0  # Awards are expensive = strong signal
                )
                
                sentiments.append({
                    'sentiment': sentiment_data['sentiment'],
                    'score': sentiment_data['score'],
                    'engagement': engagement,
                    'post': post
                })
                
                total_engagement += engagement
                
                # Track high-engagement posts
                if engagement > 50 or post['awards'] > 0:
                    top_posts.append({
                        'title': post['title'][:150] + '...' if len(post['title']) > 150 else post['title'],
                        'subreddit': post['subreddit'],
                        'score': post['score'],
                        'awards': post['awards'],
                        'comments': post['num_comments'],
                        'sentiment': sentiment_data['sentiment'],
                        'engagement': engagement
                    })
            
            # Calculate weighted sentiment
            if sentiments:
                total_weighted_score = sum(s['score'] * s['engagement'] for s in sentiments)
                total_weight = sum(s['engagement'] for s in sentiments) or 1
                overall_score = total_weighted_score / total_weight
            else:
                overall_score = 0
            
            # Classify overall sentiment
            if overall_score > 0.4:
                overall_sentiment = 'VERY BULLISH'
            elif overall_score > 0.15:
                overall_sentiment = 'BULLISH'
            elif overall_score < -0.4:
                overall_sentiment = 'VERY BEARISH'
            elif overall_score < -0.15:
                overall_sentiment = 'BEARISH'
            else:
                overall_sentiment = 'NEUTRAL'
            
            # Determine volume
            post_count = len(all_posts)
            if post_count > 50:
                volume = 'VERY HIGH'
            elif post_count > 20:
                volume = 'HIGH'
            elif post_count > 5:
                volume = 'MEDIUM'
            else:
                volume = 'LOW'
            
            # Check for recent high-award posts (urgency indicator)
            recent_awards = sum(1 for p in all_posts if p['awards'] > 5)
            high_score_posts = sum(1 for p in all_posts if p['score'] > 1000)
            
            if recent_awards > 3 or high_score_posts > 5:
                urgency = 'HIGH'
            elif recent_awards > 0 or high_score_posts > 2:
                urgency = 'MEDIUM'
            else:
                urgency = 'LOW'
            
            # Sort top posts by engagement
            top_posts.sort(key=lambda x: x['engagement'], reverse=True)
            
            # Check for WSB-specific indicators
            wsb_posts = [p for p in all_posts if p['subreddit'].lower() == 'wallstreetbets']
            wsb_sentiment = 'NONE'
            if wsb_posts:
                wsb_bullish = sum(1 for p in sentiments if p['post'] in wsb_posts and p['sentiment'] == 'BULLISH')
                wsb_bearish = sum(1 for p in sentiments if p['post'] in wsb_posts and p['sentiment'] == 'BEARISH')
                
                if wsb_bullish > wsb_bearish * 1.5:
                    wsb_sentiment = 'BULLISH'
                elif wsb_bearish > wsb_bullish * 1.5:
                    wsb_sentiment = 'BEARISH'
                else:
                    wsb_sentiment = 'MIXED'
            
            return {
                'overall_sentiment': overall_sentiment,
                'sentiment_score': round(overall_score, 3),
                'volume': volume,
                'post_count': post_count,
                'engagement_score': round(total_engagement, 0),
                'wsb_sentiment': wsb_sentiment,
                'wsb_post_count': len(wsb_posts),
                'top_posts': top_posts[:5],
                'urgency': urgency,
                'bullish_count': sum(1 for s in sentiments if s['sentiment'] == 'BULLISH'),
                'bearish_count': sum(1 for s in sentiments if s['sentiment'] == 'BEARISH')
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing Reddit sentiment for {symbol}: {str(e)}")
            return {
                'overall_sentiment': 'NEUTRAL',
                'volume': 'UNKNOWN',
                'post_count': 0,
                'engagement_score': 0,
                'error': str(e)
            }


# CLI Testing
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
    REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
    
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        print("❌ Error: Reddit credentials not found in .env file")
        print("\nAdd to your .env file:")
        print("REDDIT_CLIENT_ID=your_client_id_here")
        print("REDDIT_CLIENT_SECRET=your_client_secret_here")
        exit(1)
    
    analyzer = RedditSentimentAnalyzer(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET
    )
    
    # Test with PLTR
    print("=" * 80)
    print("REDDIT SENTIMENT ANALYSIS: PLTR")
    print("=" * 80)
    
    result = analyzer.get_reddit_sentiment('PLTR')
    
    print(f"\nOverall Sentiment: {result['overall_sentiment']} ({result['sentiment_score']})")
    print(f"Post Volume: {result['volume']} ({result['post_count']} posts)")
    print(f"Engagement Score: {result['engagement_score']}")
    print(f"Urgency: {result['urgency']}")
    print(f"WSB Sentiment: {result['wsb_sentiment']} ({result['wsb_post_count']} WSB posts)")
    print(f"Bullish vs Bearish: {result['bullish_count']} vs {result['bearish_count']}")
    
    if result.get('top_posts'):
        print(f"\n🔥 TOP POSTS:")
        for i, post in enumerate(result['top_posts'][:3], 1):
            print(f"\n{i}. r/{post['subreddit']} (Score: {post['score']}, Awards: {post['awards']})")
            print(f"   Sentiment: {post['sentiment']}")
            print(f"   {post['title']}")
    
    print("=" * 80)
