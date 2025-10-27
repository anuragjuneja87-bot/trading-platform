"""
backend/monitors/macro_news_detector.py
Macro/Critical News Detector - Fed, Tariffs, Economic Data
Routes to #news-alerts with CRITICAL priority
"""

import sys
from pathlib import Path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import threading
import time
import logging
from datetime import datetime
from typing import Dict, List


class MacroNewsDetector:
    def __init__(self, unified_news_engine, discord_alerter, check_interval: int = 30):
        """
        Initialize macro news detector
        
        Args:
            unified_news_engine: UnifiedNewsEngine instance
            discord_alerter: DiscordAlerter instance
            check_interval: Check every N seconds (default 30s for critical news)
        """
        self.unified_news = unified_news_engine
        self.discord = discord_alerter
        self.check_interval = check_interval
        self.logger = logging.getLogger(__name__)
        
        self.running = False
        self.thread = None
        
        # Track seen articles
        self.seen_article_ids = set()
        
        # CRITICAL macro keywords
        self.macro_keywords = {
            'FED': ['fed ', 'fomc', 'federal reserve', 'powell', 'jerome powell',
                   'interest rate decision', 'rate cut', 'rate hike', 'fed meeting',
                   'fed chairman', 'monetary policy', 'fed minutes'],
            
            'TARIFFS': ['tariff', 'tariffs', 'trade war', 'china tariff', 'trump tariff',
                       'import duty', 'trade tensions', 'trade deal', 'trade negotiations'],
            
            'ECONOMIC_DATA': ['cpi ', 'inflation data', 'jobs report', 'unemployment',
                             'nonfarm payrolls', 'gdp ', 'pce ', 'retail sales',
                             'consumer confidence', 'pmi ', 'ism ', 'housing starts'],
            
            'MARKET_EVENTS': ['market halt', 'circuit breaker', 'trading halt',
                             'market crash', 'market meltdown', 'selloff', 'sell-off',
                             'market panic', 'flash crash'],
            
            'GEOPOLITICAL': ['war ', 'conflict', 'attack', 'tensions', 'sanctions',
                            'nuclear', 'military', 'invasion', 'crisis']
        }
        
        self.stats = {
            'checks_performed': 0,
            'critical_news_found': 0,
            'alerts_sent': 0,
            'last_check': None,
            'by_category': {cat: 0 for cat in self.macro_keywords.keys()}
        }
    
    def start(self):
        """Start monitoring in background thread"""
        if self.running:
            self.logger.warning("Macro news detector already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        self.logger.info(f"🚨 Macro news detector started (check every {self.check_interval}s)")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self.logger.info("Macro news detector stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                self.check_macro_news()
                time.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(f"Error in macro news detector loop: {str(e)}")
                time.sleep(30)
    
    def check_macro_news(self):
        """Check for critical macro news"""
        try:
            self.stats['checks_performed'] += 1
            self.stats['last_check'] = datetime.now().isoformat()
            
            # Get all recent news (last 2 hours)
            articles = self.unified_news.get_unified_news(
                ticker=None,  # All news
                hours=2,
                limit=50
            )
            
            if not articles:
                return
            
            # Filter for macro news
            macro_articles = []
            for article in articles:
                article_id = article.get('id', '') or article.get('url', '')
                
                # Skip if already seen
                if article_id and article_id in self.seen_article_ids:
                    continue
                
                # Check if macro-related
                category = self._classify_macro_news(article)
                if category:
                    article['macro_category'] = category
                    macro_articles.append(article)
                    self.seen_article_ids.add(article_id)
                    self.stats['by_category'][category] += 1
            
            if not macro_articles:
                return
            
            self.stats['critical_news_found'] += len(macro_articles)
            self.logger.warning(f"🚨 Found {len(macro_articles)} CRITICAL macro news items!")
            
            # Send alerts immediately (CRITICAL = no batching)
            for article in macro_articles:
                self._send_macro_alert(article)
            
        except Exception as e:
            self.logger.error(f"Error checking macro news: {str(e)}")
    
    def _classify_macro_news(self, article: Dict) -> str:
        """Classify if article is macro news and return category"""
        title = article.get('title', '').lower()
        teaser = article.get('teaser', '').lower()
        full_text = f"{title} {teaser}"
        
        # Check each category
        for category, keywords in self.macro_keywords.items():
            for keyword in keywords:
                if keyword in full_text:
                    return category
        
        return None
    
    def _send_macro_alert(self, article: Dict):
        """Send macro news alert to Discord #news-alerts"""
        if not self.discord:
            return
        
        category = article.get('macro_category', 'UNKNOWN')
        
        # Priority mapping
        priority_map = {
            'FED': 'CRITICAL',
            'TARIFFS': 'CRITICAL',
            'ECONOMIC_DATA': 'HIGH',
            'MARKET_EVENTS': 'CRITICAL',
            'GEOPOLITICAL': 'HIGH'
        }
        
        priority = priority_map.get(category, 'HIGH')
        
        # Emoji mapping
        emoji_map = {
            'FED': '🏦',
            'TARIFFS': '⚠️',
            'ECONOMIC_DATA': '📊',
            'MARKET_EVENTS': '🚨',
            'GEOPOLITICAL': '🌍'
        }
        
        emoji = emoji_map.get(category, '🔴')
        
        # Build alert
        alert_data = {
            'category': category,
            'emoji': emoji,
            'priority': priority,
            'title': article.get('title', ''),
            'url': article.get('url', ''),
            'published': article.get('published_utc', ''),
            'source': article.get('source', ''),
            'teaser': article.get('teaser', ''),
            'timestamp': datetime.now().isoformat()
        }
        
        # Send to Discord
        try:
            success = self.discord.send_macro_news_alert(alert_data)
            if success:
                self.stats['alerts_sent'] += 1
                self.logger.warning(f"🚨 Sent CRITICAL macro alert: {category} - {article.get('title', '')[:50]}...")
        except AttributeError:
            # Fallback
            self.logger.warning(f"send_macro_news_alert not implemented yet")
    
    def get_statistics(self) -> Dict:
        """Get detector statistics"""
        return self.stats.copy()


if __name__ == '__main__':
    import os
    from news.unified_news_engine import UnifiedNewsEngine
    
    logging.basicConfig(level=logging.INFO)
    
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        print("Set POLYGON_API_KEY")
        exit(1)
    
    # Test
    engine = UnifiedNewsEngine(api_key)
    detector = MacroNewsDetector(engine, None, check_interval=30)
    
    print("Testing macro news detection...")
    detector.check_macro_news()
    
    print(f"\nStatistics: {detector.get_statistics()}")
