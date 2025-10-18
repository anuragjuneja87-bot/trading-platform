"""
backend/alerts/discord_alerter.py
Enhanced Discord Alerter - WITH VOLUME SPIKE ALERTS + 0DTE SUPPORT
Adds new method: send_volume_spike_alert()
Uses DISCORD_VOLUME_SPIKE webhook
Supports DISCORD_ODTE_LEVELS webhook
"""

import requests
from datetime import datetime
from typing import Dict, Optional
import logging
import os


class DiscordAlerter:
    def __init__(self, webhook_url: str = None, config: dict = None):
        """Initialize Discord Alerter"""
        self.logger = logging.getLogger(__name__)
        
        self.webhooks = {}
        
        if config:
            self.webhooks = {
                'trading': self._expand_env_var(config.get('webhook_trading')),
                'news': self._expand_env_var(config.get('webhook_news')),
                'earnings_weekly': self._expand_env_var(config.get('webhook_earnings_weekly')),
                'earnings_realtime': self._expand_env_var(config.get('webhook_earnings_realtime')),
                'market_impact': self._expand_env_var(config.get('webhook_market_impact')),
                'volume_spike': self._expand_env_var(config.get('webhook_volume_spike')),
                'odte_levels': self._expand_env_var(config.get('webhook_odte_levels'))
            }
            
            if webhook_url:
                for channel in ['trading', 'news', 'earnings_weekly', 'earnings_realtime', 
                               'market_impact', 'volume_spike', 'odte_levels']:
                    if not self.webhooks.get(channel):
                        self.webhooks[channel] = webhook_url
            
            if not webhook_url and 'webhook_url' in config:
                fallback_webhook = self._expand_env_var(config.get('webhook_url'))
                for channel in ['trading', 'news', 'earnings_weekly', 'earnings_realtime', 
                               'market_impact', 'volume_spike', 'odte_levels']:
                    if not self.webhooks.get(channel):
                        self.webhooks[channel] = fallback_webhook
        else:
            self.webhooks = {
                'trading': webhook_url,
                'news': webhook_url,
                'earnings_weekly': webhook_url,
                'earnings_realtime': webhook_url,
                'market_impact': webhook_url,
                'volume_spike': webhook_url,
                'odte_levels': webhook_url
            }
        
        active_channels = []
        for channel, url in self.webhooks.items():
            if url and not url.startswith('${') and url.startswith('http'):
                active_channels.append(channel)
        
        self.logger.info(f"Discord alerter initialized with channels: {', '.join(active_channels)}")
    
    def _expand_env_var(self, value: str) -> Optional[str]:
        """Expand environment variables"""
        if not value:
            return None
        
        if not value.startswith('${'):
            return value
        
        if value.startswith('${') and value.endswith('}'):
            var_name = value[2:-1]
            expanded = os.getenv(var_name)
            if expanded:
                return expanded
        
        return value
    
    def _send_webhook(self, channel: str, payload: Dict) -> bool:
        """Send webhook to specific channel"""
        webhook_url = self.webhooks.get(channel)
        
        if not webhook_url or webhook_url.startswith('${') or not webhook_url.startswith('http'):
            return False
        
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            self.logger.info(f"✅ Sent alert to Discord #{channel}")
            return True
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Discord webhook failed for {channel}: {str(e)}")
            return False
    
    def send_volume_spike_alert(self, symbol: str, volume_data: Dict, session: str = 'REGULAR') -> bool:
        """
        Send volume spike alert
        
        Args:
            symbol: Stock symbol
            volume_data: Volume analysis data (from calculate_intraday_spike or calculate_premarket_rvol)
            session: 'REGULAR' or 'PREMARKET'
        
        Returns:
            True if sent successfully
        """
        try:
            spike_ratio = volume_data.get('spike_ratio') or volume_data.get('rvol', 0)
            classification = volume_data.get('classification', 'UNKNOWN')
            direction = volume_data.get('direction', 'UNKNOWN')
            price_change = volume_data.get('price_change_pct', 0)
            alert_urgency = volume_data.get('alert_urgency', 'MEDIUM')
            
            # Determine emoji and color
            if classification == 'EXTREME':
                emoji = '🔥'
                color = 0xff0000  # Red
            elif classification == 'HIGH':
                emoji = '📈'
                color = 0xff6600  # Orange
            elif classification == 'ELEVATED':
                emoji = '📊'
                color = 0xffff00  # Yellow
            else:
                emoji = '📉'
                color = 0x666666  # Gray
            
            # Direction emoji
            if direction == 'BREAKOUT':
                dir_emoji = '🚀'
            elif direction == 'BREAKDOWN':
                dir_emoji = '⬇️'
            else:
                dir_emoji = '↔️'
            
            # Session display
            session_display = "PRE-MARKET" if session == 'PREMARKET' else "REGULAR HOURS"
            
            # Title
            title = f'{emoji} {symbol} - VOLUME SPIKE ({session_display})'
            if direction != 'UNKNOWN' and direction != 'NEUTRAL':
                title += f' {dir_emoji} {direction}'
            
            embed = {
                'title': title,
                'description': f'**{classification}** volume detected - {alert_urgency} priority',
                'color': color,
                'timestamp': datetime.utcnow().isoformat(),
                'fields': []
            }
            
            # Spike ratio / RVOL
            embed['fields'].append({
                'name': '📊 Volume Metrics',
                'value': (
                    f"**Spike Ratio:** {spike_ratio:.2f}x\n"
                    f"**Classification:** {classification}\n"
                    f"**Session:** {session_display}"
                ),
                'inline': True
            })
            
            # Price movement (if available)
            if price_change != 0:
                price_emoji = '📈' if price_change > 0 else '📉'
                embed['fields'].append({
                    'name': f'{price_emoji} Price Movement',
                    'value': (
                        f"**Change:** {price_change:+.2f}%\n"
                        f"**Direction:** {direction}"
                    ),
                    'inline': True
                })
            
            # Volume details
            if session == 'PREMARKET':
                current_vol = volume_data.get('current_5min_volume', 0)
                avg_vol = volume_data.get('avg_hist_5min_volume', 0)
                embed['fields'].append({
                    'name': '📦 Volume Details',
                    'value': (
                        f"**Current 5-min:** {self._format_volume(current_vol)}\n"
                        f"**Historical Avg:** {self._format_volume(avg_vol)}"
                    ),
                    'inline': True
                })
            else:
                current_bar = volume_data.get('current_bar_volume', 0)
                avg_bars = volume_data.get('avg_previous_volume', 0)
                embed['fields'].append({
                    'name': '📦 Volume Details',
                    'value': (
                        f"**Current Bar:** {self._format_volume(current_bar)}\n"
                        f"**Avg (10 bars):** {self._format_volume(avg_bars)}"
                    ),
                    'inline': True
                })
            
            # Action based on urgency
            if alert_urgency == 'CRITICAL' or classification == 'EXTREME':
                action = "🚨 **IMMEDIATE ACTION REQUIRED**\n✅ Check Bookmap NOW\n✅ Review for entry/exit\n✅ Check news catalyst"
            elif alert_urgency == 'HIGH' or classification == 'HIGH':
                action = "⚠️ **HIGH PRIORITY**\n✅ Monitor in Bookmap\n✅ Prepare for entry\n✅ Check for news"
            else:
                action = "👀 **WATCH CLOSELY**\n✅ Add to watchlist\n✅ Monitor for continuation"
            
            embed['fields'].append({
                'name': '🎯 Action Items',
                'value': action,
                'inline': False
            })
            
            # Footer
            embed['footer'] = {
                'text': f'Volume Spike Monitor • {datetime.now().strftime("%H:%M:%S ET")}'
            }
            
            payload = {'embeds': [embed]}
            return self._send_webhook('volume_spike', payload)
            
        except Exception as e:
            self.logger.error(f"Error sending volume spike alert: {str(e)}")
            return False
    
    def _format_volume(self, volume: int) -> str:
        """Format volume for display"""
        if volume >= 1_000_000:
            return f"{volume / 1_000_000:.1f}M"
        elif volume >= 1_000:
            return f"{volume / 1_000:.1f}K"
        else:
            return str(volume)
    
    def send_trading_signal(self, analysis: Dict) -> bool:
        """
        PHASE 1: Send trading signal with volume and key level data
        """
        symbol = analysis['symbol']
        alert_type = analysis.get('alert_type', 'MONITOR')
        confidence = analysis.get('confidence', 0)
        
        if alert_type == 'MONITOR':
            return False
        
        # Determine color and emoji
        if 'STRONG BUY' in alert_type:
            color = 0x00ff00
            emoji = '🟢🚀'
        elif 'BUY' in alert_type:
            color = 0x00cc00
            emoji = '🟢'
        elif 'STRONG SELL' in alert_type:
            color = 0xff0000
            emoji = '🔴⚡'
        elif 'SELL' in alert_type:
            color = 0xcc0000
            emoji = '🔴'
        elif 'MOMENTUM SHIFT' in alert_type:
            color = 0xffff00
            emoji = '⚠️'
        else:
            color = 0x666666
            emoji = '⚪'
        
        embed = {
            'title': f"{emoji} {alert_type} - {symbol}",
            'color': color,
            'timestamp': datetime.utcnow().isoformat(),
            'fields': []
        }
        
        # Price info
        embed['fields'].append({
            'name': '💰 Price Data',
            'value': (
                f"**Current:** ${analysis.get('current_price', 0):.2f}\n"
                f"**VWAP:** ${analysis.get('vwap', 0):.2f}\n"
                f"**Confidence:** {confidence:.0f}%"
            ),
            'inline': True
        })
        
        # PHASE 1: Volume Analysis
        volume_analysis = analysis.get('volume_analysis', {})
        if volume_analysis and 'error' not in volume_analysis:
            rvol = volume_analysis.get('rvol', {})
            spike = volume_analysis.get('volume_spike', {})
            
            volume_parts = []
            
            if rvol.get('rvol', 0) > 0:
                volume_parts.append(f"**RVOL:** {rvol['rvol']}x ({rvol.get('classification', 'N/A')})")
            
            if spike.get('spike_detected'):
                volume_parts.append(f"**Volume Spike:** {spike['spike_ratio']}x 🔥")
            
            if volume_analysis.get('summary'):
                volume_parts.append(f"**Summary:** {volume_analysis['summary'][:80]}")
            
            if volume_parts:
                embed['fields'].append({
                    'name': '📊 Volume Analysis (PHASE 1)',
                    'value': '\n'.join(volume_parts),
                    'inline': True
                })
        
        # PHASE 1: Key Level Detection
        key_levels = analysis.get('key_levels', {})
        if key_levels and 'error' not in key_levels:
            confluence_score = key_levels.get('confluence_score', 0)
            at_resistance = key_levels.get('at_resistance', False)
            at_support = key_levels.get('at_support', False)
            
            level_parts = []
            level_parts.append(f"**Confluence Score:** {confluence_score}/10")
            
            if at_resistance:
                level_parts.append(f"**At Resistance:** ⚠️ YES")
            if at_support:
                level_parts.append(f"**At Support:** ⚠️ YES")
            
            # Show confluent levels
            confluent_levels = key_levels.get('confluent_levels', [])
            if confluent_levels:
                level_parts.append(f"**Levels:**")
                for level in confluent_levels[:2]:  # Show top 2
                    level_parts.append(f"  • {level}")
            
            embed['fields'].append({
                'name': '🎯 Key Levels (PHASE 1)',
                'value': '\n'.join(level_parts),
                'inline': True
            })
        
        # Gap info
        gap_data = analysis.get('gap_data', {})
        if gap_data.get('gap_type') not in ['NO_GAP', 'UNKNOWN', None]:
            embed['fields'].append({
                'name': '⚠️ Gap Detected',
                'value': (
                    f"**Type:** {gap_data.get('gap_type', 'N/A')}\n"
                    f"**Size:** {gap_data.get('gap_size', 0)}%\n"
                    f"**Amount:** ${gap_data.get('gap_amount', 0):.2f}"
                ),
                'inline': True
            })
        
        # Market bias
        embed['fields'].append({
            'name': '📈 Market Bias',
            'value': (
                f"**1H:** {analysis.get('bias_1h', 'N/A')}\n"
                f"**Daily:** {analysis.get('bias_daily', 'N/A')}\n"
                f"**Options:** {analysis.get('options_sentiment', 'N/A')}"
            ),
            'inline': True
        })
        
        # Institutional flow
        embed['fields'].append({
            'name': '🦈 Institutional Flow',
            'value': (
                f"**Dark Pool:** {analysis.get('dark_pool_activity', 'N/A')}\n"
                f"**Bullish Score:** {analysis.get('bullish_score', 0)}\n"
                f"**Bearish Score:** {analysis.get('bearish_score', 0)}"
            ),
            'inline': True
        })
        
        # Entry targets
        entry_targets = analysis.get('entry_targets', {})
        if entry_targets and not entry_targets.get('insufficient_rr'):
            rr_ratio = entry_targets.get('risk_reward', 0)
            rr_emoji = '✅' if rr_ratio >= 2.0 else '⚠️'
            
            embed['fields'].append({
                'name': '🎯 Entry & Targets',
                'value': (
                    f"**Entry:** ${entry_targets.get('entry', 0):.2f}\n"
                    f"**TP1:** ${entry_targets.get('tp1', 0):.2f}\n"
                    f"**Stop Loss:** ${entry_targets.get('stop_loss', 0):.2f}\n"
                    f"**R:R Ratio:** {rr_ratio:.2f} {rr_emoji}"
                ),
                'inline': True
            })
        
        # News sentiment
        news = analysis.get('news', {})
        if news.get('news_impact') in ['HIGH', 'MEDIUM', 'EXTREME']:
            headlines = news.get('headlines', [])
            headline_text = headlines[0][:100] + '...' if headlines else 'N/A'
            
            embed['fields'].append({
                'name': '📰 News Impact',
                'value': (
                    f"**Sentiment:** {news.get('sentiment', 'N/A')}\n"
                    f"**Impact:** {news.get('news_impact', 'N/A')}\n"
                    f"**Latest:** {headline_text}"
                ),
                'inline': False
            })
        
        # Camarilla levels
        camarilla = analysis.get('camarilla', {})
        if camarilla:
            embed['fields'].append({
                'name': '📍 Key Levels (Camarilla)',
                'value': (
                    f"**R4:** ${camarilla.get('R4', 0):.2f} | "
                    f"**R3:** ${camarilla.get('R3', 0):.2f}\n"
                    f"**S3:** ${camarilla.get('S3', 0):.2f} | "
                    f"**S4:** ${camarilla.get('S4', 0):.2f}"
                ),
                'inline': False
            })
        
        # PHASE 1: Footer with total factors
        total_factors = analysis.get('total_factors_analyzed', 0)
        embed['footer'] = {
            'text': f"Phase 1 Enhanced • {total_factors} factors analyzed"
        }
        
        payload = {'embeds': [embed]}
        return self._send_webhook('trading', payload)
    
    def send_alert(self, analysis: Dict) -> bool:
        """Backward compatible method"""
        return self.send_trading_signal(analysis)
    
    def send_news_alert(self, symbol: str, news_data: Dict) -> bool:
        """Send news alert"""
        sentiment = news_data.get('sentiment', 'NEUTRAL')
        
        if 'POSITIVE' in sentiment:
            color = 0x00ff00
            emoji = '📈'
        elif 'NEGATIVE' in sentiment:
            color = 0xff0000
            emoji = '📉'
        else:
            color = 0x666666
            emoji = '📰'
        
        embed = {
            'title': f"{emoji} News Alert - {symbol}",
            'color': color,
            'timestamp': datetime.utcnow().isoformat(),
            'fields': [
                {
                    'name': '📰 Sentiment Analysis',
                    'value': (
                        f"**Sentiment:** {sentiment}\n"
                        f"**Impact:** {news_data.get('news_impact', 'N/A')}\n"
                        f"**Urgency:** {news_data.get('urgency', 'N/A')}\n"
                        f"**Score:** {news_data.get('sentiment_score', 0)}"
                    ),
                    'inline': False
                }
            ]
        }
        
        headlines = news_data.get('headlines', [])
        if headlines:
            headline_text = '\n'.join([f"• {h[:120]}..." for h in headlines[:3]])
            embed['fields'].append({
                'name': '🗞️ Latest Headlines',
                'value': headline_text,
                'inline': False
            })
        
        payload = {'embeds': [embed]}
        return self._send_webhook('news', payload)
    
    def send_market_impact_alert(self, alert_data: Dict) -> bool:
        """
        Send market impact alert (macro, M&A, analyst, spillover)
        Routes to: market_impact channel (DISCORD_NEWS_ALERTS)
        """
        try:
            article = alert_data['article']
            tickers = alert_data.get('tickers', [])
            classification = alert_data.get('classification', {})
            volume_confirmations = alert_data.get('volume_confirmations', {})
            spillover_opportunities = alert_data.get('spillover_opportunities', [])
            impact_score = alert_data.get('impact_score', 0)
            
            # Determine alert styling
            event_type = classification.get('type', 'GENERAL')
            priority = classification.get('priority', 'MEDIUM')
            
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
                'MACRO': '🌎',
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
            return self._send_webhook('market_impact', payload)
            
        except Exception as e:
            self.logger.error(f"Error sending market impact alert: {str(e)}")
            return False
    
    def send_weekly_earnings(self, earnings_list: list) -> bool:
        """Send weekly earnings calendar"""
        embed = {
            'title': '📅 Weekly Earnings Calendar',
            'description': f'Upcoming earnings for the week ({len(earnings_list)} companies)',
            'color': 0x0099ff,
            'timestamp': datetime.utcnow().isoformat(),
            'fields': []
        }
        
        from collections import defaultdict
        by_day = defaultdict(list)
        for earnings in earnings_list:
            date = earnings.get('date', 'TBD')
            by_day[date].append(earnings)
        
        for date in sorted(by_day.keys()):
            symbols = ', '.join([e['symbol'] for e in by_day[date]])
            embed['fields'].append({
                'name': date,
                'value': symbols,
                'inline': False
            })
        
        payload = {'embeds': [embed]}
        return self._send_webhook('earnings_weekly', payload)
    
    def send_earnings_alert(self, earnings_data: Dict) -> bool:
        """Send real-time earnings alert"""
        symbol = earnings_data['symbol']
        
        embed = {
            'title': f'⚡📊 EARNINGS RELEASE - {symbol}',
            'color': 0xff6600,
            'timestamp': datetime.utcnow().isoformat(),
            'fields': []
        }
        
        embed['fields'].append({
            'name': '📅 Earnings Date',
            'value': (
                f"**Date:** {earnings_data.get('date', 'TBD')}\n"
                f"**Time:** {earnings_data.get('time', 'N/A')}\n"
                f"**Fiscal Period:** {earnings_data.get('fiscal_period', 'N/A')}"
            ),
            'inline': True
        })
        
        if 'eps_estimate' in earnings_data:
            embed['fields'].append({
                'name': '💹 Estimates',
                'value': (
                    f"**EPS Est:** ${earnings_data.get('eps_estimate', 'N/A')}\n"
                    f"**Revenue Est:** {earnings_data.get('revenue_estimate', 'N/A')}"
                ),
                'inline': True
            })
        
        if 'eps_actual' in earnings_data:
            eps_surprise = earnings_data.get('eps_surprise', 0)
            surprise_emoji = '✅' if eps_surprise > 0 else '❌' if eps_surprise < 0 else '➖'
            
            embed['fields'].append({
                'name': f'{surprise_emoji} Actual Results',
                'value': (
                    f"**EPS Actual:** ${earnings_data.get('eps_actual', 'N/A')}\n"
                    f"**Surprise:** {eps_surprise}%\n"
                    f"**Revenue:** {earnings_data.get('revenue_actual', 'N/A')}"
                ),
                'inline': True
            })
        
        payload = {'embeds': [embed]}
        return self._send_webhook('earnings_realtime', payload)