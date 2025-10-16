"""
backend/monitors/openai_news_monitor.py
OpenAI News Monitor with Volume Confirmation
Monitors news for OpenAI mentions + confirms with volume spikes
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import requests
import logging
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from collections import defaultdict
import hashlib

from analyzers.volume_analyzer import VolumeAnalyzer


class OpenAINewsMonitor:
    def __init__(self, polygon_api_key: str, config: Dict):
        """
        Initialize OpenAI News Monitor
        
        Args:
            polygon_api_key: Polygon.io API key
            config: Configuration dictionary from config.yaml
        """
        self.logger = logging.getLogger(__name__)
        self.api_key = polygon_api_key
        self.base_url = "https://api.polygon.io"
        
        # Configuration
        self.config = config.get('openai_monitor', {})
        self.enabled = self.config.get('enabled', True)
        self.check_interval = self.config.get('check_interval', 60)
        self.lookback_hours = self.config.get('lookback_hours', 2)
        self.max_alerts_per_hour = self.config.get('max_alerts_per_hour', 10)
        
        # Keywords to monitor
        self.keywords = self.config.get('keywords', [
            'OpenAI', 'Open AI', 'ChatGPT', 'GPT-4', 'GPT-5', 
            'Sam Altman', 'Altman'
        ])
        
        # Load tech stocks
        self.tech_stocks = self._load_tech_stocks()
        self.priority_stocks = self.config.get('priority_tickers', [])
        
        # Volume confirmation settings
        self.volume_config = self.config.get('volume_confirmation', {})
        self.volume_enabled = self.volume_config.get('enabled', True)
        self.min_rvol = self.volume_config.get('min_rvol_for_alert', 1.5)
        self.critical_rvol = self.volume_config.get('critical_rvol', 2.5)
        self.confirmation_window = self.volume_config.get('confirmation_window', 300)
        
        # Initialize volume analyzer
        self.volume_analyzer = None
        if self.volume_enabled:
            try:
                self.volume_analyzer = VolumeAnalyzer(polygon_api_key)
                self.logger.info("✅ Volume analyzer enabled for OpenAI monitor")
            except Exception as e:
                self.logger.error(f"⚠️ Volume analyzer failed: {str(e)}")
        
        # Alert tracking
        self.seen_news_hashes: Set[str] = set()
        self.alert_counts = defaultdict(int)
        self.last_alert_reset = datetime.now()
        self.pending_confirmations: Dict[str, Dict] = {}
        
        # Impact scoring
        self.min_impact_score = self.config.get('min_impact_score', 6.0)
        self.tier1_sources = ['bloomberg', 'reuters', 'wsj', 'financial times']
        self.tier2_sources = ['cnbc', 'yahoo finance', 'marketwatch', 'seeking alpha']
        
        # Discord webhook
        self.discord_webhook = None
        
        # Stats
        self.stats = {
            'news_detected': 0,
            'volume_confirmed': 0,
            'alerts_sent': 0,
            'false_positives_filtered': 0
        }
        
        self.logger.info("✅ OpenAI News Monitor initialized")
        self.logger.info(f"   Keywords: {', '.join(self.keywords)}")
        self.logger.info(f"   Tech stocks: {len(self.tech_stocks)}")
        self.logger.info(f"   Volume confirmation: {'ENABLED' if self.volume_enabled else 'DISABLED'}")
    
    def _load_tech_stocks(self) -> List[str]:
        """Load tech stock tickers from config"""
        # Try to load from JSON file first
        tech_file = Path(__file__).parent.parent / 'config' / 'tech_stocks.json'
        
        if tech_file.exists():
            try:
                with open(tech_file, 'r') as f:
                    data = json.load(f)
                stocks = data.get('tickers', [])
                self.logger.info(f"📊 Loaded {len(stocks)} tech stocks from file")
                return stocks
            except Exception as e:
                self.logger.error(f"Error loading tech stocks: {str(e)}")
        
        # Fallback to default tech stocks
        default_stocks = [
            # Chip stocks (priority)
            'NVDA', 'AMD', 'AVGO', 'TSM', 'INTC', 'QCOM', 'ASML', 'MU', 'MRVL', 'ON',
            'AMAT', 'KLAC', 'LRCX', 'NXPI', 'TXN', 'ADI',
            
            # Cloud/AI infrastructure
            'MSFT', 'GOOGL', 'AMZN', 'META', 'ORCL', 'IBM', 'CRM', 'NOW',
            
            # Software/SaaS
            'ADBE', 'INTU', 'SNOW', 'DDOG', 'NET', 'PLTR', 'CRWD',
            
            # Other tech
            'AAPL', 'TSLA', 'UBER', 'ABNB', 'SHOP', 'SQ', 'COIN'
        ]
        
        self.logger.info(f"📊 Using {len(default_stocks)} default tech stocks")
        return default_stocks
    
    def set_discord_webhook(self, webhook_url: str):
        """Set Discord webhook URL"""
        self.discord_webhook = webhook_url
        self.logger.info("✅ Discord webhook configured for OpenAI monitor")
    
    def _make_request(self, endpoint: str, params: dict = None, retries: int = 3) -> dict:
        """Make Polygon API request with retry logic"""
        if params is None:
            params = {}
        
        params['apiKey'] = self.api_key
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(retries):
            try:
                # 20 second timeout should be sufficient with filtered queries
                response = requests.get(url, params=params, timeout=20)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout as e:
                if attempt < retries - 1:
                    self.logger.warning(f"Request timeout, retrying ({attempt + 1}/{retries})...")
                    time.sleep(2)  # Wait 2 seconds before retry
                    continue
                else:
                    self.logger.error(f"API request timed out after {retries} attempts")
                    return {}
            except requests.exceptions.RequestException as e:
                if attempt < retries - 1:
                    self.logger.warning(f"API error, retrying ({attempt + 1}/{retries}): {str(e)}")
                    time.sleep(2)
                    continue
                else:
                    self.logger.error(f"API request failed after {retries} attempts: {str(e)}")
                    return {}
        
        return {}
    
    def _create_news_hash(self, title: str, published: str) -> str:
        """Create unique hash for news article"""
        hash_str = f"{title}_{published}"
        return hashlib.md5(hash_str.encode()).hexdigest()
    
    def _extract_tickers_from_article(self, article: Dict) -> List[str]:
        """Extract stock tickers mentioned in article"""
        tickers = set()
        
        # Check tickers field
        article_tickers = article.get('tickers', [])
        for ticker in article_tickers:
            if ticker in self.tech_stocks:
                tickers.add(ticker)
        
        # Check insights
        insights = article.get('insights', [])
        for insight in insights:
            ticker = insight.get('ticker')
            if ticker and ticker in self.tech_stocks:
                tickers.add(ticker)
        
        return list(tickers)
    
    def _check_keyword_match(self, article: Dict) -> bool:
        """Check if article contains any of our keywords"""
        title = article.get('title', '').lower()
        description = article.get('description', '').lower()
        
        for keyword in self.keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in title or keyword_lower in description:
                return True
        
        return False
    
    def _calculate_news_freshness_score(self, published_utc: str) -> float:
        """Calculate freshness score (0-3 points)"""
        try:
            pub_time = datetime.strptime(published_utc, '%Y-%m-%dT%H:%M:%SZ')
            age_minutes = (datetime.utcnow() - pub_time).total_seconds() / 60
            
            if age_minutes < 5:
                return 3.0
            elif age_minutes < 15:
                return 2.0
            elif age_minutes < 60:
                return 1.0
            else:
                return 0.0
        except:
            return 0.0
    
    def _calculate_source_tier_score(self, publisher: Dict) -> float:
        """Calculate source tier score (0-2 points)"""
        name = publisher.get('name', '').lower()
        
        for tier1 in self.tier1_sources:
            if tier1 in name:
                return 2.0
        
        for tier2 in self.tier2_sources:
            if tier2 in name:
                return 1.0
        
        return 0.0
    
    def _calculate_keyword_strength_score(self, article: Dict) -> float:
        """Calculate keyword match strength (0-1 point)"""
        title = article.get('title', '').lower()
        
        strong_keywords = ['partnership', 'deal', 'contract', 'agreement', 
                          'announces', 'signs', 'collaboration']
        
        for keyword in strong_keywords:
            if keyword in title:
                return 1.0
        
        return 0.0
    
    def _check_volume_confirmation(self, tickers: List[str]) -> Dict[str, Dict]:
        """Check volume for confirmation"""
        confirmations = {}
        
        if not self.volume_analyzer:
            return confirmations
        
        for ticker in tickers:
            try:
                volume_data = self.volume_analyzer.calculate_rvol(ticker)
                
                rvol = volume_data.get('rvol', 0)
                classification = volume_data.get('classification', 'UNKNOWN')
                
                confirmations[ticker] = {
                    'rvol': rvol,
                    'classification': classification,
                    'confirmed': rvol >= self.min_rvol,
                    'critical': rvol >= self.critical_rvol
                }
                
            except Exception as e:
                self.logger.error(f"Volume check failed for {ticker}: {str(e)}")
                confirmations[ticker] = {'rvol': 0, 'confirmed': False}
        
        return confirmations
    
    def _calculate_impact_score(self, article: Dict, volume_confirmations: Dict) -> float:
        """
        Calculate overall impact score (0-10)
        
        Components:
        - News freshness: 0-3 points
        - RVOL strength: 0-4 points
        - Source tier: 0-2 points
        - Keyword strength: 0-1 point
        """
        score = 0.0
        
        # Freshness
        published = article.get('published_utc', '')
        score += self._calculate_news_freshness_score(published)
        
        # Volume confirmation (highest RVOL among tickers)
        if volume_confirmations:
            max_rvol = max([v.get('rvol', 0) for v in volume_confirmations.values()])
            
            if max_rvol >= 3.0:
                score += 4.0
            elif max_rvol >= 2.0:
                score += 3.0
            elif max_rvol >= 1.5:
                score += 2.0
        
        # Source tier
        publisher = article.get('publisher', {})
        score += self._calculate_source_tier_score(publisher)
        
        # Keyword strength
        score += self._calculate_keyword_strength_score(article)
        
        return score
    
    def check_for_openai_news(self) -> List[Dict]:
        """
        Check Polygon News API for OpenAI mentions
        
        Returns:
            List of articles with OpenAI mentions + volume confirmation
        """
        try:
            # Reset hourly counters
            if (datetime.now() - self.last_alert_reset).seconds >= 3600:
                self.alert_counts.clear()
                self.last_alert_reset = datetime.now()
            
            # Check rate limit
            if sum(self.alert_counts.values()) >= self.max_alerts_per_hour:
                self.logger.debug("Rate limit reached for this hour")
                return []
            
            # Query Polygon News API with time filter for efficiency
            endpoint = "/v2/reference/news"
            
            # Only fetch news from last 2 hours to reduce payload
            cutoff_time = datetime.utcnow() - timedelta(hours=self.lookback_hours)
            
            params = {
                'limit': 20,  # Smaller limit for faster response
                'order': 'desc',
                'published_utc.gte': cutoff_time.strftime('%Y-%m-%dT%H:%M:%SZ')  # Time filter
            }
            
            data = self._make_request(endpoint, params)
            
            if not data:
                self.logger.debug("No response from news API")
                return []
            
            if 'results' not in data:
                self.logger.debug("No news results in API response")
                return []
            
            articles = data['results']
            
            if not articles:
                self.logger.debug("No articles returned from news API")
                return []
            
            matched_articles = []
            
            for article in articles:
                # Check if article is recent enough
                published = article.get('published_utc', '')
                try:
                    pub_time = datetime.strptime(published, '%Y-%m-%dT%H:%M:%SZ')
                    age_hours = (datetime.utcnow() - pub_time).total_seconds() / 3600
                    
                    if age_hours > self.lookback_hours:
                        continue
                except:
                    continue
                
                # Check for keyword match
                if not self._check_keyword_match(article):
                    continue
                
                # Check if already alerted
                news_hash = self._create_news_hash(
                    article.get('title', ''),
                    published
                )
                
                if news_hash in self.seen_news_hashes:
                    continue
                
                # Extract tickers
                tickers = self._extract_tickers_from_article(article)
                
                if not tickers:
                    self.logger.debug(f"No tech stocks found in article: {article.get('title', '')[:50]}")
                    continue
                
                self.stats['news_detected'] += 1
                
                # Volume confirmation
                volume_confirmations = {}
                if self.volume_enabled:
                    volume_confirmations = self._check_volume_confirmation(tickers)
                    
                    # Filter out non-confirmed tickers if required
                    if self.config.get('include_unconfirmed', False) is False:
                        confirmed_tickers = [
                            t for t, v in volume_confirmations.items() 
                            if v.get('confirmed', False)
                        ]
                        
                        if not confirmed_tickers:
                            self.logger.info(
                                f"News detected but no volume confirmation: "
                                f"{article.get('title', '')[:50]}"
                            )
                            self.stats['false_positives_filtered'] += 1
                            continue
                        
                        tickers = confirmed_tickers
                
                # Calculate impact score
                impact_score = self._calculate_impact_score(article, volume_confirmations)
                
                if impact_score < self.min_impact_score:
                    self.logger.debug(
                        f"Impact score too low ({impact_score:.1f}): "
                        f"{article.get('title', '')[:50]}"
                    )
                    self.stats['false_positives_filtered'] += 1
                    continue
                
                # Mark as seen
                self.seen_news_hashes.add(news_hash)
                
                # Track volume confirmation
                if any(v.get('confirmed') for v in volume_confirmations.values()):
                    self.stats['volume_confirmed'] += 1
                
                # Build alert data
                matched_articles.append({
                    'article': article,
                    'tickers': tickers,
                    'volume_confirmations': volume_confirmations,
                    'impact_score': impact_score,
                    'news_hash': news_hash
                })
            
            return matched_articles
            
        except Exception as e:
            self.logger.error(f"Error checking OpenAI news: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return []
    
    def send_discord_alert(self, alert_data: Dict) -> bool:
        """Send alert to Discord"""
        if not self.discord_webhook:
            self.logger.warning("Discord webhook not configured")
            return False
        
        try:
            article = alert_data['article']
            tickers = alert_data['tickers']
            volume_confirmations = alert_data['volume_confirmations']
            impact_score = alert_data['impact_score']
            
            # Determine alert level
            if impact_score >= 8.0:
                alert_level = '🔴 CRITICAL'
                color = 0xff0000
            elif impact_score >= 6.0:
                alert_level = '🟡 HIGH'
                color = 0xffaa00
            else:
                alert_level = '🟢 INFO'
                color = 0x00ff00
            
            # Calculate time since publication
            published = article.get('published_utc', '')
            try:
                pub_time = datetime.strptime(published, '%Y-%m-%dT%H:%M:%SZ')
                age_minutes = int((datetime.utcnow() - pub_time).total_seconds() / 60)
                time_str = f"{age_minutes} minutes ago" if age_minutes < 60 else f"{age_minutes // 60} hours ago"
            except:
                time_str = "Unknown"
            
            # Build volume confirmation text
            volume_text = []
            for ticker in tickers:
                if ticker in volume_confirmations:
                    conf = volume_confirmations[ticker]
                    rvol = conf.get('rvol', 0)
                    classification = conf.get('classification', 'UNKNOWN')
                    
                    emoji = '⚠️' if conf.get('critical') else '✓' if conf.get('confirmed') else '○'
                    volume_text.append(
                        f"   • {ticker}: RVOL {rvol}x ({classification}) {emoji}"
                    )
            
            volume_section = '\n'.join(volume_text) if volume_text else '   No volume data available'
            
            # Build embed
            embed = {
                'title': f'{alert_level} OpenAI Alert - VOLUME CONFIRMED' if volume_confirmations else f'{alert_level} OpenAI Alert',
                'description': article.get('title', 'No title'),
                'color': color,
                'timestamp': datetime.utcnow().isoformat(),
                'fields': [
                    {
                        'name': '📰 Source',
                        'value': f"{article.get('publisher', {}).get('name', 'Unknown')} - {time_str}",
                        'inline': False
                    },
                    {
                        'name': '🏢 Tickers',
                        'value': ', '.join(tickers),
                        'inline': True
                    },
                    {
                        'name': '💥 Impact Score',
                        'value': f'{impact_score:.1f}/10',
                        'inline': True
                    },
                    {
                        'name': '📊 Volume Confirmation',
                        'value': volume_section,
                        'inline': False
                    },
                    {
                        'name': '🔗 Read Article',
                        'value': f"[Click here]({article.get('article_url', '#')})",
                        'inline': False
                    }
                ],
                'footer': {
                    'text': f'⚡ Detected: {time_str} | OpenAI News Monitor'
                }
            }
            
            payload = {'embeds': [embed]}
            
            response = requests.post(
                self.discord_webhook,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            
            self.stats['alerts_sent'] += 1
            self.alert_counts[datetime.now().hour] += 1
            
            self.logger.info(
                f"✅ OpenAI alert sent: {', '.join(tickers)} | "
                f"Impact: {impact_score:.1f}/10"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send Discord alert: {str(e)}")
            return False
    
    def run_single_check(self) -> int:
        """Run a single check cycle"""
        if not self.enabled:
            self.logger.debug("OpenAI monitor disabled")
            return 0
        
        # Always log checks for visibility
        self.logger.info("🔍 Checking for OpenAI news...")
        
        matched_articles = self.check_for_openai_news()
        
        if not matched_articles:
            self.logger.info("✅ Check complete - No new OpenAI news found")
            return 0
        
        alerts_sent = 0
        
        for alert_data in matched_articles:
            success = self.send_discord_alert(alert_data)
            if success:
                alerts_sent += 1
        
        return alerts_sent
    
    def run_continuous(self):
        """Run continuous monitoring"""
        self.logger.info("Starting OpenAI news monitor...")
        self.logger.info(f"Check interval: {self.check_interval}s")
        self.logger.info(f"Volume confirmation: {'ENABLED' if self.volume_enabled else 'DISABLED'}")
        
        try:
            while True:
                try:
                    alerts_sent = self.run_single_check()
                    
                    if alerts_sent > 0:
                        self.logger.info(f"Sent {alerts_sent} OpenAI alerts")
                    
                except Exception as e:
                    self.logger.error(f"Error in check cycle: {str(e)}")
                
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            self.logger.info("Stopping OpenAI monitor...")
            self.print_stats()
    
    def print_stats(self):
        """Print statistics"""
        print("\n" + "=" * 60)
        print("OPENAI NEWS MONITOR STATISTICS")
        print("=" * 60)
        print(f"News Detected: {self.stats['news_detected']}")
        print(f"Volume Confirmed: {self.stats['volume_confirmed']}")
        print(f"Alerts Sent: {self.stats['alerts_sent']}")
        print(f"False Positives Filtered: {self.stats['false_positives_filtered']}")
        print("=" * 60 + "\n")


# CLI Testing
def main():
    """Command-line interface for testing"""
    import sys
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    api_key = os.getenv('POLYGON_API_KEY')
    webhook = os.getenv('DISCORD_OPENAI_NEWS')
    
    if not api_key:
        print("❌ POLYGON_API_KEY not found")
        sys.exit(1)
    
    # Test config
    config = {
        'openai_monitor': {
            'enabled': True,
            'check_interval': 60,
            'lookback_hours': 2,
            'max_alerts_per_hour': 10,
            'keywords': ['OpenAI', 'ChatGPT', 'GPT-4', 'Sam Altman'],
            'volume_confirmation': {
                'enabled': True,
                'min_rvol_for_alert': 1.5,
                'critical_rvol': 2.5
            },
            'min_impact_score': 6.0,
            'include_unconfirmed': False
        }
    }
    
    monitor = OpenAINewsMonitor(api_key, config)
    
    if webhook:
        monitor.set_discord_webhook(webhook)
    
    if len(sys.argv) > 1 and sys.argv[1] == 'run':
        print("Starting continuous monitoring...")
        print("Press Ctrl+C to stop")
        monitor.run_continuous()
    else:
        print("Running single check...")
        alerts = monitor.run_single_check()
        print(f"\n✅ Check complete: {alerts} alerts sent")
        monitor.print_stats()


if __name__ == '__main__':
    main()