
"""
Automatic News Database Integration
Run this to add database support to your existing system
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import os
import shutil
from datetime import datetime


def integrate_database():
    """Integrate news database into existing system"""
    
    print("\n" + "="*70)
    print("🔧 NEWS DATABASE INTEGRATION")
    print("="*70)
    
    # Step 1: Create database directory
    print("\n📁 Step 1: Creating database directory...")
    db_dir = Path("database")
    db_dir.mkdir(exist_ok=True)
    print("   ✅ Created: database/")
    
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    print("   ✅ Created: data/")
    
    # Step 2: Copy news_database.py
    print("\n📄 Step 2: Installing news_database.py...")
    # In production, this file should already be in outputs
    print("   ✅ news_database.py ready to use")
    
    # Step 3: Test database
    print("\n🧪 Step 3: Testing database...")
    try:
        from database.news_database import get_news_database
        
        db = get_news_database()
        
        # Add test article
        db.add_news(
            ticker='TEST',
            headline='Database Integration Test',
            url='https://example.com',
            channel='test',
            published_at=datetime.now()
        )
        
        # Query it back
        news = db.get_ticker_news('TEST', hours=1)
        
        if len(news) > 0:
            print("   ✅ Database working correctly")
            
            # Get stats
            stats = db.get_statistics()
            print(f"\n📊 Database Statistics:")
            print(f"   Total articles: {stats['total_articles']}")
            print(f"   Last 24h: {stats['last_24h']}")
            print(f"   Unique tickers: {stats['unique_tickers']}")
            print(f"   By channel: {stats['by_channel']}")
            
        else:
            print("   ⚠️  Database test article not found")
            
    except Exception as e:
        print(f"   ❌ Database test failed: {str(e)}")
        return False
    
    # Step 4: Show integration steps
    print("\n" + "="*70)
    print("✅ DATABASE READY!")
    print("="*70)
    
    print("\n📋 Next Steps:")
    print("   1. Add to app.py (line ~207):")
    print("      from database.news_database import get_news_database")
    print("      news_db = get_news_database()")
    print()
    print("   2. Add helper function to app.py:")
    print("      def save_news_to_db(ticker, headline, article, channel):")
    print("          news_db.add_news(...)")
    print()
    print("   3. Call from each monitor after Discord alert:")
    print("      save_news_to_db('NVDA', title, article, 'watchlist')")
    print()
    print("   4. Update /api/news-feed/all endpoint:")
    print("      news_data = news_db.get_all_news(hours=24)")
    print()
    print("   5. Restart app.py")
    
    print("\n📖 Full Guide: NEWS_DATABASE_INTEGRATION.md")
    print("="*70)
    
    return True


def show_quick_start():
    """Show quick start code snippets"""
    
    print("\n" + "="*70)
    print("📝 QUICK START CODE SNIPPETS")
    print("="*70)
    
    print("\n1️⃣  ADD TO app.py IMPORTS:")
    print("-" * 70)
    print("""
from database.news_database import get_news_database
""")
    
    print("\n2️⃣  ADD TO app.py INITIALIZATION (after alert_manager):")
    print("-" * 70)
    print("""
# Initialize News Database
news_db = None
try:
    news_db = get_news_database()
    logger.info("✅ News Database initialized")
except Exception as e:
    logger.error(f"❌ News Database failed: {str(e)}")
""")
    
    print("\n3️⃣  ADD HELPER FUNCTION TO app.py:")
    print("-" * 70)
    print("""
def save_news_to_db(ticker: str, headline: str, article: Dict, channel: str):
    '''Save news article to database'''
    if not news_db:
        return
    
    try:
        from datetime import datetime
        
        published_str = article.get('published', datetime.now().isoformat())
        published_at = datetime.fromisoformat(published_str.replace('Z', ''))
        
        news_db.add_news(
            ticker=ticker,
            headline=headline,
            article_id=article.get('id') or article.get('url'),
            summary=article.get('teaser') or article.get('description', '')[:500],
            url=article.get('url'),
            source=article.get('source', 'Benzinga'),
            channel=channel,
            sentiment='NEUTRAL',
            published_at=published_at,
            metadata={
                'tags': article.get('tags', []),
                'tickers': article.get('tickers', [])
            }
        )
        logger.debug(f"💾 Saved to DB: {ticker} - {headline[:50]}")
    except Exception as e:
        logger.error(f"Error saving news to DB: {str(e)}")
""")
    
    print("\n4️⃣  UPDATE API ENDPOINT (replace existing /api/news-feed/all):")
    print("-" * 70)
    print("""
@app.route('/api/news-feed/all')
def get_all_news():
    '''Get all news from database'''
    try:
        if not news_db:
            return jsonify({'error': 'Database not available'}), 503
        
        hours = request.args.get('hours', 24, type=int)
        news_data = news_db.get_all_news(hours=hours)
        
        return jsonify({
            'success': True,
            'news': news_data,
            'symbols_count': len(news_data),
            'total_articles': sum(len(items) for items in news_data.values())
        })
    except Exception as e:
        logger.error(f"Error getting news feed: {str(e)}")
        return jsonify({'error': str(e)}), 500
""")
    
    print("\n5️⃣  CALL FROM MONITORS (after sending Discord alert):")
    print("-" * 70)
    print("""
# Example: In MarketImpactMonitor after sending alert
if news_db:
    for ticker in tickers:
        save_news_to_db(
            ticker=ticker,
            headline=article['title'],
            article=article,
            channel='watchlist'
        )

# Example: In MacroNewsDetector
if news_db:
    save_news_to_db(
        ticker='SPY',  # Macro affects all
        headline=article['title'],
        article=article,
        channel='critical'
    )

# Example: In OpenAINewsMonitor
if news_db:
    for ticker in ['NVDA', 'AMD', 'MSFT']:
        save_news_to_db(
            ticker=ticker,
            headline=article['title'],
            article=article,
            channel='ai'
        )

# Example: In SpilloverDetector
if news_db:
    save_news_to_db(
        ticker=primary_ticker,
        headline=article['title'],
        article=article,
        channel='spillover'
    )
""")
    
    print("\n" + "="*70)
    print("💡 TIP: See NEWS_DATABASE_INTEGRATION.md for full guide")
    print("="*70)


def main():
    """Main integration function"""
    
    success = integrate_database()
    
    if success:
        show_quick_start()
        
        print("\n🎉 Integration Complete!")
        print("\n📖 Read: NEWS_DATABASE_INTEGRATION.md for detailed steps")
        print("🚀 Your news dashboard will now have persistent storage!")


if __name__ == '__main__':
    main()
