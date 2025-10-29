"""
Real-Time Earnings Monitor - BENZINGA API VERSION
Pre-market: 5:00 AM - 8:00 AM ET (20 sec checks)
Post-market: 3:50 PM - 7:00 PM ET (5 sec checks) ⚡ ULTRA-FAST
Routes to: DISCORD_REALTIME_EARNINGS
WITH DATABASE PERSISTENCE
WITH FORTUNE 500 MARKET CAP FILTER ($5B+)
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
                 check_interval_postmarket: int = 5):  # 5 SECONDS!
        """
        Initialize Earnings Monitor - Benzinga API version
        
        Args:
            polygon_api_key: Polygon API key (with Benzinga earnings access)
            discord_alerter: DiscordAlerter instance
            check_interval_premarket: Pre-market check interval (default 20s)
            check_interval_postmarket: Post-market check interval (default 5s) ⚡
        """
        self.polygon_api_key = polygon_api_key
        self.discord = discord_alerter
        self.check_interval_premarket = check_interval_premarket
        self.check_interval_postmarket = check_interval_postmarket
        self.logger = logging.getLogger(__name__)
        
        self.running = False
        self.thread = None
        
        # ✨ NEW: MARKET CAP FILTER - Fortune 500 companies
        # Fortune 500: $5B+ | Fortune 100: $50B+ | Top 200: $10B+
        self.MIN_MARKET_CAP = 5_000_000_000  # $5 billion
        
        # Track seen earnings (to prevent duplicates)
        self.seen_earnings = set()  # Set of (symbol, date, benzinga_id) tuples
        
        # Earnings calendar cache
        self.today_earnings = []
        self.calendar_last_updated = None
        
        self.stats = {
            'checks_performed': 0,
            'earnings_detected': 0,
            'alerts_sent': 0,
            'filtered_smallcap': 0,  # ✨ NEW: Track filtered companies
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
        
        self.logger.info(f"📊 Earnings monitor started (Benzinga API)")
        self.logger.info(f"   🌅 Pre-market: 5:00 AM - 8:00 AM ET (check every {self.check_interval_premarket}s)")
        self.logger.info(f"   🌆 Post-market: 3:50 PM - 7:00 PM ET (check every {self.check_interval_postmarket}s) ⚡ ULTRA-FAST")
        self.logger.info(f"   📅 Monitoring {len(self.today_earnings)} stocks with earnings today")
        self.logger.info(f"   💎 Market cap filter: ${self.MIN_MARKET_CAP:,.0f}+ (Fortune 500)")
    
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
    
    def _get_market_cap(self, ticker: str) -> float:
        """
        ✨ NEW: Get market cap for a ticker using Polygon API
        
        Args:
            ticker: Stock ticker symbol
        
        Returns:
            Market cap in dollars (0 if unavailable)
        """
        try:
            url = f"https://api.polygon.io/v3/reference/tickers/{ticker}"
            params = {'apiKey': self.polygon_api_key}
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            market_cap = data.get('results', {}).get('market_cap', 0)
            
            return market_cap if market_cap else 0
            
        except Exception as e:
            self.logger.debug(f"Could not fetch market cap for {ticker}: {str(e)}")
            return 0  # Default to 0 if unavailable (will be filtered out)
    
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
                
                # ✨ NEW: MARKET CAP FILTER - Skip small cap companies
                market_cap = self._get_market_cap(ticker)
                if market_cap < self.MIN_MARKET_CAP:
                    self.stats['filtered_smallcap'] += 1
                    self.logger.info(
                        f"⏭️  Skipping {ticker} - Market cap ${market_cap:,.0f} "
                        f"below ${self.MIN_MARKET_CAP:,.0f} threshold"
                    )
                    continue
                
                # Analyze beat/miss
                sentiment = self._analyze_earnings_sentiment(earning)
                
                # Track stats
                if sentiment == 'BEAT':
                    self.stats['beats'] += 1
                elif sentiment == 'MISS':
                    self.stats['misses'] += 1
                else:
                    self.stats['inline'] += 1
                
                self.logger.warning(
                    f"🚨 EARNINGS DETECTED: {ticker} (${market_cap/1e9:.1f}B) - {sentiment} | "
                    f"EPS: {earning.get('actual_eps')} vs {earning.get('estimated_eps')}"
                )
                
                # Send alert
                self._send_earnings_alert(earning, sentiment)
        
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
            # Use existing Discord alerter method (we'll update this)
            success = self._send_to_discord(alert_data)
            
            if success:
                self.stats['alerts_sent'] += 1
                self.logger.info(f"✅ Earnings alert sent: {ticker} - {sentiment}")
                
                # Save to database if callback exists
                if hasattr(self, 'save_to_db_callback') and self.save_to_db_callback:
                    try:
                        headline = f"{ticker} {sentiment} - {fiscal_period} {fiscal_year} Earnings"
                        self.save_to_db_callback(
                            ticker=ticker,
                            headline=headline,
                            article=earning,
                            channel='earnings'
                        )
                    except Exception as e:
                        self.logger.error(f"Error saving to database: {str(e)}")
        
        except Exception as e:
            self.logger.error(f"Error sending earnings alert: {str(e)}")
    
    def _send_to_discord(self, alert_data: Dict) -> bool:
        """Send formatted earnings alert to Discord webhook"""
        webhook_url = self.discord.config.get('webhook_earnings_realtime')
        
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
                'text': f"Detected at {alert_data['time']} ET • Earnings Monitor v2"
            },
            'timestamp': alert_data['timestamp']
        }
        
        payload = {'embeds': [embed]}
        
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.error(f"Discord webhook error: {str(e)}")
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
            'description': f'**{len(earnings_list)} companies reporting earnings**',
            'color': 0x5865F2,  # Discord blurple
            'fields': [
                {
                    'name': f'🔥 Major Earnings ({len(major)} companies)',
                    'value': '\n\n'.join(major_lines[:10]) if major_lines else 'None',
                    'inline': False
                }
            ],
            'footer': {
                'text': f'Daily Preview • Monitor active 3:50-7 PM ET'
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
        return self.stats.copy()


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
        check_interval_postmarket=5
    )
    
    # Test daily preview
    print("Testing daily preview for tomorrow...")
    preview = monitor.get_daily_preview()
    
    print(f"\n✅ Found {len(preview)} earnings scheduled for tomorrow:")
    for e in preview[:10]:
        print(f"  • {e['ticker']} - {e.get('company_name')} at {e.get('time')}")