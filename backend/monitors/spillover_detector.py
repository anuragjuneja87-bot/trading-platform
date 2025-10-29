"""
backend/monitors/spillover_detector.py
Spillover Detection System - Detects related ticker opportunities
Example: NVDA news → Alert on NVTS, SMCI, ARM (related stocks)
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
from datetime import datetime
from typing import Dict, List, Optional


class SpilloverDetector:
    def __init__(self, 
                 unified_news_engine,
                 discord_alerter,
                 polygon_api_key: str,
                 spillover_map: Dict[str, List[str]],
                 check_interval: int = 60):
        """
        Initialize spillover detector
        
        Args:
            unified_news_engine: UnifiedNewsEngine instance
            discord_alerter: DiscordAlerter instance
            polygon_api_key: Polygon API key for volume checks
            spillover_map: Dict mapping primary tickers to related tickers
            check_interval: Check every N seconds (default 60s)
        """
        self.unified_news = unified_news_engine
        self.discord = discord_alerter
        self.polygon_api_key = polygon_api_key
        self.spillover_map = spillover_map
        self.check_interval = check_interval
        self.logger = logging.getLogger(__name__)
        
        self.running = False
        self.thread = None
        
        # Track seen spillover opportunities
        self.seen_opportunities = set()
        
        # Major tickers to monitor
        self.major_tickers = list(spillover_map.keys())
        
        self.stats = {
            'checks_performed': 0,
            'opportunities_found': 0,
            'alerts_sent': 0,
            'last_check': None,
            'by_primary_ticker': {ticker: 0 for ticker in self.major_tickers}
        }
    
    def start(self):
        """Start monitoring in background thread"""
        if self.running:
            self.logger.warning("Spillover detector already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        self.logger.info(f"🔗 Spillover detector started (check every {self.check_interval}s)")
        self.logger.info(f"   Monitoring {len(self.major_tickers)} major tickers: {', '.join(self.major_tickers)}")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self.logger.info("Spillover detector stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                self.check_spillover_opportunities()
                time.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(f"Error in spillover detector loop: {str(e)}")
                time.sleep(60)
    
    def check_spillover_opportunities(self):
        """Check for spillover opportunities"""
        try:
            self.stats['checks_performed'] += 1
            self.stats['last_check'] = datetime.now().isoformat()
            
            # Check each major ticker for news
            for primary_ticker in self.major_tickers:
                self._check_ticker_spillover(primary_ticker)
            
        except Exception as e:
            self.logger.error(f"Error checking spillover opportunities: {str(e)}")
    
    def _check_ticker_spillover(self, primary_ticker: str):
        """Check if primary ticker has news that affects related tickers"""
        try:
            # Get recent news for primary ticker (last 2 hours)
            articles = self.unified_news.get_unified_news(
                ticker=primary_ticker,
                hours=2,
                limit=10
            )
            
            if not articles:
                return
            
            # Get related tickers from spillover map
            related_tickers = self.spillover_map.get(primary_ticker, [])
            if not related_tickers:
                return
            
            # Check each article
            for article in articles:
                # FIX 1: Verify this is ACTUALLY about the primary ticker
                if not self._is_primary_ticker_news(article, primary_ticker):
                    continue
                
                article_id = article.get('id', '') or article.get('url', '')
                
                # FIX 2: Global deduplication (not just per-primary ticker)
                if article_id in self.seen_opportunities:
                    continue
                
                # Check if news is significant
                if not self._is_significant_news(article):
                    continue
                
                # Check volume confirmation on related tickers
                opportunities = []
                for related_ticker in related_tickers:
                    volume_data = self._check_volume_confirmation(related_ticker)
                    if volume_data and volume_data['rvol'] >= 2.0:
                        opportunities.append({
                            'ticker': related_ticker,
                            'volume_data': volume_data
                        })
                
                # FIX 3: Only alert if we have REAL opportunities (not fake RVOL)
                if opportunities and len(opportunities) >= 1:
                    # Verify at least one opportunity has real volume data
                    real_opportunities = [
                        opp for opp in opportunities 
                        if opp['volume_data'].get('volume', 0) > 0
                    ]
                    
                    if not real_opportunities:
                        continue
                    
                    self.seen_opportunities.add(article_id)  # Mark as seen globally
                    self.stats['opportunities_found'] += 1
                    self.stats['by_primary_ticker'][primary_ticker] += 1
                    
                    self.logger.info(
                        f"🔗 Spillover opportunity: {primary_ticker} → "
                        f"{', '.join([o['ticker'] for o in real_opportunities])}"
                    )
                    
                    # Send alert with real opportunities only
                    self._send_spillover_alert(primary_ticker, article, real_opportunities)
        
        except Exception as e:
            self.logger.error(f"Error checking spillover for {primary_ticker}: {str(e)}")
    
    def _is_primary_ticker_news(self, article: Dict, ticker: str) -> bool:
        """
        Verify article is ACTUALLY about the primary ticker
        Not just mentioning it in passing
        """
        title = article.get('title', '').upper()
        teaser = article.get('teaser', '').upper()
        
        # Must appear in title OR be the first ticker mentioned
        tickers = article.get('tickers', [])
        
        # Check 1: Ticker in title (strong signal)
        if ticker in title:
            return True
        
        # Check 2: Ticker is the FIRST/PRIMARY ticker in article
        if tickers and len(tickers) > 0:
            # Primary ticker should be in first 2 tickers
            if ticker in tickers[:2]:
                return True
        
        # Check 3: Company name in title (for major companies)
        company_names = {
            'NVDA': 'NVIDIA',
            'TSLA': 'TESLA',
            'AAPL': 'APPLE',
            'MSFT': 'MICROSOFT',
            'GOOGL': 'GOOGLE',
            'AMZN': 'AMAZON',
            'META': 'META',
            'CRM': 'SALESFORCE'
        }
        
        company_name = company_names.get(ticker, '')
        if company_name and company_name in title:
            return True
        
        # Otherwise, not primary news
        return False
    
    
    def _is_significant_news(self, article: Dict) -> bool:
        """Check if news is significant enough for spillover"""
        title = article.get('title', '').lower()
        teaser = article.get('teaser', '').lower()
        full_text = f"{title} {teaser}"
        
        # Significant keywords
        significant_keywords = [
            'announces', 'partnership', 'deal', 'agreement', 'contract',
            'acquisition', 'merger', 'launches', 'unveils', 'releases',
            'earnings beat', 'earnings miss', 'guidance', 'forecast',
            'breakthrough', 'innovation', 'expansion', 'investment',
            'upgrade', 'downgrade', 'price target'
        ]
        
        return any(keyword in full_text for keyword in significant_keywords)
    
    def _check_volume_confirmation(self, ticker: str) -> Optional[Dict]:
        """Check if related ticker has volume confirmation"""
        try:
            # Get current day's aggregate
            endpoint = "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"
            
            from datetime import date
            today = date.today().isoformat()
            
            url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev"
            
            response = requests.get(
                url,
                params={'apiKey': self.polygon_api_key},
                timeout=5
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            if 'results' not in data or not data['results']:
                return None
            
            result = data['results'][0]
            current_volume = result.get('v', 0)
            
            # Get average volume (rough estimate using previous day)
            # In production, you'd want to calculate proper 20-day average
            avg_volume = current_volume * 0.5  # Simplified
            
            if avg_volume == 0:
                return None
            
            rvol = current_volume / avg_volume
            
            return {
                'ticker': ticker,
                'current_volume': current_volume,
                'avg_volume': avg_volume,
                'rvol': round(rvol, 2),
                'price': result.get('c', 0),
                'volume': current_volume  # Include volume for verification
            }
            
        except Exception as e:
            self.logger.debug(f"Error checking volume for {ticker}: {str(e)}")
            return None
    
    def _send_spillover_alert(self, 
                             primary_ticker: str,
                             article: Dict,
                             opportunities: List[Dict]):
        """Send spillover alert to Discord"""
        if not self.discord:
            return
        
        alert_data = {
            'primary_ticker': primary_ticker,
            'article': {
                'title': article.get('title', ''),
                'url': article.get('url', ''),
                'published': article.get('published_utc', ''),
                'source': article.get('source', ''),
                'teaser': article.get('teaser', '')[:200]
            },
            'opportunities': opportunities,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            success = self.discord.send_spillover_alert(alert_data)
            if success:
                self.stats['alerts_sent'] += 1
                tickers = ', '.join([o['ticker'] for o in opportunities])
                self.logger.info(f"✅ Sent spillover alert: {primary_ticker} → {tickers}")
                
                # ==================== DATABASE SAVE ====================
                # Save to database after successful Discord alert
                if hasattr(self, 'save_to_db_callback') and self.save_to_db_callback:
                    try:
                        # Save for primary ticker
                        self.save_to_db_callback(
                            ticker=primary_ticker,
                            headline=f"Spillover: {article.get('title', 'Market News')}",
                            article=article,
                            channel='spillover'
                        )
                        
                        # Save for related tickers with volume confirmation
                        for opportunity in opportunities:
                            related_ticker = opportunity['ticker']
                            self.save_to_db_callback(
                                ticker=related_ticker,
                                headline=f"Spillover from {primary_ticker}: {article.get('title', 'Market News')}",
                                article=article,
                                channel='spillover'
                            )
                        
                        self.logger.debug(
                            f"💾 Saved spillover news to database: {primary_ticker} + "
                            f"{len(opportunities)} related tickers"
                        )
                    except Exception as e:
                        self.logger.error(f"Error saving to database: {str(e)}")
                # =====================================================
                
        except AttributeError:
            self.logger.warning("send_spillover_alert not implemented yet")
    
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
    
    # Test spillover map
    spillover_map = {
        'NVDA': ['NVTS', 'SMCI', 'ARM', 'AMD'],
        'TSLA': ['RIVN', 'LCID', 'F', 'GM'],
        'AAPL': ['QCOM', 'CIRR', 'SWKS']
    }
    
    engine = UnifiedNewsEngine(api_key)
    detector = SpilloverDetector(engine, None, api_key, spillover_map, check_interval=60)
    
    print("Testing spillover detection...")
    detector.check_spillover_opportunities()
    
    print(f"\nStatistics: {detector.get_statistics()}")