"""
backend/monitors/market_impact_monitor.py
Market Impact News Monitor - Real-time high-impact news alerts
Monitors: Macro events, M&A, analyst upgrades, spillover effects
Routes to: DISCORD_NEWS_ALERTS channel
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import requests
import logging
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from collections import defaultdict

from analyzers.volume_analyzer import VolumeAnalyzer


class MarketImpactMonitor:
    def __init__(self, polygon_api_key: str, config: Dict, watchlist_manager=None):
        """
        Initialize Market Impact Monitor
        
        Args:
            polygon_api_key: Polygon.io API key
            config: Configuration from config.yaml
            watchlist_manager: Watchlist manager instance
        """
        self.logger = logging.getLogger(__name__)
        self.api_key = polygon_api_key
        self.base_url = "https://api.polygon.io"
        
        # Configuration
        self.config = config.get('market_impact_monitor', {})
        self.enabled = self.config.get('enabled', True)
        self.check_interval = self.config.get('check_interval', 60)
        self.lookback_hours = self.config.get('lookback_hours', 2)
        self.max_alerts_per_hour = self.config.get('max_alerts_per_hour', 20)
        
        # Watchlist
        self.watchlist_manager = watchlist_manager
        self.watchlist = []
        if watchlist_manager:
            try:
                self.watchlist = watchlist_manager.load_symbols()
                self.logger.info(f"📊 Monitoring {len(self.watchlist)} watchlist stocks")
            except Exception as e:
                self.logger.error(f"Error loading watchlist: {str(e)}")
        
        # Keywords for different event types
        self.macro_keywords = self.config.get('macro_keywords', [
            'Fed', 'Federal Reserve', 'Powell', 'FOMC', 'interest rate',
            'tariff', 'tariffs', 'trade war', 'Trump tariff', 'China tariff',
            'Treasury', 'inflation', 'CPI', 'jobs report', 'unemployment',
            'GDP', 'recession', 'economic data', 'circuit breaker',
            'market halt', 'trading halt', 'emergency meeting'
        ])
        
        self.analyst_keywords = self.config.get('analyst_keywords', [
            'upgrade', 'downgrade', 'price target', 'initiated coverage',
            'raises target', 'lowers target', 'outperform', 'underperform',
            'buy rating', 'sell rating', 'overweight', 'underweight'
        ])
        
        self.ma_keywords = self.config.get('ma_keywords', [
            'merger', 'acquisition', 'acquires', 'acquired', 'takeover',
            'buyout', 'deal', 'to acquire', 'to buy', 'agrees to buy',
            'merger agreement', 'acquisition agreement'
        ])
        
        self.earnings_keywords = self.config.get('earnings_keywords', [
            'beats estimates', 'misses estimates', 'earnings surprise',
            'blowout earnings', 'disappointing earnings', 'eps beat',
            'revenue beat', 'guidance raised', 'guidance lowered'
        ])
        
        # Spillover mapping (NVDA -> related stocks)
        self.spillover_map = self.config.get('spillover_map', {
            'NVDA': ['NVTS', 'SMCI', 'ARM', 'AMD', 'AVGO', 'TSM', 'INTC', 'MU', 'MRVL'],
            'TSLA': ['RIVN', 'LCID', 'F', 'GM', 'CHPT'],
            'AAPL': ['QCOM', 'CIRR', 'SWKS'],
            'MSFT': ['PLTR', 'SNOW', 'DDOG', 'NET'],
            'GOOGL': ['PLTR', 'AI', 'C3AI'],
            'AMZN': ['SHOP', 'WMT', 'EBAY'],
            'CRM': ['NOW', 'SNOW', 'WDAY', 'DDOG'],
            'SQ': ['PYPL', 'COIN', 'HOOD', 'SOFI'],
            'META': ['SNAP', 'PINS', 'RBLX']
        })
        
        # Volume confirmation
        self.volume_enabled = self.config.get('volume_confirmation', {}).get('enabled', True)
        self.min_rvol = self.config.get('volume_confirmation', {}).get('min_rvol', 2.0)
        self.critical_rvol = self.config.get('volume_confirmation', {}).get('critical_rvol', 3.0)
        
        # Initialize volume analyzer
        self.volume_analyzer = None
        if self.volume_enabled:
            try:
                self.volume_analyzer = VolumeAnalyzer(polygon_api_key)
                self.logger.info("✅ Volume analyzer enabled for market impact")
            except Exception as e:
                self.logger.error(f"⚠️ Volume analyzer failed: {str(e)}")
        
        # Alert tracking
        self.seen_news_hashes: Set[str] = set()
        self.alert_counts = defaultdict(int)
        self.last_alert_reset = datetime.now()
        
        # Thresholds
        self.min_price_target_change = self.config.get('min_price_target_change_percent', 20)
        self.min_earnings_surprise = self.config.get('min_earnings_surprise_percent', 10)
        self.min_impact_score = self.config.get('min_impact_score', 7.0)
        
        # Discord webhook
        self.discord_webhook = None
        
        # Stats
        self.stats = {
            'macro_events': 0,
            'analyst_events': 0,
            'ma_events': 0,
            'earnings_events': 0,
            'spillover_events': 0,
            'volume_confirmed': 0,
            'alerts_sent': 0,
            'filtered': 0
        }
        
        self.logger.info("✅ Market Impact Monitor initialized")
        self.logger.info(f"   Macro keywords: {len(self.macro_keywords)}")
        self.logger.info(f"   Watchlist stocks: {len(self.watchlist)}")
        self.logger.info(f"   Spillover maps: {len(self.spillover_map)}")
        self.logger.info(f"   Min RVOL: {self.min_rvol}x")
    
    def set_discord_webhook(self, webhook_url: str):
        """Set Discord webhook URL"""
        self.discord_webhook = webhook_url
        self.logger.info("✅ Discord webhook configured for market impact")
    
    def _make_request(self, endpoint: str, params: dict = None, retries: int = 3) -> dict:
        """Make Polygon API request with retry logic"""
        if params is None:
            params = {}
        
        params['apiKey'] = self.api_key
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(retries):
            try:
                response = requests.get(url, params=params, timeout=20)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout:
                if attempt < retries - 1:
                    self.logger.warning(f"Timeout, retrying ({attempt + 1}/{retries})...")
                    time.sleep(2)
                    continue
                else:
                    self.logger.error("API request timed out")
                    return {}
            except requests.exceptions.RequestException as e:
                if attempt < retries - 1:
                    self.logger.warning(f"API error, retrying: {str(e)}")
                    time.sleep(2)
                    continue
                else:
                    self.logger.error(f"API request failed: {str(e)}")
                    return {}
        
        return {}
    
    def _create_news_hash(self, title: str, published: str) -> str:
        """Create unique hash for news article"""
        hash_str = f"{title}_{published}"
        return hashlib.md5(hash_str.encode()).hexdigest()
    
    def _check_keyword_match(self, text: str, keywords: List[str]) -> Optional[str]:
        """Check if text contains any keywords, return matched keyword"""
        text_lower = text.lower()
        for keyword in keywords:
            if keyword.lower() in text_lower:
                return keyword
        return None
    
    def _classify_news_event(self, article: Dict) -> Dict:
        """Classify news event type and extract details"""
        title = article.get('title', '')
        description = article.get('description', '')
        full_text = f"{title} {description}"
        
        classification = {
            'type': 'GENERAL',
            'priority': 'MEDIUM',
            'matched_keyword': None,
            'details': {}
        }
        
        # Check macro events (highest priority)
        macro_match = self._check_keyword_match(full_text, self.macro_keywords)
        if macro_match:
            classification['type'] = 'MACRO'
            classification['priority'] = 'CRITICAL'
            classification['matched_keyword'] = macro_match
            self.stats['macro_events'] += 1
            return classification
        
        # Check M&A events
        ma_match = self._check_keyword_match(full_text, self.ma_keywords)
        if ma_match:
            classification['type'] = 'M&A'
            classification['priority'] = 'HIGH'
            classification['matched_keyword'] = ma_match
            self.stats['ma_events'] += 1
            return classification
        
        # Check analyst events
        analyst_match = self._check_keyword_match(full_text, self.analyst_keywords)
        if analyst_match:
            classification['type'] = 'ANALYST'
            classification['priority'] = 'HIGH' if 'price target' in full_text.lower() else 'MEDIUM'
            classification['matched_keyword'] = analyst_match
            self.stats['analyst_events'] += 1
            
            # Try to extract price target change
            if 'raises target' in full_text.lower() or 'price target' in full_text.lower():
                # This is where we'd parse the price target increase
                # For now, we'll flag it as significant
                classification['details']['has_price_target'] = True
            
            return classification
        
        # Check earnings events
        earnings_match = self._check_keyword_match(full_text, self.earnings_keywords)
        if earnings_match:
            classification['type'] = 'EARNINGS'
            classification['priority'] = 'HIGH'
            classification['matched_keyword'] = earnings_match
            self.stats['earnings_events'] += 1
            return classification
        
        return classification
    
    def _check_spillover_opportunities(self, trigger_symbol: str, article: Dict) -> List[Dict]:
        """Check for spillover opportunities when a major stock has news"""
        if trigger_symbol not in self.spillover_map:
            return []
        
        related_stocks = self.spillover_map[trigger_symbol]
        spillover_opportunities = []
        
        self.logger.info(f"🔍 Checking spillover: {trigger_symbol} → {len(related_stocks)} related stocks")
        
        for related_symbol in related_stocks:
            try:
                # Check if related stock has volume spike
                if not self.volume_analyzer:
                    continue
                
                volume_data = self.volume_analyzer.calculate_rvol(related_symbol)
                rvol = volume_data.get('rvol', 0)
                classification = volume_data.get('classification', 'UNKNOWN')
                
                # Only alert if volume confirms (2.0x+)
                if rvol >= self.min_rvol:
                    # Get current price for % change
                    quote = self._get_quick_quote(related_symbol)
                    
                    spillover_opportunities.append({
                        'symbol': related_symbol,
                        'rvol': rvol,
                        'classification': classification,
                        'current_price': quote.get('price', 0),
                        'change_percent': quote.get('change_percent', 0),
                        'critical': rvol >= self.critical_rvol
                    })
                    
                    self.logger.info(f"  ⚡ {related_symbol}: RVOL {rvol:.1f}x ({classification})")
                
            except Exception as e:
                self.logger.error(f"Error checking spillover for {related_symbol}: {str(e)}")
                continue
        
        if spillover_opportunities:
            self.stats['spillover_events'] += 1
        
        return spillover_opportunities
    
    def _get_quick_quote(self, symbol: str) -> Dict:
        """Get quick quote for price/change"""
        try:
            endpoint = f"/v2/last/trade/{symbol}"
            data = self._make_request(endpoint)
            
            if 'results' in data:
                current_price = data['results'].get('p', 0)
                
                # Get previous close for % change
                yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                endpoint2 = f"/v2/aggs/ticker/{symbol}/range/1/day/{yesterday}/{yesterday}"
                prev_data = self._make_request(endpoint2, {'adjusted': 'true'})
                
                if 'results' in prev_data and prev_data['results']:
                    prev_close = prev_data['results'][0]['c']
                    change_percent = ((current_price - prev_close) / prev_close) * 100
                else:
                    change_percent = 0
                
                return {
                    'price': current_price,
                    'change_percent': round(change_percent, 2)
                }
        except:
            pass
        
        return {'price': 0, 'change_percent': 0}
    
    def _calculate_impact_score(self, article: Dict, classification: Dict, 
                                 volume_data: Dict = None, spillover_count: int = 0) -> float:
        """
        Calculate impact score (0-10)
        
        Components:
        - Event priority: 0-4 points (CRITICAL=4, HIGH=3, MEDIUM=2)
        - News freshness: 0-2 points (<5min=2, <30min=1)
        - Volume confirmation: 0-3 points (>3x=3, >2x=2, >1.5x=1)
        - Spillover effect: 0-1 point (spillover detected=1)
        """
        score = 0.0
        
        # Event priority
        priority = classification.get('priority', 'MEDIUM')
        if priority == 'CRITICAL':
            score += 4.0
        elif priority == 'HIGH':
            score += 3.0
        elif priority == 'MEDIUM':
            score += 2.0
        
        # News freshness
        published = article.get('published_utc', '')
        try:
            pub_time = datetime.strptime(published, '%Y-%m-%dT%H:%M:%SZ')
            age_minutes = (datetime.utcnow() - pub_time).total_seconds() / 60
            
            if age_minutes < 5:
                score += 2.0
            elif age_minutes < 30:
                score += 1.0
        except:
            pass
        
        # Volume confirmation
        if volume_data:
            rvol = volume_data.get('rvol', 0)
            if rvol >= 3.0:
                score += 3.0
            elif rvol >= 2.0:
                score += 2.0
            elif rvol >= 1.5:
                score += 1.0
        
        # Spillover effect
        if spillover_count > 0:
            score += 1.0
        
        return score
    
    def check_for_market_impact_news(self) -> List[Dict]:
        """Check for high-impact market news"""
        try:
            # Reset hourly counters
            if (datetime.now() - self.last_alert_reset).seconds >= 3600:
                self.alert_counts.clear()
                self.last_alert_reset = datetime.now()
            
            # Check rate limit
            if sum(self.alert_counts.values()) >= self.max_alerts_per_hour:
                self.logger.debug("Rate limit reached")
                return []
            
            # Query Polygon News API
            endpoint = "/v2/reference/news"
            cutoff_time = datetime.utcnow() - timedelta(hours=self.lookback_hours)
            
            params = {
                'limit': 30,
                'order': 'desc',
                'published_utc.gte': cutoff_time.strftime('%Y-%m-%dT%H:%M:%SZ')
            }
            
            data = self._make_request(endpoint, params)
            
            if not data or 'results' not in data:
                return []
            
            articles = data['results']
            matched_articles = []
            
            for article in articles:
                # Check if recent enough
                published = article.get('published_utc', '')
                try:
                    pub_time = datetime.strptime(published, '%Y-%m-%dT%H:%M:%SZ')
                    age_hours = (datetime.utcnow() - pub_time).total_seconds() / 3600
                    
                    if age_hours > self.lookback_hours:
                        continue
                except:
                    continue
                
                # Check if already alerted
                news_hash = self._create_news_hash(article.get('title', ''), published)
                if news_hash in self.seen_news_hashes:
                    continue
                
                # Classify the news event
                classification = self._classify_news_event(article)
                
                # Skip general news
                if classification['type'] == 'GENERAL':
                    continue
                
                # Extract tickers
                tickers = article.get('tickers', [])
                
                # For macro events, we monitor all watchlist stocks
                if classification['type'] == 'MACRO':
                    tickers = ['SPY', 'QQQ']  # Use indices as markers
                
                # Filter to watchlist stocks (except macro events)
                if classification['type'] != 'MACRO':
                    tickers = [t for t in tickers if t in self.watchlist or t in ['SPY', 'QQQ']]
                
                if not tickers:
                    continue
                
                # Volume confirmation
                volume_confirmations = {}
                spillover_opportunities = []
                
                for ticker in tickers[:3]:  # Check top 3 tickers
                    if self.volume_analyzer and ticker not in ['SPY', 'QQQ']:
                        try:
                            vol_data = self.volume_analyzer.calculate_rvol(ticker)
                            rvol = vol_data.get('rvol', 0)
                            
                            if rvol >= self.min_rvol:
                                volume_confirmations[ticker] = vol_data
                                self.stats['volume_confirmed'] += 1
                            
                            # Check spillover
                            spillover = self._check_spillover_opportunities(ticker, article)
                            if spillover:
                                spillover_opportunities.extend(spillover)
                        
                        except Exception as e:
                            self.logger.error(f"Volume check failed for {ticker}: {str(e)}")
                
                # Calculate impact score
                primary_volume = volume_confirmations.get(tickers[0], {}) if tickers else {}
                impact_score = self._calculate_impact_score(
                    article, 
                    classification,
                    primary_volume,
                    len(spillover_opportunities)
                )
                
                # Filter by impact score
                if impact_score < self.min_impact_score:
                    self.stats['filtered'] += 1
                    continue
                
                # Mark as seen
                self.seen_news_hashes.add(news_hash)
                
                # Build alert data
                matched_articles.append({
                    'article': article,
                    'tickers': tickers,
                    'classification': classification,
                    'volume_confirmations': volume_confirmations,
                    'spillover_opportunities': spillover_opportunities,
                    'impact_score': impact_score,
                    'news_hash': news_hash
                })
            
            return matched_articles
            
        except Exception as e:
            self.logger.error(f"Error checking market impact news: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return []
    
    def send_discord_alert(self, alert_data: Dict) -> bool:
        """Send market impact alert to Discord"""
        if not self.discord_webhook:
            self.logger.warning("Discord webhook not configured")
            return False
        
        try:
            article = alert_data['article']
            tickers = alert_data['tickers']
            classification = alert_data['classification']
            volume_confirmations = alert_data['volume_confirmations']
            spillover_opportunities = alert_data['spillover_opportunities']
            impact_score = alert_data['impact_score']
            
            # Determine alert styling
            event_type = classification['type']
            priority = classification['priority']
            
            if priority == 'CRITICAL':
                emoji = '🔴'
                color = 0xff0000
            elif priority == 'HIGH':
                emoji = '🟡'
                color = 0xffaa00
            else:
                emoji = '🟢'
                color = 0x00ff00
            
            # Event type emojis
            type_emoji = {
                'MACRO': '🌍',
                'M&A': '🤝',
                'ANALYST': '📊',
                'EARNINGS': '💰',
                'GENERAL': '📰'
            }.get(event_type, '📰')
            
            # Calculate time since publication
            published = article.get('published_utc', '')
            try:
                pub_time = datetime.strptime(published, '%Y-%m-%dT%H:%M:%SZ')
                age_minutes = int((datetime.utcnow() - pub_time).total_seconds() / 60)
                time_str = f"{age_minutes} min ago" if age_minutes < 60 else f"{age_minutes // 60}h ago"
            except:
                time_str = "Unknown"
            
            # Build embed
            title = f"{emoji} {type_emoji} {event_type} ALERT"
            if spillover_opportunities:
                title += " + SPILLOVER"
            
            embed = {
                'title': title,
                'description': article.get('title', 'No title'),
                'color': color,
                'timestamp': datetime.utcnow().isoformat(),
                'fields': []
            }
            
            # Source and timing
            embed['fields'].append({
                'name': '📰 Source',
                'value': f"{article.get('publisher', {}).get('name', 'Unknown')} • {time_str}",
                'inline': False
            })
            
            # Tickers (for non-spillover)
            if event_type != 'MACRO' and not spillover_opportunities:
                embed['fields'].append({
                    'name': '🎯 Affected Tickers',
                    'value': ', '.join(tickers[:5]),
                    'inline': True
                })
            
            # Impact score
            embed['fields'].append({
                'name': '💥 Impact Score',
                'value': f'{impact_score:.1f}/10',
                'inline': True
            })
            
            # Volume confirmation
            if volume_confirmations:
                vol_text = []
                for ticker, vol_data in volume_confirmations.items():
                    rvol = vol_data.get('rvol', 0)
                    classification_str = vol_data.get('classification', 'N/A')
                    emoji_str = '⚡⚡⚡' if rvol >= 3.0 else '⚡⚡' if rvol >= 2.5 else '⚡'
                    vol_text.append(f"  • {ticker}: RVOL {rvol:.1f}x ({classification_str}) {emoji_str}")
                
                embed['fields'].append({
                    'name': '📊 Volume Confirmation',
                    'value': '\n'.join(vol_text),
                    'inline': False
                })
            
            # Spillover opportunities (IMPORTANT)
            if spillover_opportunities:
                spillover_text = []
                for opp in spillover_opportunities[:5]:  # Top 5
                    symbol = opp['symbol']
                    rvol = opp['rvol']
                    change = opp['change_percent']
                    classification_str = opp['classification']
                    
                    emoji_str = '⚡⚡⚡' if opp['critical'] else '⚡⚡' if rvol >= 2.5 else '⚡'
                    change_str = f"+{change:.1f}%" if change > 0 else f"{change:.1f}%"
                    
                    spillover_text.append(
                        f"  • **{symbol}**: {change_str} | RVOL {rvol:.1f}x ({classification_str}) {emoji_str}"
                    )
                
                embed['fields'].append({
                    'name': f'💥 Related Movers ({len(spillover_opportunities)} detected)',
                    'value': '\n'.join(spillover_text),
                    'inline': False
                })
            
            # Action items
            if event_type == 'MACRO':
                action_text = "✅ Check SPY/QQQ for market direction\n✅ Review watchlist for sector impact\n✅ Adjust position sizing"
            elif spillover_opportunities:
                action_text = f"✅ Check {spillover_opportunities[0]['symbol']} for continuation\n✅ Monitor related stocks for entry\n✅ Watch for momentum shifts"
            elif event_type == 'M&A':
                action_text = "✅ Check if target stock on watchlist\n✅ Review deal terms and timeline\n✅ Consider arbitrage opportunity"
            elif event_type == 'ANALYST':
                action_text = "✅ Review price target change magnitude\n✅ Check volume for validation\n✅ Look for entry on pullback"
            else:
                action_text = "✅ Review news details\n✅ Check Bookmap for confirmation\n✅ Monitor for follow-through"
            
            embed['fields'].append({
                'name': '🎯 Action Items',
                'value': action_text,
                'inline': False
            })
            
            # Article link
            embed['fields'].append({
                'name': '🔗 Read Full Article',
                'value': f"[Click here]({article.get('article_url', '#')})",
                'inline': False
            })
            
            # Footer
            embed['footer'] = {
                'text': f"⚡ Market Impact Monitor • Detected: {time_str}"
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
                f"✅ Market impact alert sent: {event_type} | "
                f"Tickers: {', '.join(tickers[:3])} | "
                f"Impact: {impact_score:.1f}/10"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send Discord alert: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False
    
    def run_single_check(self) -> int:
        """Run a single check cycle"""
        if not self.enabled:
            return 0
        
        self.logger.info("🔍 Checking for market impact news...")
        
        matched_articles = self.check_for_market_impact_news()
        
        if not matched_articles:
            self.logger.info("✅ Check complete - No high-impact news")
            return 0
        
        alerts_sent = 0
        
        for alert_data in matched_articles:
            success = self.send_discord_alert(alert_data)
            if success:
                alerts_sent += 1
        
        return alerts_sent
    
    def run_continuous(self):
        """Run continuous monitoring"""
        self.logger.info("Starting market impact monitor...")
        self.logger.info(f"Check interval: {self.check_interval}s")
        self.logger.info(f"Volume threshold: {self.min_rvol}x")
        self.logger.info(f"Monitoring: {len(self.watchlist)} stocks + macro events")
        
        try:
            while True:
                try:
                    alerts_sent = self.run_single_check()
                    
                    if alerts_sent > 0:
                        self.logger.info(f"📬 Sent {alerts_sent} market impact alerts")
                    
                except Exception as e:
                    self.logger.error(f"Error in check cycle: {str(e)}")
                
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            self.logger.info("Stopping market impact monitor...")
            self.print_stats()
    
    def print_stats(self):
        """Print statistics"""
        print("\n" + "=" * 60)
        print("MARKET IMPACT MONITOR STATISTICS")
        print("=" * 60)
        print(f"Macro Events: {self.stats['macro_events']}")
        print(f"Analyst Events: {self.stats['analyst_events']}")
        print(f"M&A Events: {self.stats['ma_events']}")
        print(f"Earnings Events: {self.stats['earnings_events']}")
        print(f"Spillover Events: {self.stats['spillover_events']}")
        print(f"Volume Confirmed: {self.stats['volume_confirmed']}")
        print(f"Alerts Sent: {self.stats['alerts_sent']}")
        print(f"Filtered (low impact): {self.stats['filtered']}")
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
    webhook = os.getenv('DISCORD_NEWS_ALERTS')
    
    if not api_key:
        print("❌ POLYGON_API_KEY not found")
        sys.exit(1)
    
    # Test config
    config = {
        'market_impact_monitor': {
            'enabled': True,
            'check_interval': 60,
            'lookback_hours': 2,
            'max_alerts_per_hour': 20,
            'min_impact_score': 7.0,
            'volume_confirmation': {
                'enabled': True,
                'min_rvol': 2.0,
                'critical_rvol': 3.0
            }
        }
    }
    
    monitor = MarketImpactMonitor(api_key, config)
    
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
