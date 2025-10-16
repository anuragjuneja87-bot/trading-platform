"""
Live Earnings Scanner
Manually check for earnings RIGHT NOW
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta

load_dotenv()


def check_polygon_earnings(api_key, symbols):
    """
    Check Polygon API for earnings data
    """
    print("\n" + "=" * 80)
    print("🔍 CHECKING POLYGON FOR LIVE EARNINGS DATA")
    print("=" * 80)
    
    today = datetime.now()
    # Check today and yesterday (earnings often released after market close)
    yesterday = today - timedelta(days=1)
    
    date_from = yesterday.strftime('%Y-%m-%d')
    date_to = today.strftime('%Y-%m-%d')
    
    print(f"\nDate range: {date_from} to {date_to}")
    print(f"Checking {len(symbols)} symbols...")
    
    earnings_found = []
    
    for symbol in symbols:
        try:
            # Check for earnings news (alternative method)
            url = f"https://api.polygon.io/v2/reference/news"
            params = {
                'ticker': symbol,
                'limit': 10,
                'apiKey': api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'results' in data:
                    for article in data['results']:
                        title = article.get('title', '').lower()
                        
                        # Check for earnings keywords
                        earnings_keywords = ['earnings', 'reports q', 'quarterly results', 
                                           'beats', 'misses', 'eps', 'revenue']
                        
                        if any(keyword in title for keyword in earnings_keywords):
                            # Check if recent (within 24 hours)
                            pub_time_str = article.get('published_utc', '')
                            if pub_time_str:
                                pub_time = datetime.strptime(pub_time_str, '%Y-%m-%dT%H:%M:%SZ')
                                hours_ago = (datetime.now() - pub_time).total_seconds() / 3600
                                
                                if hours_ago < 24:
                                    earnings_found.append({
                                        'symbol': symbol,
                                        'title': article.get('title'),
                                        'time_ago': hours_ago,
                                        'url': article.get('article_url')
                                    })
                                    print(f"\n✅ {symbol} - EARNINGS DETECTED!")
                                    print(f"   Headline: {article.get('title')[:70]}...")
                                    print(f"   Published: {hours_ago:.1f} hours ago")
                                    break
            
            print(f"   {symbol}: Checked", end='\r')
            
        except Exception as e:
            print(f"\n   ⚠️  Error checking {symbol}: {str(e)}")
            continue
    
    print("\n\n" + "=" * 80)
    
    if earnings_found:
        print(f"🎯 FOUND {len(earnings_found)} RECENT EARNINGS!")
        print("=" * 80)
        
        for e in earnings_found:
            print(f"\n📊 {e['symbol']}")
            print(f"   Headline: {e['title']}")
            print(f"   Published: {e['time_ago']:.1f} hours ago")
            if e.get('url'):
                print(f"   URL: {e['url']}")
    else:
        print("📭 NO RECENT EARNINGS FOUND")
        print("=" * 80)
        print("\nThis could mean:")
        print("• No earnings released in the last 24 hours")
        print("• Earnings not yet available via API")
        print("• None of your watchlist stocks reported")
    
    return earnings_found


def manual_earnings_scan():
    """
    Run a manual earnings scan using alert_manager
    """
    print("\n" + "=" * 80)
    print("🔄 RUNNING MANUAL EARNINGS SCAN")
    print("=" * 80)
    
    try:
        from utils.watchlist_manager import WatchlistManager
        from analyzers.enhanced_professional_analyzer import EnhancedProfessionalAnalyzer
        
        api_key = os.getenv('POLYGON_API_KEY')
        wm = WatchlistManager('backend/data/watchlist.txt')
        symbols = wm.load_symbols()
        
        print(f"\n📋 Scanning {len(symbols)} symbols: {', '.join(symbols)}")
        
        analyzer = EnhancedProfessionalAnalyzer(polygon_api_key=api_key)
        
        earnings_detected = []
        
        for symbol in symbols:
            print(f"\nAnalyzing {symbol}...", end=' ')
            
            try:
                result = analyzer.generate_professional_signal(symbol)
                
                # Check for earnings indicators
                news = result.get('news', {})
                gap = result.get('gap_data', {})
                
                # Strong earnings signal: High impact news + gap
                if news.get('news_impact') in ['HIGH', 'MEDIUM']:
                    headlines = news.get('headlines', [])
                    
                    for headline in headlines:
                        if any(word in headline.lower() for word in ['earnings', 'reports', 'beats', 'misses', 'eps']):
                            earnings_detected.append({
                                'symbol': symbol,
                                'headline': headline,
                                'sentiment': news.get('sentiment'),
                                'gap': gap.get('gap_type', 'NO_GAP'),
                                'gap_size': gap.get('gap_size', 0)
                            })
                            print("✅ EARNINGS DETECTED!")
                            break
                    else:
                        print("No earnings")
                else:
                    print("No earnings")
                    
            except Exception as e:
                print(f"Error: {str(e)}")
                continue
        
        print("\n" + "=" * 80)
        
        if earnings_detected:
            print(f"🎯 DETECTED {len(earnings_detected)} EARNINGS EVENTS!")
            print("=" * 80)
            
            for e in earnings_detected:
                print(f"\n📊 {e['symbol']}")
                print(f"   News: {e['sentiment']}")
                print(f"   Gap: {e['gap']} ({e['gap_size']:+.1f}%)")
                print(f"   Headline: {e['headline'][:70]}...")
        else:
            print("📭 NO EARNINGS DETECTED IN CURRENT SCAN")
            print("=" * 80)
        
        return earnings_detected
        
    except Exception as e:
        print(f"\n❌ Scan failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def main():
    """
    Main function
    """
    print("\n" + "=" * 80)
    print("📡 LIVE EARNINGS SCANNER")
    print("=" * 80)
    
    print("\nWhat would you like to do?")
    print("1. Check Polygon API for recent earnings")
    print("2. Run manual earnings scan (uses your analyzer)")
    print("3. Both")
    print("4. Exit")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == '1':
        try:
            from utils.watchlist_manager import WatchlistManager
            api_key = os.getenv('POLYGON_API_KEY')
            wm = WatchlistManager('backend/data/watchlist.txt')
            symbols = wm.load_symbols()
            
            check_polygon_earnings(api_key, symbols)
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
    
    elif choice == '2':
        manual_earnings_scan()
    
    elif choice == '3':
        print("\n🔄 Running comprehensive scan...")
        
        # Part 1: Polygon check
        try:
            from utils.watchlist_manager import WatchlistManager
            api_key = os.getenv('POLYGON_API_KEY')
            wm = WatchlistManager('backend/data/watchlist.txt')
            symbols = wm.load_symbols()
            
            check_polygon_earnings(api_key, symbols)
        except Exception as e:
            print(f"\n❌ Polygon check failed: {str(e)}")
        
        # Part 2: Manual scan
        manual_earnings_scan()
    
    elif choice == '4':
        print("\n👋 Exiting...")
        return
    
    else:
        print("\n❌ Invalid choice")
    
    # Instructions
    print("\n" + "=" * 80)
    print("💡 HOW REAL-TIME EARNINGS WORK:")
    print("=" * 80)
    print("""
Your system checks for earnings in TWO ways:

1. 🔍 NEWS MONITORING (Primary Method)
   - Scans news headlines every 5-15 minutes
   - Looks for keywords: "earnings", "beats", "misses", "reports Q3"
   - Detects earnings within minutes of release
   - Triggers alert to Discord #earnings-realtime

2. 📊 GAP DETECTION (Secondary Method)
   - Detects large gaps at market open
   - Checks if gap correlates with earnings news
   - Useful for after-hours earnings releases

⏰ TIMING:
   - Most earnings: Released after market close (4:00 PM ET)
   - Some earnings: Before market open (7:00 AM ET)
   - Alert typically arrives: 5-30 minutes after release

🎯 WHAT TO DO WHEN YOU GET AN ALERT:
   1. Read the sentiment (BEAT or MISS)
   2. Check the gap size for tomorrow's open
   3. Plan your entry strategy
   4. Set alerts in Bookmap
   5. Execute at market open
    """)
    
    print("=" * 80)


if __name__ == '__main__':
    main()
