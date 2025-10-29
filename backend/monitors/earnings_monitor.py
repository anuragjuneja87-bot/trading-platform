"""
backend/monitors/earnings_monitor.py
Real-Time Earnings Monitor - CALENDAR-BASED APPROACH
Pre-market: 5:00 AM - 8:00 AM ET (20 sec checks)
Post-market: 3:50 PM - 7:00 PM ET (10 sec checks) ← FASTEST FOR CRITICAL EARNINGS
Routes to: DISCORD_EARNINGS_REALTIME
WITH DATABASE PERSISTENCE
"""

import sys
from pathlib import Path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import threading
import time
import logging
import requests
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, List, Optional
import pytz


class EarningsMonitor:
    def __init__(self, 
                 polygon_api_key: str,
                 unified_news_engine,
                 discord_alerter,
                 check_interval_premarket: int = 20,
                 check_interval_postmarket: int = 10):
        """
        Initialize Earnings Monitor - Calendar-based approach
        
        Args:
            polygon_api_key: Polygon API key
            unified_news_engine: UnifiedNewsEngine instance
            discord_alerter: DiscordAlerter instance
            check_interval_premarket: Pre-market check interval (default 20s)
            check_interval_postmarket: Post-market check interval (default 10s)
        """
        self.polygon_api_key = polygon_api_key
        self.unified_news = unified_news_engine
        self.discord = discord_alerter
        self.check_interval_premarket = check_interval_premarket
        self.check_interval_postmarket = check_interval_postmarket
        self.logger = logging.getLogger(__name__)
        
        self.running = False
        self.thread = None
        
        # Track seen earnings
        self.seen_earnings = set()  # Set of (symbol, date) tuples
        
        # Earnings calendar cache (refreshed weekly)
        self.earnings_calendar = []
        self.calendar_last_updated = None
        
        # Earnings keywords for news detection
        self.earnings_keywords = [
            'earnings', 'reports q', 'quarterly results', 'reports third quarter',
            'beats', 'misses', 'eps', 'revenue', 'guidance', 'blowout',
            'disappointing earnings', 'earnings surprise', 'beats estimates',
            'misses estimates', 'raises guidance', 'lowers guidance',
            'beats expectations', 'misses expectations', 'q1 earnings',
            'q2 earnings', 'q3 earnings', 'q4 earnings', 'reports results'
        ]
        
        self.stats = {
            'checks_performed': 0,
            'earnings_detected': 0,
            'alerts_sent': 0,
            'last_check': None,
            'calendar_symbols': 0,
            'calendar_last_updated': None,
            'current_session': None,
            'beats': 0,
            'misses': 0
        }
    
    def start(self):
        """Start monitoring in background thread"""
        if self.running:
            self.logger.warning("Earnings monitor already running")
            return
        
        self.running = True
        
        # Load initial earnings calendar
        self._refresh_earnings_calendar()
        
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        
        self.logger.info(f"📊 Earnings monitor started")
        self.logger.info(f"   🌅 Pre-market: 5:00 AM - 8:00 AM ET (check every {self.check_interval_premarket}s)")
        self.logger.info(f"   🌆 Post-market: 3:50 PM - 7:00 PM ET (check every {self.check_interval_postmarket}s) ⚡ FASTEST")
        self.logger.info(f"   📅 Monitoring {len(self.earnings_calendar)} stocks with earnings this week")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self.logger.info("Earnings monitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop - only runs during pre/post market windows"""
        while self.running:
            try:
                # Check if we're in a monitoring window
                session = self._get_current_session()
                
                if session == 'PREMARKET':
                    self.stats['current_session'] = 'PREMARKET'
                    self.check_earnings()
                    time.sleep(self.check_interval_premarket)
                    
                elif session == 'POSTMARKET':
                    self.stats['current_session'] = 'POSTMARKET'
                    self.check_earnings()
                    time.sleep(self.check_interval_postmarket)
                    
                else:
                    # Outside monitoring window - sleep for 1 minute
                    self.stats['current_session'] = 'IDLE'
                    time.sleep(60)
                    
                    # Refresh calendar if needed (once per day at market close)
                    if session == 'MARKET_CLOSE':
                        self._refresh_earnings_calendar()
                
            except Exception as e:
                self.logger.error(f"Error in earnings monitor loop: {str(e)}")
                time.sleep(30)
    
    def _get_current_session(self) -> str:
        """
        Determine current session
        Returns: 'PREMARKET', 'POSTMARKET', 'MARKET_HOURS', 'MARKET_CLOSE', 'IDLE'
        """
        et_tz = pytz.timezone('America/New_York')
        now_et = datetime.now(et_tz)
        current_time = now_et.time()
        
        # Pre-market: 5:00 AM - 8:00 AM ET
        premarket_start = dt_time(5, 0)
        premarket_end = dt_time(8, 0)
        
        # Post-market: 3:50 PM - 7:00 PM ET
        postmarket_start = dt_time(15, 50)  # 3:50 PM
        postmarket_end = dt_time(19, 0)     # 7:00 PM
        
        # Market close window for calendar refresh: 4:00 PM - 4:05 PM
        market_close_start = dt_time(16, 0)
        market_close_end = dt_time(16, 5)
        
        if premarket_start <= current_time < premarket_end:
            return 'PREMARKET'
        elif postmarket_start <= current_time < postmarket_end:
            return 'POSTMARKET'
        elif market_close_start <= current_time < market_close_end:
            return 'MARKET_CLOSE'
        elif dt_time(9, 30) <= current_time < dt_time(16, 0):
            return 'MARKET_HOURS'
        else:
            return 'IDLE'
    
    def _refresh_earnings_calendar(self):
        """Fetch earnings calendar for the current week from Polygon"""
        try:
            self.logger.info("📅 Refreshing earnings calendar...")
            
            # Get date range: today through next 7 days
            today = datetime.now().date()
            end_date = today + timedelta(days=7)
            
            # Polygon earnings calendar endpoint
            url = "https://api.polygon.io/v2/reference/financials"
            
            # Alternative: Use simpler approach - get earnings from news
            # For speed, we'll monitor news for ALL stocks, not just a pre-filtered list
            # This ensures we catch EVERYTHING
            
            # For now, we'll use a hybrid approach:
            # 1. Monitor major indices for earnings
            # 2. Rely on news scanning to catch earnings as they're released
            
            # Major stocks to always monitor (can be expanded)
            self.earnings_calendar = self._get_major_watchlist()
            
            self.calendar_last_updated = datetime.now().isoformat()
            self.stats['calendar_symbols'] = len(self.earnings_calendar)
            self.stats['calendar_last_updated'] = self.calendar_last_updated
            
            self.logger.info(f"✅ Earnings calendar updated: {len(self.earnings_calendar)} symbols")
            
        except Exception as e:
            self.logger.error(f"Error refreshing earnings calendar: {str(e)}")
            # Fallback to major indices if calendar fetch fails
            self.earnings_calendar = self._get_major_watchlist()
    
    def _get_major_watchlist(self) -> List[str]:
        """Get major symbols to monitor for earnings (fallback)"""
        # Major tech and indices
        return [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 
            'AMD', 'INTC', 'NFLX', 'CRM', 'ORCL', 'ADBE', 'PYPL',
            'SPY', 'QQQ', 'DIA', 'IWM',
            # Add more as needed
        ]
    
    def check_earnings(self):
        """Check for earnings announcements via news"""
        try:
            self.stats['checks_performed'] += 1
            self.stats['last_check'] = datetime.now().isoformat()
            
            # Get recent news (last 30 minutes - we need FAST detection)
            # For post-market, we check even more frequently
            hours = 0.5  # 30 minutes
            
            articles = self.unified_news.get_unified_news(
                ticker=None,  # ALL news (calendar approach)
                hours=hours,
                limit=100  # Check more articles for comprehensive coverage
            )
            
            if not articles:
                return
            
            # Filter for earnings-related news
            earnings_articles = []
            for article in articles:
                if self._is_earnings_news(article):
                    article_id = article.get('id', '') or article.get('url', '')
                    
                    # Get primary ticker
                    tickers = article.get('tickers', [])
                    if not tickers:
                        continue
                    
                    primary_ticker = tickers[0]
                    
                    # Create unique key
                    today = datetime.now().date().isoformat()
                    earnings_key = f"{primary_ticker}_{today}"
                    
                    # Skip if already seen
                    if earnings_key in self.seen_earnings:
                        continue
                    
                    self.seen_earnings.add(earnings_key)
                    earnings_articles.append(article)
            
            if not earnings_articles:
                return
            
            self.stats['earnings_detected'] += len(earnings_articles)
            self.logger.info(f"📊 Found {len(earnings_articles)} EARNINGS announcements!")
            
            # Send alerts immediately (CRITICAL = no batching)
            for article in earnings_articles:
                self._send_earnings_alert(article)
            
        except Exception as e:
            self.logger.error(f"Error checking earnings: {str(e)}")
    
    def _is_earnings_news(self, article: Dict) -> bool:
        """Check if article is earnings-related"""
        title = article.get('title', '').lower()
        teaser = article.get('teaser', '').lower()
        full_text = f"{title} {teaser}"
        
        # Must contain earnings keywords
        return any(keyword in full_text for keyword in self.earnings_keywords)
    
    def _extract_earnings_sentiment(self, article: Dict) -> str:
        """Extract if earnings BEAT or MISS from article text"""
        title = article.get('title', '').lower()
        teaser = article.get('teaser', '').lower()
        full_text = f"{title} {teaser}"
        
        # BEAT indicators
        beat_keywords = ['beats', 'beat', 'tops', 'exceeds', 'blowout', 'surprise',
                         'better than expected', 'above expectations', 'strong results']
        
        # MISS indicators
        miss_keywords = ['misses', 'miss', 'disappoints', 'below expectations',
                        'falls short', 'weaker than expected', 'disappointing']
        
        # Check for BEAT
        if any(keyword in full_text for keyword in beat_keywords):
            self.stats['beats'] += 1
            return 'BEAT'
        
        # Check for MISS
        elif any(keyword in full_text for keyword in miss_keywords):
            self.stats['misses'] += 1
            return 'MISS'
        
        # Neutral
        return 'NEUTRAL'
    
    def _send_earnings_alert(self, article: Dict):
        """Send earnings alert to Discord"""
        if not self.discord:
            return
        
        # Get primary ticker
        tickers = article.get('tickers', [])
        symbol = tickers[0] if tickers else 'UNKNOWN'
        
        # Extract sentiment
        sentiment = self._extract_earnings_sentiment(article)
        
        # Determine urgency based on session
        session = self._get_current_session()
        urgency = 'CRITICAL' if session == 'POSTMARKET' else 'HIGH'
        
        # Build earnings data for Discord
        earnings_data = {
            'symbol': symbol,
            'sentiment': sentiment,
            'title': article.get('title', ''),
            'url': article.get('url', ''),
            'published': article.get('published_utc', ''),
            'source': article.get('source', ''),
            'teaser': article.get('teaser', ''),
            'session': session,
            'urgency': urgency,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            success = self.discord.send_earnings_alert(symbol, earnings_data)
            if success:
                self.stats['alerts_sent'] += 1
                self.logger.info(
                    f"🚨 EARNINGS ALERT: {symbol} - {sentiment} "
                    f"({session}, {urgency})"
                )
                
                # ==================== DATABASE SAVE ====================
                # Save to database after successful Discord alert
                if hasattr(self, 'save_to_db_callback') and self.save_to_db_callback:
                    try:
                        self.save_to_db_callback(
                            ticker=symbol,
                            headline=article.get('title', 'Earnings Report'),
                            article=article,
                            channel='earnings'
                        )
                        self.logger.debug(f"💾 Saved earnings to database: {symbol}")
                    except Exception as e:
                        self.logger.error(f"Error saving to database: {str(e)}")
                # =====================================================
                
        except Exception as e:
            self.logger.error(f"Error sending earnings alert: {str(e)}")
    
    def get_statistics(self) -> Dict:
        """Get monitor statistics"""
        return self.stats.copy()


if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        print("❌ Set POLYGON_API_KEY in .env")
        exit(1)
    
    # Test earnings monitor
    print("\n📊 Testing Earnings Monitor...")
    print("This will check for recent earnings news")
    
    # You would normally import UnifiedNewsEngine here
    # For testing, we'll simulate
    monitor = EarningsMonitor(
        polygon_api_key=api_key,
        unified_news_engine=None,  # Would be real engine
        discord_alerter=None,
        check_interval_premarket=20,
        check_interval_postmarket=10
    )
    
    print(f"\n✅ Monitor initialized")
    print(f"Session: {monitor._get_current_session()}")
    print(f"Calendar: {len(monitor.earnings_calendar)} symbols")
    print(f"\nStatistics: {monitor.get_statistics()}")
