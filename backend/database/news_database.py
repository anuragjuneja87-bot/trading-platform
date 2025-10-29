"""
News Database Manager
SQLite-based persistent storage for all news alerts
Stores news from all 4 channels with full history
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)


class NewsDatabase:
    def __init__(self, db_path: str = "data/news_history.db"):
        """
        Initialize news database
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        
        # Create data directory if needed
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        logger.info(f"✅ News database initialized: {db_path}")
    
    def _init_database(self):
        """Create database tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Main news table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id TEXT UNIQUE NOT NULL,
                ticker TEXT NOT NULL,
                headline TEXT NOT NULL,
                summary TEXT,
                url TEXT,
                source TEXT,
                channel TEXT,
                sentiment TEXT,
                published_at TIMESTAMP NOT NULL,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                UNIQUE(article_id, ticker)
            )
        """)
        
        # Index for fast queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ticker_published 
            ON news_articles(ticker, published_at DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_channel_published 
            ON news_articles(channel, published_at DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_published 
            ON news_articles(published_at DESC)
        """)
        
        conn.commit()
        conn.close()
        
        logger.info("✅ Database tables initialized")
    
    def add_news(self, 
                 ticker: str,
                 headline: str,
                 article_id: str = None,
                 summary: str = None,
                 url: str = None,
                 source: str = "Benzinga",
                 channel: str = "watchlist",
                 sentiment: str = "NEUTRAL",
                 published_at: datetime = None,
                 metadata: Dict = None) -> bool:
        """
        Add news article to database
        
        Args:
            ticker: Stock ticker (NVDA, TSLA, etc.)
            headline: News headline
            article_id: Unique article ID (auto-generated if None)
            summary: Article summary/teaser
            url: Article URL
            source: News source (Benzinga, Polygon, etc.)
            channel: Which Discord channel (critical, watchlist, ai, spillover)
            sentiment: BULLISH, BEARISH, NEUTRAL
            published_at: When article was published
            metadata: Additional JSON metadata
            
        Returns:
            True if added, False if duplicate
        """
        try:
            # Generate article_id if not provided
            if not article_id:
                article_id = self._generate_article_id(ticker, headline, published_at)
            
            # Use current time if published_at not provided
            if not published_at:
                published_at = datetime.now()
            
            # Convert metadata to JSON
            metadata_json = json.dumps(metadata) if metadata else None
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO news_articles 
                (article_id, ticker, headline, summary, url, source, channel, 
                 sentiment, published_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article_id, ticker, headline, summary, url, source, 
                channel, sentiment, published_at.isoformat(), metadata_json
            ))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"✅ Added news: {ticker} - {headline[:50]}...")
            return True
            
        except sqlite3.IntegrityError:
            # Duplicate - already exists
            logger.debug(f"⚠️  Duplicate news skipped: {ticker} - {headline[:50]}...")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error adding news: {str(e)}")
            return False
    
    def _generate_article_id(self, ticker: str, headline: str, published_at: datetime) -> str:
        """Generate unique article ID from content"""
        content = f"{ticker}_{headline}_{published_at.isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get_ticker_news(self, 
                       ticker: str, 
                       hours: int = 24,
                       limit: int = 50) -> List[Dict]:
        """
        Get news for specific ticker
        
        Args:
            ticker: Stock ticker
            hours: Hours of history to retrieve
            limit: Maximum number of articles
            
        Returns:
            List of news articles
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM news_articles
                WHERE ticker = ?
                AND published_at >= ?
                ORDER BY published_at DESC
                LIMIT ?
            """, (ticker, cutoff_time.isoformat(), limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            articles = []
            for row in rows:
                article = dict(row)
                # Parse metadata JSON
                if article['metadata']:
                    article['metadata'] = json.loads(article['metadata'])
                articles.append(article)
            
            return articles
            
        except Exception as e:
            logger.error(f"❌ Error getting ticker news: {str(e)}")
            return []
    
    def get_all_news(self, hours: int = 24) -> Dict[str, List[Dict]]:
        """
        Get all news grouped by ticker
        
        Args:
            hours: Hours of history to retrieve
            
        Returns:
            Dict mapping ticker to list of articles
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM news_articles
                WHERE published_at >= ?
                ORDER BY ticker, published_at DESC
            """, (cutoff_time.isoformat(),))
            
            rows = cursor.fetchall()
            conn.close()
            
            # Group by ticker
            news_by_ticker = {}
            for row in rows:
                article = dict(row)
                if article['metadata']:
                    article['metadata'] = json.loads(article['metadata'])
                
                ticker = article['ticker']
                if ticker not in news_by_ticker:
                    news_by_ticker[ticker] = []
                
                # Format for dashboard
                news_by_ticker[ticker].append({
                    'headline': article['headline'],
                    'url': article['url'],
                    'sentiment': article['sentiment'],
                    'time_str': self._format_time(article['published_at']),
                    'timestamp': article['published_at'],
                    'source': article['source'],
                    'channel': article['channel']
                })
            
            return news_by_ticker
            
        except Exception as e:
            logger.error(f"❌ Error getting all news: {str(e)}")
            return {}
    
    def get_channel_news(self, 
                        channel: str, 
                        hours: int = 24,
                        limit: int = 100) -> List[Dict]:
        """
        Get news from specific channel
        
        Args:
            channel: Channel name (critical, watchlist, ai, spillover)
            hours: Hours of history
            limit: Max articles
            
        Returns:
            List of articles
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM news_articles
                WHERE channel = ?
                AND published_at >= ?
                ORDER BY published_at DESC
                LIMIT ?
            """, (channel, cutoff_time.isoformat(), limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            articles = []
            for row in rows:
                article = dict(row)
                if article['metadata']:
                    article['metadata'] = json.loads(article['metadata'])
                articles.append(article)
            
            return articles
            
        except Exception as e:
            logger.error(f"❌ Error getting channel news: {str(e)}")
            return []
    
    def get_statistics(self) -> Dict:
        """Get database statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Total articles
            cursor.execute("SELECT COUNT(*) FROM news_articles")
            total = cursor.fetchone()[0]
            
            # By channel
            cursor.execute("""
                SELECT channel, COUNT(*) as count
                FROM news_articles
                GROUP BY channel
            """)
            by_channel = dict(cursor.fetchall())
            
            # Last 24 hours
            cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
            cursor.execute("""
                SELECT COUNT(*) FROM news_articles
                WHERE published_at >= ?
            """, (cutoff,))
            last_24h = cursor.fetchone()[0]
            
            # Unique tickers
            cursor.execute("SELECT COUNT(DISTINCT ticker) FROM news_articles")
            unique_tickers = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total_articles': total,
                'last_24h': last_24h,
                'unique_tickers': unique_tickers,
                'by_channel': by_channel
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting statistics: {str(e)}")
            return {}
    
    def cleanup_old_news(self, days: int = 30) -> int:
        """
        Delete news older than N days
        
        Args:
            days: Keep news from last N days
            
        Returns:
            Number of articles deleted
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM news_articles
                WHERE published_at < ?
            """, (cutoff_time.isoformat(),))
            
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"🗑️  Cleaned up {deleted} old articles (older than {days} days)")
            return deleted
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up old news: {str(e)}")
            return 0
    
    def _format_time(self, timestamp_str: str) -> str:
        """Format timestamp for display"""
        try:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            now = datetime.now()
            diff = now - dt
            
            if diff.total_seconds() < 60:
                return "Just now"
            elif diff.total_seconds() < 3600:
                mins = int(diff.total_seconds() / 60)
                return f"{mins}m ago"
            elif diff.total_seconds() < 86400:
                hours = int(diff.total_seconds() / 3600)
                return f"{hours}h ago"
            else:
                days = int(diff.total_seconds() / 86400)
                return f"{days}d ago"
        except:
            return timestamp_str


# Global instance
_db_instance = None

def get_news_database() -> NewsDatabase:
    """Get global news database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = NewsDatabase()
    return _db_instance
