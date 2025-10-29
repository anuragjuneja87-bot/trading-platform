"""
Real-Time Earnings Monitor - BENZINGA API VERSION v2.1
Pre-market: 5:00 AM - 8:00 AM ET (20 sec checks)
Post-market: 3:50 PM - 7:00 PM ET (5 sec checks) ⚡ ULTRA-FAST
Routes to: DISCORD_REALTIME_EARNINGS
WITH DATABASE PERSISTENCE
WITH RATE LIMIT PROTECTION
WITH FORTUNE 500 MARKET CAP FILTER ($5B+)
EXPERIMENTAL VERSION - TEST BEFORE PRODUCTION
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
                 discord_alerter,
                 check_interval_premarket: int = 20,
                 check_interval_postmarket: int = 5,
                 min_market_cap: int = 5_000_000_000,  # $5B default
                 allow_unknown_market_cap: bool = True):  # Allow if market cap unavailable
        """
        Initialize Earnings Monitor - Benzinga API version with Market Cap Filter
        
        Args:
            polygon_api_key: Polygon API key (with Benzinga earnings access)
            discord_alerter: DiscordAlerter instance
            check_interval_premarket: Pre-market check interval (default 20s)
            check_interval_postmarket: Post-market check interval (default 5s) ⚡
            min_market_cap: Minimum market cap for alerts (default $5B for Fortune 500)
            allow_unknown_market_cap: If True, send alerts even if market cap unavailable
        """
        self.polygon_api_key = polygon_api_key
        self.discord = discord_alerter
        self.check_interval_premarket = check_interval_premarket
        self.check_interval_postmarket = check_interval_postmarket
        self.logger = logging.getLogger(__name__)
        
        # MARKET CAP FILTER CONFIGURATION
        self.MIN_MARKET_CAP = min_market_cap
        self.ALLOW_UNKNOWN_MARKET_CAP = allow_unknown_market_cap
        
        self.running = False
        self.thread = None
        
        # Track seen earnings (to prevent duplicates)
        self.seen_earnings = set()  # Set of (symbol, date, benzinga_id) tuples
        
        # Earnings calendar cache
        self.today_earnings = []
        self.calendar_last_updated = None
        
        self.stats = {
            'checks_performed': 0,
            'earnings_detected': 0,
            'alerts_sent': 0,
            'filtered_smallcap': 0,  # NEW: Track filtered companies
            'market_cap_unknown': 0,  # NEW: Track unknown market caps
            'last_check': None,
            'calendar_symbols': 0,
            'calendar_last_updated': None,
            'current_session': None,
            'beats': 0,
            'misses': 0,
            'inline': 0
        }
    
    def start(self):
        """Start monitoring in background thread"""
        if self.running:
            self.logger.warning("Earnings monitor already running")
            return
        
        self.running = True
        
        # Load today's earnings calendar
        self._refresh_earnings_calendar()
        
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        
        self.logger.info(f"📊 Earnings monitor started (Benzinga API v2.1)")
        self.logger.info(f"   🌅 Pre-market: 5:00 AM - 8:00 AM ET (check every {self.check_interval_premarket}s)")
        self.logger.info(f"   🌆 Post-market: 3:50 PM - 7:00 PM ET (check every {self.check_interval_postmarket}s) ⚡ ULTRA-FAST")
        self.logger.info(f"   📅 Monitoring {len(self.today_earnings)} stocks with earnings today")
        self.logger.info(f"   💎 Market cap filter: ${self.MIN_MARKET_CAP:,.0f}+ (Fortune 500)")
        if self.ALLOW_UNKNOWN_MARKET_CAP:
            self.logger.info(f"   ⚠️  Unknown market caps: ALLOWED (will send alerts)")
        else:
            self.logger.info(f"   🚫 Unknown market caps: BLOCKED (will skip alerts)")
    
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
                session = self._get_current_session()
                
                if session == 'PREMARKET':
                    self.stats['current_session'] = 'PREMARKET'
                    self.check_earnings()
                    time.sleep(self.check_interval_premarket)
                    
                elif session == 'POSTMARKET':
                    self.stats['current_session'] = 'POSTMARKET'
                    self.check_earnings()
                    time.sleep(self.check_interval_postmarket)  # 5 SECONDS!
                    
                else:
                    self.stats['current_session'] = 'IDLE'
                    time.sleep(60)
                    
                    # Refresh calendar at market close
                    if session == 'MARKET_CLOSE':
                        self._refresh_earnings_calendar()
                
            except Exception as e:
                self.logger.error(f"Error in earnings monitor loop: {str(e)}")
                time.sleep(30)
    
    def _get_current_session(self) -> str:
        """Determine current session"""
        et_tz = pytz.timezone('America/New_York')
        now_et = datetime.now(et_tz)
        current_time = now_et.time()
        
        premarket_start = dt_time(5, 0)
        premarket_end = dt_time(8, 0)
        postmarket_start = dt_time(15, 50)  # 3:50 PM
        postmarket_end = dt_time(19, 0)     # 7:00 PM
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
        """Fetch today's earnings calendar from Polygon/Benzinga"""
        try:
            self.logger.info("📅 Refreshing earnings calendar...")
            
            today = datetime.now().date().isoformat()
            
            url = "https://api.polygon.io/benzinga/v1/earnings"
            params = {
                'apiKey': self.polygon_api_key,
                'date.gte': today,
                'date.lte': today,
                'limit': 250
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'results' in data and data['results']:
                self.today_earnings = data['results']
                self.calendar_last_updated = datetime.now().isoformat()
                self.stats['calendar_symbols'] = len(self.today_earnings)
                self.stats['calendar_last_updated'] = self.calendar_last_updated
                
                self.logger.info(f"✅ Earnings calendar updated: {len(self.today_earnings)} stocks reporting today")
                
                # Log major earnings
                major_tickers = [e for e in self.today_earnings if e.get('importance', 0) >= 4]
                if major_tickers:
                    tickers = ', '.join([e['ticker'] for e in major_tickers[:10]])
                    self.logger.info(f"   📊 Major earnings today: {tickers}")
            else:
                self.logger.info("ℹ️  No earnings scheduled for today")
                self.today_earnings = []
            
        except Exception as e:
            self.logger.error(f"Error refreshing earnings calendar: {str(e)}")
            self.today_earnings = []
    
    def _get_market_cap(self, ticker: str) -> Optional[float]:
        """
        Get market cap for a ticker using Polygon API
        
        Args:
            ticker: Stock ticker symbol
        
        Returns:
            Market cap in dollars, or None if unavailable
        """
        try:
            url = f"https://api.polygon.io/v3/reference/tickers/{ticker}"
            params = {'apiKey': self.polygon_api_key}
            
            response = requests.get(url, params=params, timeout=5)
            
            # Handle specific HTTP errors
            if response.status_code == 404:
                self.logger.info(f"⚠️  {ticker}: Ticker not found in Polygon database")
                return None
            elif response.status_code == 429:
                self.logger.warning(f"⚠️  {ticker}: Rate limited on market cap API")
                return None
            
            response.raise_for_status()
            
            data = response.json()
            market_cap = data.get('results', {}).get('market_cap', 0)
            
            if market_cap and market_cap > 0:
                # Log market cap in billions for readability
                self.logger.info(f"💰 {ticker}: ${market_cap/1e9:.2f}B market cap")
                return market_cap
            else:
                self.logger.info(f"⚠️  {ticker}: No market cap data available")
                return None
            
        except requests.exceptions.Timeout:
            self.logger.warning(f"⚠️  {ticker}: Timeout fetching market cap")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"⚠️  {ticker}: Error fetching market cap - {str(e)}")
            return None
        except Exception as e:
            self.logger.warning(f"⚠️  {ticker}: Unexpected error - {str(e)}")
            return None
    
    def check_earnings(self):
        """Check for earnings that have been released (actual_eps populated)"""
        try:
            self.stats['checks_performed'] += 1
            self.stats['last_check'] = datetime.now().isoformat()
            
            today = datetime.now().date().isoformat()
            
            # Query for TODAY's earnings with actual results
            url = "https://api.polygon.io/benzinga/v1/earnings"
            params = {
                'apiKey': self.polygon_api_key,
                'date.gte': today,
                'date.lte': today,
                'limit': 250
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'results' not in data or not data['results']:
                return
            
            # Filter for earnings that have been RELEASED (have actual_eps)
            released_earnings = [
                e for e in data['results'] 
                if e.get('actual_eps') is not None
            ]
            
            for earning in released_earnings:
                benzinga_id = earning.get('benzinga_id')
                ticker = earning.get('ticker')
                date = earning.get('date')
                
                # Skip if already seen
                key = (ticker, date, benzinga_id)
                if key in self.seen_earnings:
                    continue
                
                # Mark as seen
                self.seen_earnings.add(key)
                self.stats['earnings_detected'] += 1
                
                # 🔍 MARKET CAP FILTER - Check if company meets threshold
                market_cap = self._get_market_cap(ticker)
                
                if market_cap is None:
                    # Market cap unavailable
                    self.stats['market_cap_unknown'] += 1
                    
                    if not self.ALLOW_UNKNOWN_MARKET_CAP:
                        self.logger.info(
                            f"⏭️  Skipping {ticker} - Market cap unknown and filtering enabled"
                        )
                        continue
                    else:
                        self.logger.info(
                            f"✅ Allowing {ticker} - Market cap unknown but filter is permissive"
                        )
                
                elif market_cap < self.MIN_MARKET_CAP:
                    # Market cap below threshold
                    self.stats['filtered_smallcap'] += 1
                    self.logger.info(
                        f"⏭️  Skipping {ticker} - Market cap ${market_cap:,.0f} "
                        f"below ${self.MIN_MARKET_CAP:,.0f} threshold"
                    )
                    continue
                
                # Passed filter - proceed with alert
                sentiment = self._analyze_earnings_sentiment(earning)
                
                # Track stats
                if sentiment == 'BEAT':
                    self.stats['beats'] += 1
                elif sentiment == 'MISS':
                    self.stats['misses'] += 1
                else:
                    self.stats['inline'] += 1
                
                market_cap_str = f"(${market_cap/1e9:.1f}B)" if market_cap else "(Unknown cap)"
                self.logger.warning(
                    f"🚨 EARNINGS DETECTED: {ticker} {market_cap_str} - {sentiment} | "
                    f"EPS: {earning.get('actual_eps')} vs {earning.get('estimated_eps')}"
                )
                
                # Send alert
                self._send_earnings_alert(earning, sentiment)
                
                # Add delay to avoid Discord rate limits (max 5 per 2 seconds)
                time.sleep(0.5)
        
        except Exception as e:
            self.logger.error(f"Error checking earnings: {str(e)}")
    
    def _analyze_earnings_sentiment(self, earning: Dict) -> str:
        """
        Analyze if earnings beat, missed, or inline
        
        Returns: 'BEAT', 'MISS', or 'INLINE'
        """
        actual_eps = earning.get('actual_eps')
        estimated_eps = earning.get('estimated_eps')
        eps_surprise_pct = earning.get('eps_surprise_percent', 0)
        
        if actual_eps is None or estimated_eps is None:
            return 'INLINE'
        
        # Use surprise percentage if available
        if eps_surprise_pct:
            if eps_surprise_pct > 0.02:  # >2% beat
                return 'BEAT'
            elif eps_surprise_pct < -0.02:  # >2% miss
                return 'MISS'
            else:
                return 'INLINE'
        
        # Fallback: compare actual vs estimate
        surprise = actual_eps - estimated_eps
        surprise_pct = (surprise / abs(estimated_eps)) * 100 if estimated_eps != 0 else 0
        
        if surprise_pct > 2:
            return 'BEAT'
        elif surprise_pct < -2:
            return 'MISS'
        else:
            return 'INLINE'
    
    def _send_earnings_alert(self, earning: Dict, sentiment: str):
        """Send earnings alert to Discord"""
        if not self.discord:
            return
        
        ticker = earning.get('ticker', 'UNKNOWN')
        company = earning.get('company_name', ticker)
        
        # EPS data
        actual_eps = earning.get('actual_eps')
        estimated_eps = earning.get('estimated_eps')
        eps_surprise = earning.get('eps_surprise', 0)
        eps_surprise_pct = earning.get('eps_surprise_percent', 0)
        
        # Revenue data
        actual_revenue = earning.get('actual_revenue')
        estimated_revenue = earning.get('estimated_revenue')
        revenue_surprise_pct = earning.get('revenue_surprise_percent', 0)
        
        # Fiscal period
        fiscal_period = earning.get('fiscal_period', 'N/A')
        fiscal_year = earning.get('fiscal_year', 'N/A')
        
        # Time
        date = earning.get('date')
        time = earning.get('time')
        
        alert_data = {
            'ticker': ticker,
            'company': company,
            'sentiment': sentiment,
            'fiscal_period': f"{fiscal_period} {fiscal_year}",
            'date': date,
            'time': time,
            'eps': {
                'actual': actual_eps,
                'estimate': estimated_eps,
                'surprise': eps_surprise,
                'surprise_pct': eps_surprise_pct * 100 if eps_surprise_pct else 0
            },
            'revenue': {
                'actual': actual_revenue,
                'estimate': estimated_revenue,
                'surprise_pct': revenue_surprise_pct * 100 if revenue_surprise_pct else 0
            },
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # Use existing Discord alerter method
            success = self._send_to_discord(alert_data)
            
            if success:
                self.stats['alerts_sent'] += 1
                self.logger.info(f"✅ Earnings alert sent: {ticker} - {sentiment}")
                
                # Save to database if callback exists and is callable
                if hasattr(self, 'save_to_db_callback') and callable(self.save_to_db_callback):
                    try:
                        headline = f"{ticker} {sentiment} - {fiscal_period} {fiscal_year} Earnings"
                        self.save_to_db_callback(
                            ticker=ticker,
                            headline=headline,
                            article=earning,
                            channel='earnings'
                        )
                    except Exception as e:
                        self.logger.debug(f"Database save skipped: {str(e)}")
        
        except Exception as e:
            self.logger.error(f"Error sending earnings alert: {str(e)}")
    
    def _send_to_discord(self, alert_data: Dict) -> bool:
        """Send formatted earnings alert to Discord webhook"""
        # Try different ways to access the webhook based on DiscordAlerter structure
        webhook_url = None
        
        if hasattr(self.discord, 'webhooks'):
            # Method 1: webhooks dictionary
            webhook_url = self.discord.webhooks.get('earnings_realtime')
        elif hasattr(self.discord, 'config'):
            # Method 2: config dictionary
            webhook_url = self.discord.config.get('webhook_earnings_realtime')
        elif hasattr(self.discord, 'webhook_earnings_realtime'):
            # Method 3: direct attribute
            webhook_url = self.discord.webhook_earnings_realtime
        
        if not webhook_url:
            self.logger.warning("Discord webhook for earnings not configured")
            return False
        
        ticker = alert_data['ticker']
        sentiment = alert_data['sentiment']
        eps = alert_data['eps']
        revenue = alert_data['revenue']
        
        # Emoji and color based on sentiment
        if sentiment == 'BEAT':
            emoji = '🚀'
            color = 0x00ff00  # Green
        elif sentiment == 'MISS':
            emoji = '📉'
            color = 0xff0000  # Red
        else:
            emoji = '➡️'
            color = 0xffff00  # Yellow
        
        # Format EPS
        eps_str = f"**Actual:** ${eps['actual']:.2f}\n" if eps['actual'] else ""
        eps_str += f"**Estimate:** ${eps['estimate']:.2f}\n" if eps['estimate'] else ""
        eps_str += f"**Surprise:** {eps['surprise_pct']:+.1f}%" if eps['surprise_pct'] else ""
        
        # Format Revenue
        rev_str = ""
        if revenue['actual']:
            rev_str += f"**Actual:** ${revenue['actual']/1e9:.2f}B\n"
        if revenue['estimate']:
            rev_str += f"**Estimate:** ${revenue['estimate']/1e9:.2f}B\n"
        if revenue['surprise_pct']:
            rev_str += f"**Surprise:** {revenue['surprise_pct']:+.1f}%"
        
        # Trading action
        if sentiment == 'BEAT':
            action = (
                "✅ **Potential Long Setup**\n"
                "• Watch for gap up continuation\n"
                "• Monitor volume on breakout\n"
                "• Set alerts near resistance"
            )
        elif sentiment == 'MISS':
            action = (
                "⚠️ **Potential Short Setup**\n"
                "• Watch for gap down continuation\n"
                "• Monitor panic selling\n"
                "• Set alerts near support"
            )
        else:
            action = (
                "ℹ️ **Inline Results**\n"
                "• Watch price action for direction\n"
                "• May consolidate near current levels"
            )
        
        embed = {
            'title': f"{emoji} EARNINGS ALERT: {ticker}",
            'description': f"**{alert_data['company']}** - {sentiment}",
            'color': color,
            'fields': [
                {
                    'name': '📊 EPS (Earnings Per Share)',
                    'value': eps_str or 'N/A',
                    'inline': True
                },
                {
                    'name': '💰 Revenue',
                    'value': rev_str or 'N/A',
                    'inline': True
                },
                {
                    'name': '📅 Period',
                    'value': alert_data['fiscal_period'],
                    'inline': False
                },
                {
                    'name': '🎯 Trading Action',
                    'value': action,
                    'inline': False
                }
            ],
            'footer': {
                'text': f"Detected at {alert_data['time']} ET • Earnings Monitor v2.1"
            },
            'timestamp': alert_data['timestamp']
        }
        
        payload = {'embeds': [embed]}
        
        # Retry logic for rate limits
        max_retries = 3
        retry_delay = 2  # Start with 2 seconds
        
        for attempt in range(max_retries):
            try:
                response = requests.post(webhook_url, json=payload, timeout=10)
                response.raise_for_status()
                return True
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limited
                    if attempt < max_retries - 1:
                        self.logger.warning(f"Discord rate limited, retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        self.logger.error(f"Discord rate limit exceeded after {max_retries} attempts")
                        return False
                else:
                    self.logger.error(f"Discord webhook error: {e}")
                    return False
            except Exception as e:
                self.logger.error(f"Discord webhook error: {str(e)}")
                return False
        
        return False
    
    def get_daily_preview(self, date: str = None) -> List[Dict]:
        """
        Get earnings preview for specified date
        
        Args:
            date: Date in YYYY-MM-DD format (default: tomorrow)
        
        Returns:
            List of earnings scheduled for that date
        """
        if not date:
            tomorrow = (datetime.now() + timedelta(days=1)).date()
            date = tomorrow.isoformat()
        
        try:
            url = "https://api.polygon.io/benzinga/v1/earnings"
            params = {
                'apiKey': self.polygon_api_key,
                'date.gte': date,
                'date.lte': date,
                'limit': 250
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'results' in data and data['results']:
                # Filter for confirmed earnings
                confirmed = [
                    e for e in data['results']
                    if e.get('date_status') == 'confirmed'
                ]
                
                # Sort by importance
                confirmed.sort(key=lambda x: x.get('importance', 0), reverse=True)
                
                return confirmed
            
            return []
        
        except Exception as e:
            self.logger.error(f"Error getting daily preview: {str(e)}")
            return []
    
    def send_daily_preview(self, date: str = None):
        """Send daily earnings preview to Discord (called at 6 PM)"""
        if not date:
            tomorrow = (datetime.now() + timedelta(days=1)).date()
            date = tomorrow.isoformat()
        
        earnings_list = self.get_daily_preview(date)
        
        if not earnings_list:
            self.logger.info(f"No earnings scheduled for {date}")
            return
        
        self.logger.info(f"📅 Sending daily preview: {len(earnings_list)} earnings for {date}")
        
        # Group by importance
        major = [e for e in earnings_list if e.get('importance', 0) >= 4]
        others = [e for e in earnings_list if e.get('importance', 0) < 4]
        
        # Build Discord message
        webhook_url = None
        if hasattr(self.discord, 'webhooks'):
            webhook_url = self.discord.webhooks.get('earnings_realtime')
        elif hasattr(self.discord, 'config'):
            webhook_url = self.discord.config.get('webhook_earnings_realtime')
        
        if not webhook_url:
            self.logger.warning("Discord webhook not configured")
            return
        
        # Format major earnings
        major_lines = []
        for e in major[:15]:  # Top 15
            ticker = e.get('ticker')
            company = e.get('company_name', ticker)
            time = e.get('time', 'N/A')[:5]  # HH:MM
            eps_est = e.get('estimated_eps', 0)
            rev_est = e.get('estimated_revenue', 0) / 1e9 if e.get('estimated_revenue') else 0
            
            major_lines.append(
                f"**{ticker}** - {company}\n"
                f"  ⏰ {time} ET | EPS Est: ${eps_est:.2f} | Rev Est: ${rev_est:.2f}B"
            )
        
        embed = {
            'title': f'📅 EARNINGS PREVIEW - {date}',
            'description': f'**{len(earnings_list)} companies reporting earnings**\n💎 *Filtered: Fortune 500 only ($5B+ market cap)*',
            'color': 0x5865F2,  # Discord blurple
            'fields': [
                {
                    'name': f'🔥 Major Earnings ({len(major)} companies)',
                    'value': '\n\n'.join(major_lines[:10]) if major_lines else 'None',
                    'inline': False
                }
            ],
            'footer': {
                'text': f'Daily Preview • Monitor active 3:50-7 PM ET • v2.1'
            },
            'timestamp': datetime.now().isoformat()
        }
        
        if len(major) > 10:
            embed['fields'].append({
                'name': '📊 More Major Earnings',
                'value': '\n\n'.join(major_lines[10:15]),
                'inline': False
            })
        
        if others:
            embed['fields'].append({
                'name': f'ℹ️ Other Earnings ({len(others)} companies)',
                'value': f'{", ".join([e["ticker"] for e in others[:20]])}...',
                'inline': False
            })
        
        payload = {'embeds': [embed]}
        
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            self.logger.info(f"✅ Daily preview sent: {len(earnings_list)} earnings for {date}")
        except Exception as e:
            self.logger.error(f"Error sending daily preview: {str(e)}")
    
    def get_statistics(self) -> Dict:
        """Get monitor statistics"""
        stats = self.stats.copy()
        stats['market_cap_filter'] = {
            'threshold': self.MIN_MARKET_CAP,
            'allow_unknown': self.ALLOW_UNKNOWN_MARKET_CAP,
            'filtered_count': self.stats['filtered_smallcap'],
            'unknown_count': self.stats['market_cap_unknown']
        }
        return stats


if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    API_KEY = os.getenv('POLYGON_API_KEY')
    
    # Test monitor
    monitor = EarningsMonitor(
        polygon_api_key=API_KEY,
        discord_alerter=None,
        check_interval_premarket=20,
        check_interval_postmarket=5,
        min_market_cap=5_000_000_000,  # $5B
        allow_unknown_market_cap=True  # Allow if market cap unavailable
    )
    
    # Test daily preview
    print("Testing daily preview for tomorrow...")
    preview = monitor.get_daily_preview()
    
    print(f"\n✅ Found {len(preview)} earnings scheduled for tomorrow:")
    for e in preview[:10]:
        print(f"  • {e['ticker']} - {e.get('company_name')} at {e.get('time')}")