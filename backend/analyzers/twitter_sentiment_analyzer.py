"""
backend/analyzers/twitter_sentiment_analyzer.py
Twitter/X Sentiment Analyzer for Trading System
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from collections import defaultdict
import time

class TwitterSentimentAnalyzer:
    def __init__(self, bearer_token: str):
        """
        Initialize Twitter Sentiment Analyzer
        
        Args:
            bearer_token: Twitter API v2 Bearer Token
        """
        self.bearer_token = bearer_token
        self.base_url = "https://api.twitter.com/2"
        self.logger = logging.getLogger(__name__)
        
        # Cache to avoid rate limits
        self.cache = {}
        self.cache_duration = 120  # 2 minutes cache
        self.last_request_time = {}
        
        # Sentiment keywords
        self.bullish_keywords = [
            'bullish', 'moon', 'rocket', 'calls', 'buying', 'long',
            'breakout', 'rally', 'pump', 'ATH', 'all time high',
            'buy the dip', 'loading', 'accumulating', 'strong'
        ]
        
        self.bearish_keywords = [
            'bearish', 'puts', 'selling', 'short', 'crash', 'dump',
            'breakdown', 'falling', 'weak', 'overvalued', 'bubble',
            'exit', 'trimming', 'taking profits', 'rug'
        ]
        
        # High-influence accounts
        self.whale_accounts = [
            'unusual_whales',
            'DeItaone',
            'zerohedge',
            'FirstSquawk',
            'LiveSquawk',
            'fxhedgers',
            'Investingcom',
            'carlquintanilla',
            'jimcramer',
            'GRDecter'
        ]
    
    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make Twitter API request with rate limiting"""
        cache_key = f"{endpoint}_{str(params)}"
        
        # Check cache
        if cache_key in self.cache:
            cache_time, cache_data = self.cache[cache_key]
            if time.time() - cache_time < self.cache_duration:
                return cache_data
        
        # Rate limiting
        now = time.time()
        if endpoint in self.last_request_time:
            time_since_last = now - self.last_request_time[endpoint]
            if time_since_last < 1:
                time.sleep(1 - time_since_last)
        
        self.last_request_time[endpoint] = time.time()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.bearer_token}',
            'User-Agent': 'TradingBotV2'
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 429:
                self.logger.warning("Twitter API rate limit hit, using cached data")
                return self.cache.get(cache_key, (0, {}))[1]
            
            response.raise_for_status()
            data = response.json()
            
            # Cache the result
            self.cache[cache_key] = (time.time(), data)
            return data
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Twitter API request failed: {str(e)}")
            if cache_key in self.cache:
                return self.cache[cache_key][1]
            return {}
    
    def search_recent_tweets(self, symbol: str, max_results: int = 100) -> List[Dict]:
        """Search for recent tweets about a symbol"""
        query = f"(${symbol} OR #{symbol}) -is:retweet lang:en"
        
        params = {
            'query': query,
            'max_results': min(max_results, 100),
            'tweet.fields': 'created_at,public_metrics,author_id,entities',
            'expansions': 'author_id',
            'user.fields': 'username,verified,public_metrics'
        }
        
        endpoint = '/tweets/search/recent'
        data = self._make_request(endpoint, params)
        
        if 'data' not in data:
            return []
        
        tweets = data['data']
        users = {user['id']: user for user in data.get('includes', {}).get('users', [])}
        
        enriched_tweets = []
        for tweet in tweets:
            author_id = tweet.get('author_id')
            user_data = users.get(author_id, {})
            
            enriched_tweets.append({
                'text': tweet.get('text', ''),
                'created_at': tweet.get('created_at', ''),
                'likes': tweet.get('public_metrics', {}).get('like_count', 0),
                'retweets': tweet.get('public_metrics', {}).get('retweet_count', 0),
                'replies': tweet.get('public_metrics', {}).get('reply_count', 0),
                'username': user_data.get('username', 'unknown'),
                'verified': user_data.get('verified', False),
                'followers': user_data.get('public_metrics', {}).get('followers_count', 0)
            })
        
        return enriched_tweets
    
    def analyze_tweet_sentiment(self, text: str) -> Dict:
        """Analyze sentiment of a single tweet"""
        text_lower = text.lower()
        
        bullish_count = sum(1 for keyword in self.bullish_keywords if keyword in text_lower)
        bearish_count = sum(1 for keyword in self.bearish_keywords if keyword in text_lower)
        
        # Check for emojis
        rocket_emojis = text.count('🚀') + text.count('📈')
        bearish_emojis = text.count('📉') + text.count('💩')
        
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
    
    def get_twitter_sentiment(self, symbol: str) -> Dict:
        """Get comprehensive Twitter sentiment analysis"""
        try:
            tweets = self.search_recent_tweets(symbol, max_results=100)
            
            if not tweets:
                return {
                    'overall_sentiment': 'NEUTRAL',
                    'volume': 'LOW',
                    'engagement_score': 0,
                    'tweet_count': 0,
                    'top_tweets': [],
                    'whale_sentiment': 'NEUTRAL',
                    'urgency': 'LOW'
                }
            
            sentiments = []
            engagement_scores = []
            whale_tweets = []
            top_engagement = []
            
            for tweet in tweets:
                sentiment_data = self.analyze_tweet_sentiment(tweet['text'])
                
                engagement = (
                    tweet['likes'] * 1 +
                    tweet['retweets'] * 3 +
                    tweet['replies'] * 2
                ) * (1 + min(tweet['followers'] / 100000, 10))
                
                sentiments.append({
                    'sentiment': sentiment_data['sentiment'],
                    'score': sentiment_data['score'],
                    'engagement': engagement,
                    'tweet': tweet
                })
                
                engagement_scores.append(engagement)
                
                if tweet['username'].lower() in [w.lower() for w in self.whale_accounts]:
                    whale_tweets.append({
                        'username': tweet['username'],
                        'text': tweet['text'],
                        'sentiment': sentiment_data['sentiment'],
                        'engagement': engagement
                    })
                
                if engagement > 100:
                    top_engagement.append({
                        'username': tweet['username'],
                        'text': tweet['text'][:150] + '...' if len(tweet['text']) > 150 else tweet['text'],
                        'engagement': engagement,
                        'sentiment': sentiment_data['sentiment']
                    })
            
            total_weighted_score = sum(s['score'] * s['engagement'] for s in sentiments)
            total_engagement = sum(engagement_scores) or 1
            overall_score = total_weighted_score / total_engagement
            
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
            
            recent_count = sum(1 for t in tweets if self._is_recent(t['created_at'], hours=1))
            if recent_count > 50:
                volume = 'VERY HIGH'
            elif recent_count > 20:
                volume = 'HIGH'
            elif recent_count > 5:
                volume = 'MEDIUM'
            else:
                volume = 'LOW'
            
            if whale_tweets:
                whale_bullish = sum(1 for w in whale_tweets if w['sentiment'] == 'BULLISH')
                whale_bearish = sum(1 for w in whale_tweets if w['sentiment'] == 'BEARISH')
                
                if whale_bullish > whale_bearish * 1.5:
                    whale_sentiment = 'BULLISH'
                elif whale_bearish > whale_bullish * 1.5:
                    whale_sentiment = 'BEARISH'
                else:
                    whale_sentiment = 'MIXED'
            else:
                whale_sentiment = 'NONE'
            
            urgency = 'LOW'
            if volume in ['HIGH', 'VERY HIGH'] and abs(overall_score) > 0.3:
                urgency = 'HIGH'
            elif volume == 'HIGH' or abs(overall_score) > 0.4:
                urgency = 'MEDIUM'
            
            top_engagement.sort(key=lambda x: x['engagement'], reverse=True)
            
            return {
                'overall_sentiment': overall_sentiment,
                'sentiment_score': round(overall_score, 3),
                'volume': volume,
                'tweet_count': len(tweets),
                'recent_tweets': recent_count,
                'engagement_score': round(total_engagement, 0),
                'whale_sentiment': whale_sentiment,
                'whale_count': len(whale_tweets),
                'top_tweets': top_engagement[:5],
                'urgency': urgency,
                'bullish_count': sum(1 for s in sentiments if s['sentiment'] == 'BULLISH'),
                'bearish_count': sum(1 for s in sentiments if s['sentiment'] == 'BEARISH')
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing Twitter sentiment for {symbol}: {str(e)}")
            return {
                'overall_sentiment': 'NEUTRAL',
                'volume': 'UNKNOWN',
                'engagement_score': 0,
                'tweet_count': 0,
                'error': str(e)
            }
    
    def _is_recent(self, timestamp: str, hours: int = 1) -> bool:
        """Check if timestamp is within recent hours"""
        try:
            tweet_time = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S.%fZ')
            time_diff = datetime.utcnow() - tweet_time
            return time_diff.total_seconds() < (hours * 3600)
        except:
            return False