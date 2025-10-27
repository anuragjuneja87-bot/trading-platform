#!/usr/bin/env python3
"""
Test script to check what news publishers you're currently getting from Polygon
Run this to see if you need Benzinga or if Polygon Real-Time is sufficient
"""

import requests
import os
from datetime import datetime

# Get your Polygon API key
POLYGON_API_KEY = os.getenv('POLYGON_API_KEY')

if not POLYGON_API_KEY:
    print("ERROR: POLYGON_API_KEY not found in environment variables")
    print("Set it with: export POLYGON_API_KEY='your_key_here'")
    exit(1)

def test_polygon_news():
    """Test current Polygon news feed"""
    
    print("=" * 80)
    print("POLYGON NEWS FEED TEST")
    print("=" * 80)
    print(f"Testing at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Test with major tickers
    test_tickers = ['NVDA', 'TSLA', 'AAPL', 'MSFT']
    
    publishers_found = {}
    total_articles = 0
    
    for ticker in test_tickers:
        print(f"\n{'='*80}")
        print(f"Testing: {ticker}")
        print(f"{'='*80}")
        
        endpoint = f"https://api.polygon.io/v2/reference/news"
        params = {
            'ticker': ticker,
            'limit': 5,
            'order': 'desc',
            'apiKey': POLYGON_API_KEY
        }
        
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'results' not in data or not data['results']:
                print(f"  ⚠️  No news found for {ticker}")
                continue
            
            articles = data['results']
            total_articles += len(articles)
            
            for i, article in enumerate(articles, 1):
                publisher = article.get('publisher', {}).get('name', 'Unknown')
                title = article.get('title', 'No title')
                published = article.get('published_utc', '')
                
                # Track publishers
                publishers_found[publisher] = publishers_found.get(publisher, 0) + 1
                
                # Parse timestamp
                try:
                    pub_time = datetime.strptime(published, '%Y-%m-%dT%H:%M:%SZ')
                    time_ago = datetime.utcnow() - pub_time
                    hours_ago = time_ago.total_seconds() / 3600
                    
                    if hours_ago < 1:
                        time_str = f"{int(time_ago.total_seconds() / 60)} min ago"
                    elif hours_ago < 24:
                        time_str = f"{int(hours_ago)} hours ago"
                    else:
                        time_str = f"{int(hours_ago / 24)} days ago"
                except:
                    time_str = "Unknown time"
                
                print(f"\n  Article {i}:")
                print(f"    Publisher: {publisher}")
                print(f"    Time: {time_str}")
                print(f"    Title: {title[:80]}...")
            
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Error fetching news for {ticker}: {str(e)}")
            continue
    
    # Summary
    print(f"\n\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total articles found: {total_articles}")
    print(f"\nPublishers found ({len(publishers_found)} unique):")
    
    # Sort by frequency
    sorted_publishers = sorted(publishers_found.items(), key=lambda x: x[1], reverse=True)
    for publisher, count in sorted_publishers:
        print(f"  • {publisher}: {count} articles")
    
    # Analysis
    print(f"\n{'='*80}")
    print("ANALYSIS")
    print(f"{'='*80}")
    
    premium_sources = ['Reuters', 'Bloomberg', 'CNBC', 'MarketWatch', 'Barron\'s', 'Wall Street Journal']
    basic_sources = ['Business Wire', 'GlobeNewswire', 'PR Newswire', 'Seeking Alpha', 'The Motley Fool', 'Benzinga']
    
    has_premium = any(pub in publishers_found for pub in premium_sources)
    has_basic = any(pub in publishers_found for pub in basic_sources)
    
    if has_premium:
        print("✅ GOOD: You have premium sources (Reuters, Bloomberg, etc)")
        print("   → Polygon Real-Time is working well")
        print("   → You may NOT need Benzinga subscription")
    elif has_basic:
        print("⚠️  LIMITED: Only basic sources found (Press releases, Seeking Alpha)")
        print("   → Missing premium sources (Reuters, Bloomberg, CNBC)")
        print("   → RECOMMEND: Add Benzinga ($99/month) for better coverage")
    else:
        print("❌ PROBLEM: Very limited sources")
        print("   → STRONGLY RECOMMEND: Add Benzinga")
    
    # Check for OpenAI news
    print(f"\n{'='*80}")
    print("OPENAI NEWS TEST")
    print(f"{'='*80}")
    
    print("Searching for 'OpenAI' keyword...")
    
    endpoint = f"https://api.polygon.io/v2/reference/news"
    params = {
        'limit': 10,
        'order': 'desc',
        'apiKey': POLYGON_API_KEY
    }
    
    try:
        response = requests.get(endpoint, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        openai_articles = []
        if 'results' in data and data['results']:
            for article in data['results']:
                title = article.get('title', '').lower()
                if 'openai' in title or 'chatgpt' in title or 'gpt' in title:
                    openai_articles.append(article)
        
        if openai_articles:
            print(f"✅ Found {len(openai_articles)} OpenAI-related articles")
            for article in openai_articles[:3]:
                publisher = article.get('publisher', {}).get('name', 'Unknown')
                title = article.get('title', 'No title')
                print(f"  • {publisher}: {title[:70]}...")
            print("\n   → Your OpenAI news monitor should work with better keywords")
        else:
            print("❌ No OpenAI articles found in recent news")
            print("   → This is why your #openai-news channel is empty")
            print("   → RECOMMEND: Add Benzinga for better AI coverage")
    
    except Exception as e:
        print(f"❌ Error searching OpenAI news: {str(e)}")
    
    # Final recommendation
    print(f"\n\n{'='*80}")
    print("FINAL RECOMMENDATION")
    print(f"{'='*80}")
    
    if has_premium and openai_articles:
        print("✅ Your current Polygon Real-Time News is GOOD")
        print("   → Fix your news monitor logic first")
        print("   → Test for 1 week before adding Benzinga")
        print("   → Potential savings: $99/month")
    elif has_basic and not openai_articles:
        print("⚠️  Your current Polygon has LIMITED coverage")
        print("   → Missing AI/tech premium sources")
        print("   → RECOMMEND: Add Benzinga News ($99/month)")
        print("   → This will fix your OpenAI news issue")
    else:
        print("❌ Your current coverage is INSUFFICIENT")
        print("   → STRONGLY RECOMMEND: Add Benzinga News ($99/month)")
        print("   → Essential for pre-market trading with 6-7 figure positions")
    
    print(f"\n{'='*80}\n")


if __name__ == '__main__':
    test_polygon_news()
