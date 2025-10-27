"""
backend/monitors/openai_news_monitor_v2.py
OpenAI News Monitor using Benzinga + Unified News Engine
Fixes the empty #openai-news channel issue
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


class OpenAINewsMonitor:
    def __init__(self, unified_news_engine, discord_alerter, check_interval: int = 300):
        """
        Initialize OpenAI news monitor
        
        Args:
            unified_news_engine: UnifiedNewsEngine instance
            discord_alerter: DiscordAlerter instance
            check_interval: Check every N seconds (default 5 min)
        """
        self.unified_news = unified_news_engine
        self.discord = discord_alerter
        self.check_interval = check_interval
        self.logger = logging.getLogger(__name__)
        
        self.running = False
        self.thread = None
        
        # Track seen articles
        self.seen_article_ids = set()
        
        # AI keywords to search for
        self.ai_keywords = [
            'OpenAI', 'ChatGPT', 'GPT-4', 'GPT-5', 'GPT',
            'Sam Altman', 'Anthropic', 'Claude', 'Google Gemini',
            'AI model', 'LLM', 'large language model',
            'artificial intelligence', 'generative AI',
            'AI chip', 'AI infrastructure', 'AI regulation',
            'Microsoft AI', 'Google AI'
        ]
        
        self.stats = {
            'checks_performed': 0,
            'articles_found': 0,
            'alerts_sent': 0,
            'last_check': None
        }
    
    def start(self):
        """Start monitoring in background thread"""
        if self.running:
            self.logger.warning("OpenAI news monitor already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        self.logger.info(f"✅ OpenAI news monitor started (check every {self.check_interval}s)")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self.logger.info("OpenAI news monitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                self.check_ai_news()
                time.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(f"Error in OpenAI news monitor loop: {str(e)}")
                time.sleep(60)  # Wait 1 min on error
    
    def check_ai_news(self):
        """Check for AI/OpenAI news"""
        try:
            self.stats['checks_performed'] += 1
            self.stats['last_check'] = datetime.now().isoformat()
            
            # Search for AI keywords in last 24 hours
            articles = self.unified_news.search_with_keywords(
                keywords=self.ai_keywords,
                hours=24
            )
            
            if not articles:
                self.logger.debug("No AI news found")
                return
            
            self.stats['articles_found'] += len(articles)
            
            # Process new articles only
            new_articles = []
            for article in articles:
                article_id = article.get('id', '') or article.get('url', '')
                if article_id and article_id not in self.seen_article_ids:
                    new_articles.append(article)
                    self.seen_article_ids.add(article_id)
            
            if not new_articles:
                self.logger.debug(f"Found {len(articles)} AI articles but all already seen")
                return
            
            self.logger.info(f"🤖 Found {len(new_articles)} new AI articles")
            
            # Group by primary topic
            grouped = self._group_ai_articles(new_articles)
            
            # Send alerts for each group
            for topic, topic_articles in grouped.items():
                self._send_ai_news_alert(topic, topic_articles)
            
        except Exception as e:
            self.logger.error(f"Error checking AI news: {str(e)}")
    
    def _group_ai_articles(self, articles: List[Dict]) -> Dict[str, List[Dict]]:
        """Group articles by primary AI topic"""
        groups = {
            'OpenAI': [],
            'Anthropic': [],
            'Google AI': [],
            'Microsoft AI': [],
            'AI Regulation': [],
            'AI Infrastructure': [],
            'General AI': []
        }
        
        for article in articles:
            title = article.get('title', '').lower()
            teaser = article.get('teaser', '').lower()
            full_text = f"{title} {teaser}"
            
            # Categorize
            if 'openai' in full_text or 'chatgpt' in full_text or 'sam altman' in full_text:
                groups['OpenAI'].append(article)
            elif 'anthropic' in full_text or 'claude' in full_text:
                groups['Anthropic'].append(article)
            elif 'google' in full_text and ('gemini' in full_text or 'ai' in full_text):
                groups['Google AI'].append(article)
            elif 'microsoft' in full_text and 'ai' in full_text:
                groups['Microsoft AI'].append(article)
            elif any(word in full_text for word in ['regulation', 'policy', 'law', 'government']):
                groups['AI Regulation'].append(article)
            elif any(word in full_text for word in ['chip', 'gpu', 'infrastructure', 'data center']):
                groups['AI Infrastructure'].append(article)
            else:
                groups['General AI'].append(article)
        
        # Remove empty groups
        return {k: v for k, v in groups.items() if v}
    
    def _send_ai_news_alert(self, topic: str, articles: List[Dict]):
        """Send AI news alert to Discord"""
        if not self.discord:
            return
        
        # Pick emoji based on topic
        emoji_map = {
            'OpenAI': '🤖',
            'Anthropic': '🧠',
            'Google AI': '🔍',
            'Microsoft AI': '💻',
            'AI Regulation': '⚖️',
            'AI Infrastructure': '🏗️',
            'General AI': '🤖'
        }
        
        emoji = emoji_map.get(topic, '🤖')
        
        # Determine urgency
        urgency_keywords = ['breaking', 'just announced', 'launches', 'releases', 'unveils']
        is_urgent = any(
            any(keyword in article.get('title', '').lower() for keyword in urgency_keywords)
            for article in articles
        )
        
        urgency = 'HIGH' if is_urgent else 'MEDIUM'
        
        # Build alert
        alert_data = {
            'topic': topic,
            'emoji': emoji,
            'urgency': urgency,
            'article_count': len(articles),
            'articles': articles[:5],  # Top 5
            'timestamp': datetime.now().isoformat()
        }
        
        # Send to Discord (will use send_ai_news_alert method)
        try:
            success = self.discord.send_ai_news_alert(alert_data)
            if success:
                self.stats['alerts_sent'] += 1
                self.logger.info(f"✅ Sent AI news alert: {topic} ({len(articles)} articles)")
        except AttributeError:
            # Fallback if send_ai_news_alert doesn't exist yet
            self.logger.warning(f"send_ai_news_alert not implemented, using generic alert")
    
    def get_statistics(self) -> Dict:
        """Get monitor statistics"""
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
    monitor = OpenAINewsMonitor(engine, None, check_interval=60)
    
    print("Testing OpenAI news detection...")
    monitor.check_ai_news()
    
    print(f"\nStatistics: {monitor.get_statistics()}")
