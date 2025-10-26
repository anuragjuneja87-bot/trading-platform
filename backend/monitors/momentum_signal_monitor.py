"""
backend/monitors/momentum_signal_monitor.py
Momentum Signal Monitor - Combines RVOL + Dark Pool + Gamma Walls
Routes to: DISCORD_MOMENTUM_SIGNALS

TRIGGERS:
1. Momentum Buy Signal (4+ factors aligned)
2. Momentum Sell Signal (4+ factors aligned)
3. Gamma Wall Approach (price near magnet)
4. Dark Pool Direction Change (flip detected)
5. Extreme Confluence Setup (all factors perfect)
"""

import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import requests
import logging
import time
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Optional

from analyzers.enhanced_professional_analyzer import EnhancedProfessionalAnalyzer
from analyzers.confluence_alert_system import ConfluenceAlertSystem


class MomentumSignalMonitor:
    def __init__(self, polygon_api_key: str, config: dict, watchlist_manager):
        """
        Initialize Momentum Signal Monitor
        
        Combines:
        - RVOL (volume confirmation)
        - Dark Pool (institutional flow)
        - Gamma Walls (price magnets)
        - Key Levels (confluence)
        
        Routes to: DISCORD_MOMENTUM_SIGNALS
        """
        self.polygon_api_key = polygon_api_key
        self.config = config.get('momentum_signal_monitor', {})
        self.watchlist_manager = watchlist_manager
        
        self.logger = logging.getLogger(__name__)
        
        # Discord webhook
        self.discord_webhook = None
        
        # Monitoring state
        self.enabled = self.config.get('enabled', True)
        self.check_interval = self.config.get('check_interval', 60)
        self.market_hours_only = self.config.get('market_hours_only', True)
        
        # Cooldown tracking
        self.last_alert = defaultdict(lambda: defaultdict(float))
        self.cooldowns = self.config.get('cooldown_minutes', {
            'momentum_signal': 15,
            'gamma_approach': 10,
            'dark_pool_flip': 5,
            'extreme_setup': 30,
            'confluence_alert': 15  # Same as momentum
        })
        
        # Thresholds
        thresholds = self.config.get('thresholds', {})
        self.min_rvol = thresholds.get('min_rvol', 2.5)
        self.extreme_rvol = thresholds.get('extreme_rvol', 4.0)
        self.min_dark_pool_strength = thresholds.get('min_dark_pool_strength', 4)
        self.min_dark_pool_value = thresholds.get('min_dark_pool_value', 1000000)
        self.gamma_wall_distance = thresholds.get('gamma_wall_distance_pct', 1.0)
        self.gamma_wall_urgent = thresholds.get('gamma_wall_urgent_pct', 0.5)
        self.min_confluence = thresholds.get('min_confluence', 7)
        self.extreme_confluence = thresholds.get('extreme_confluence', 8)
        
        # Filters
        filters = self.config.get('filters', {})
        self.watchlist_only = filters.get('watchlist_only', True)
        self.min_price = filters.get('min_price', 5.0)
        self.max_alerts_per_symbol_per_day = filters.get('max_alert_per_symbol_per_day', 5)
        
        # Track previous dark pool direction
        self.previous_dark_pool_direction = {}
        
        # Daily alert counter
        self.daily_alerts = defaultdict(int)
        self.last_reset_date = datetime.now().date()
        
        # Statistics
        self.stats = {
            'total_checks': 0,
            'momentum_buy_signals': 0,
            'momentum_sell_signals': 0,
            'gamma_approaches': 0,
            'dark_pool_flips': 0,
            'extreme_setups': 0,
            'total_alerts_sent': 0
        }
        
        # Initialize analyzer
        self.analyzer = EnhancedProfessionalAnalyzer(
            polygon_api_key=polygon_api_key,
            debug_mode=False
        )
        
        # Initialize Confluence Alert System (Feature #5)
        self.confluence_system = ConfluenceAlertSystem()
        
        self.logger.info("✅ Momentum Signal Monitor initialized")
        self.logger.info(f"   Check Interval: {self.check_interval}s")
        self.logger.info(f"   Min RVOL: {self.min_rvol}x")
        self.logger.info(f"   Min Dark Pool Strength: {self.min_dark_pool_strength}")
        self.logger.info(f"   Gamma Wall Distance: {self.gamma_wall_distance}%")
        self.logger.info(f"   🎯 Confluence alerts: 75%+ confidence")
    
    def set_discord_webhook(self, webhook_url: str):
        """Set Discord webhook URL"""
        self.discord_webhook = webhook_url
        self.logger.info(f"✅ Discord webhook configured for Momentum Signals")
    
    def is_market_hours(self) -> bool:
        """Check if currently in market hours"""
        now = datetime.now()
        
        # Check if weekday
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Check time (9:30 AM - 4:00 PM ET)
        current_time = now.time()
        market_open = datetime.strptime("09:30", "%H:%M").time()
        market_close = datetime.strptime("16:00", "%H:%M").time()
        
        return market_open <= current_time <= market_close
    
    def reset_daily_counters(self):
        """Reset daily alert counters at midnight"""
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.daily_alerts.clear()
            self.last_reset_date = today
            self.logger.info("📅 Daily alert counters reset")
    
    def can_alert(self, symbol: str, alert_type: str) -> bool:
        """Check if can send alert (cooldown + daily limit)"""
        # Check daily limit
        if self.daily_alerts[symbol] >= self.max_alerts_per_symbol_per_day:
            return False
        
        # Check cooldown
        now = time.time()
        last_alert_time = self.last_alert[symbol][alert_type]
        cooldown_seconds = self.cooldowns.get(alert_type, 15) * 60
        
        if now - last_alert_time < cooldown_seconds:
            return False
        
        return True
    
    def mark_alerted(self, symbol: str, alert_type: str):
        """Mark symbol as alerted"""
        self.last_alert[symbol][alert_type] = time.time()
        self.daily_alerts[symbol] += 1
    
    def send_discord_alert(self, embed: dict):
        """Send alert to Discord"""
        if not self.discord_webhook:
            return False
        
        try:
            payload = {'embeds': [embed]}
            response = requests.post(self.discord_webhook, json=payload, timeout=10)
            response.raise_for_status()
            
            self.stats['total_alerts_sent'] += 1
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send Discord alert: {str(e)}")
            return False
    
    def check_momentum_buy_signal(self, symbol: str, data: dict) -> Optional[dict]:
        """
        TRIGGER 1: Momentum Buy Signal
        Requires 4+ bullish factors
        """
        factors = []
        factor_count = 0
        
        # Factor 1: Dark Pool Buying
        dark_pool = data.get('dark_pool_details', {})
        if dark_pool.get('institutional_flow') == 'BUYING':
            strength = dark_pool.get('signal_strength', 0)
            if strength >= self.min_dark_pool_strength:
                factors.append(f"Dark Pool BUYING (strength: {strength})")
                factor_count += 1
        
        # Factor 2: High RVOL
        volume_analysis = data.get('volume_analysis', {})
        rvol_data = volume_analysis.get('rvol', {})
        rvol = rvol_data.get('rvol', 0)
        if rvol >= self.min_rvol:
            factors.append(f"RVOL {rvol:.1f}x ({rvol_data.get('classification', 'HIGH')})")
            factor_count += 1
        
        # Factor 3: Near Gamma Wall Support
        open_interest = data.get('open_interest', {})
        nearest_wall = open_interest.get('nearest_wall')
        if nearest_wall and nearest_wall['type'] == 'support':
            distance = nearest_wall.get('distance_pct', 999)
            if distance <= self.gamma_wall_distance:
                factors.append(f"Gamma Support ${nearest_wall['strike']} ({distance:.1f}% away)")
                factor_count += 1
        
        # Factor 4: High Confluence Support
        key_levels = data.get('key_levels', {})
        if key_levels.get('at_support') and key_levels.get('confluence_score', 0) >= self.min_confluence:
            confluence = key_levels['confluence_score']
            factors.append(f"High Confluence Support ({confluence}/10)")
            factor_count += 1
        
        # Factor 5: Price Below VWAP (oversold)
        if data.get('current_price', 0) < data.get('vwap', 999999):
            factors.append("Price < VWAP (oversold)")
            factor_count += 1
        
        # Factor 6: Positive News
        news = data.get('news', {})
        if news.get('sentiment') in ['POSITIVE', 'VERY POSITIVE']:
            factors.append(f"News: {news['sentiment']}")
            factor_count += 1
        
        # Need 4+ factors
        if factor_count >= 4:
            return {
                'type': 'momentum_buy',
                'factors': factors,
                'factor_count': factor_count,
                'confidence': min(factor_count / 6 * 100, 95),
                'data': data
            }
        
        return None
    
    def check_momentum_sell_signal(self, symbol: str, data: dict) -> Optional[dict]:
        """
        TRIGGER 2: Momentum Sell Signal
        Requires 4+ bearish factors
        """
        factors = []
        factor_count = 0
        
        # Factor 1: Dark Pool Selling
        dark_pool = data.get('dark_pool_details', {})
        if dark_pool.get('institutional_flow') == 'SELLING':
            strength = dark_pool.get('signal_strength', 0)
            if strength >= self.min_dark_pool_strength:
                factors.append(f"Dark Pool SELLING (strength: {strength})")
                factor_count += 1
        
        # Factor 2: High RVOL
        volume_analysis = data.get('volume_analysis', {})
        rvol_data = volume_analysis.get('rvol', {})
        rvol = rvol_data.get('rvol', 0)
        if rvol >= self.min_rvol:
            factors.append(f"RVOL {rvol:.1f}x ({rvol_data.get('classification', 'HIGH')})")
            factor_count += 1
        
        # Factor 3: Near Gamma Wall Resistance
        open_interest = data.get('open_interest', {})
        nearest_wall = open_interest.get('nearest_wall')
        if nearest_wall and nearest_wall['type'] == 'resistance':
            distance = nearest_wall.get('distance_pct', 999)
            if distance <= self.gamma_wall_distance:
                factors.append(f"Gamma Resistance ${nearest_wall['strike']} ({distance:.1f}% away)")
                factor_count += 1
        
        # Factor 4: High Confluence Resistance
        key_levels = data.get('key_levels', {})
        if key_levels.get('at_resistance') and key_levels.get('confluence_score', 0) >= self.min_confluence:
            confluence = key_levels['confluence_score']
            factors.append(f"High Confluence Resistance ({confluence}/10)")
            factor_count += 1
        
        # Factor 5: Price Above VWAP (overbought)
        if data.get('current_price', 0) > data.get('vwap', 0):
            factors.append("Price > VWAP (overbought)")
            factor_count += 1
        
        # Factor 6: Negative News
        news = data.get('news', {})
        if news.get('sentiment') in ['NEGATIVE', 'VERY NEGATIVE']:
            factors.append(f"News: {news['sentiment']}")
            factor_count += 1
        
        # Need 4+ factors
        if factor_count >= 4:
            return {
                'type': 'momentum_sell',
                'factors': factors,
                'factor_count': factor_count,
                'confidence': min(factor_count / 6 * 100, 95),
                'data': data
            }
        
        return None
    
    def check_gamma_wall_approach(self, symbol: str, data: dict) -> Optional[dict]:
        """
        TRIGGER 3: Gamma Wall Approach
        Price within 0.5-1% of gamma wall + RVOL confirmation
        """
        open_interest = data.get('open_interest', {})
        nearest_wall = open_interest.get('nearest_wall')
        
        if not nearest_wall:
            return None
        
        distance = nearest_wall.get('distance_pct', 999)
        
        # Must be within threshold
        if distance > self.gamma_wall_distance:
            return None
        
        # RVOL confirmation
        volume_analysis = data.get('volume_analysis', {})
        rvol = volume_analysis.get('rvol', {}).get('rvol', 0)
        
        if rvol < 2.0:  # Need at least 2x RVOL
            return None
        
        # Dark Pool confirmation
        dark_pool = data.get('dark_pool_details', {})
        flow = dark_pool.get('institutional_flow', 'NEUTRAL')
        
        # Check if flow matches wall type
        if nearest_wall['type'] == 'support' and flow != 'BUYING':
            return None
        if nearest_wall['type'] == 'resistance' and flow != 'SELLING':
            return None
        
        urgency = 'URGENT' if distance <= self.gamma_wall_urgent else 'HIGH'
        
        return {
            'type': 'gamma_approach',
            'wall': nearest_wall,
            'distance': distance,
            'rvol': rvol,
            'flow': flow,
            'urgency': urgency,
            'data': data
        }
    
    def check_dark_pool_flip(self, symbol: str, data: dict) -> Optional[dict]:
        """
        TRIGGER 4: Dark Pool Direction Change
        Institutional flow flipped in last check
        """
        dark_pool = data.get('dark_pool_details', {})
        current_flow = dark_pool.get('institutional_flow', 'NEUTRAL')
        
        # Get previous flow
        previous_flow = self.previous_dark_pool_direction.get(symbol, 'NEUTRAL')
        
        # Update tracking
        self.previous_dark_pool_direction[symbol] = current_flow
        
        # Check for flip
        if previous_flow in ['BUYING', 'SELLING'] and current_flow in ['BUYING', 'SELLING']:
            if previous_flow != current_flow:
                strength = dark_pool.get('signal_strength', 0)
                block_value = dark_pool.get('block_trade_value', 0)
                
                # Must meet minimum criteria
                if strength >= 3 and block_value >= self.min_dark_pool_value:
                    return {
                        'type': 'dark_pool_flip',
                        'previous': previous_flow,
                        'current': current_flow,
                        'strength': strength,
                        'block_value': block_value,
                        'data': data
                    }
        
        return None
    
    def check_extreme_setup(self, symbol: str, data: dict) -> Optional[dict]:
        """
        TRIGGER 5: Extreme Confluence Setup
        ALL factors perfectly aligned (RARE!)
        """
        # Dark Pool: Max strength
        dark_pool = data.get('dark_pool_details', {})
        dark_pool_strength = dark_pool.get('signal_strength', 0)
        if dark_pool_strength < 5:
            return None
        
        # RVOL: Extreme
        volume_analysis = data.get('volume_analysis', {})
        rvol = volume_analysis.get('rvol', {}).get('rvol', 0)
        if rvol < self.extreme_rvol:
            return None
        
        # Gamma Wall: Very close
        open_interest = data.get('open_interest', {})
        nearest_wall = open_interest.get('nearest_wall')
        if not nearest_wall or nearest_wall.get('distance_pct', 999) > self.gamma_wall_urgent:
            return None
        
        # Key Levels: Extreme confluence
        key_levels = data.get('key_levels', {})
        confluence = key_levels.get('confluence_score', 0)
        if confluence < self.extreme_confluence:
            return None
        
        # Volume Spike: Detected
        spike_data = volume_analysis.get('volume_spike', {})
        if not spike_data.get('spike_detected'):
            return None
        
        # ALL FACTORS ALIGNED!
        flow = dark_pool.get('institutional_flow')
        direction = 'BUY' if flow == 'BUYING' else 'SELL'
        
        return {
            'type': 'extreme_setup',
            'direction': direction,
            'dark_pool_strength': dark_pool_strength,
            'rvol': rvol,
            'gamma_wall': nearest_wall,
            'confluence': confluence,
            'spike_ratio': spike_data.get('spike_ratio', 0),
            'data': data
        }
    
    def create_momentum_signal_embed(self, symbol: str, signal: dict) -> dict:
        """Create Discord embed for momentum buy/sell signal"""
        data = signal['data']
        is_buy = signal['type'] == 'momentum_buy'
        
        embed = {
            'title': f"{'🟢 MOMENTUM BUY SIGNAL' if is_buy else '🔴 MOMENTUM SELL SIGNAL'}: {symbol}",
            'color': 0x00ff00 if is_buy else 0xff0000,
            'timestamp': datetime.utcnow().isoformat(),
            'fields': []
        }
        
        # Factors
        factors_text = '\n'.join([f"✅ {f}" for f in signal['factors']])
        embed['fields'].append({
            'name': f"📊 Factors ({signal['factor_count']}/6)",
            'value': factors_text,
            'inline': False
        })
        
        # Price & Levels
        dark_pool = data.get('dark_pool_details', {})
        entry_targets = data.get('entry_targets', {})
        
        price_info = f"**Current:** ${data.get('current_price', 0):.2f}\n"
        price_info += f"**VWAP:** ${data.get('vwap', 0):.2f}\n"
        
        if entry_targets.get('entry'):
            price_info += f"\n**Entry:** ${entry_targets['entry']:.2f}\n"
            price_info += f"**Stop:** ${entry_targets['stop_loss']:.2f}\n"
            price_info += f"**Target:** ${entry_targets['tp1']:.2f}"
        
        embed['fields'].append({
            'name': '💰 Levels',
            'value': price_info,
            'inline': True
        })
        
        # Dark Pool Details
        dp_info = f"**Flow:** {dark_pool.get('institutional_flow', 'N/A')}\n"
        dp_info += f"**Activity:** {dark_pool.get('activity', 'N/A')}\n"
        block_value = dark_pool.get('block_trade_value', 0)
        if block_value > 0:
            dp_info += f"**Value:** ${block_value/1000000:.1f}M"
        
        embed['fields'].append({
            'name': '🏦 Dark Pool',
            'value': dp_info,
            'inline': True
        })
        
        # Confidence
        embed['footer'] = {
            'text': f"⏰ {datetime.now().strftime('%I:%M %p ET')} | Confidence: {signal['confidence']:.0f}%"
        }
        
        return embed
    
    def create_gamma_approach_embed(self, symbol: str, signal: dict) -> dict:
        """Create Discord embed for gamma wall approach"""
        data = signal['data']
        wall = signal['wall']
        
        embed = {
            'title': f"⚡ GAMMA WALL APPROACH: {symbol}",
            'color': 0xffff00,
            'timestamp': datetime.utcnow().isoformat(),
            'fields': []
        }
        
        # Wall Info
        wall_emoji = '🛡️' if wall['type'] == 'support' else '⚠️'
        wall_info = f"{wall_emoji} **${wall['strike']}** ({wall['type'].upper()})\n"
        wall_info += f"**Distance:** {signal['distance']:.1f}%\n"
        wall_info += f"**Current Price:** ${data.get('current_price', 0):.2f}"
        
        embed['fields'].append({
            'name': '🎯 Gamma Wall',
            'value': wall_info,
            'inline': False
        })
        
        # Confirmation
        confirm_info = f"**RVOL:** {signal['rvol']:.1f}x\n"
        confirm_info += f"**Dark Pool:** {signal['flow']}\n"
        confirm_info += f"**Urgency:** {signal['urgency']}"
        
        embed['fields'].append({
            'name': '✅ Confirmation',
            'value': confirm_info,
            'inline': False
        })
        
        # Action
        action = f"🎲 **HIGH probability** {'bounce' if wall['type'] == 'support' else 'rejection'} at ${wall['strike']}\n"
        action += f"Watch for entry on {'touch' if wall['type'] == 'support' else 'rejection'}!"
        
        embed['fields'].append({
            'name': '💡 Action',
            'value': action,
            'inline': False
        })
        
        embed['footer'] = {
            'text': f"⏰ {datetime.now().strftime('%I:%M %p ET')}"
        }
        
        return embed
    
    def create_dark_pool_flip_embed(self, symbol: str, signal: dict) -> dict:
        """Create Discord embed for dark pool direction change"""
        data = signal['data']
        
        embed = {
            'title': f"🔄 DARK POOL DIRECTION CHANGE: {symbol}",
            'color': 0xff6600,
            'timestamp': datetime.utcnow().isoformat(),
            'fields': []
        }
        
        # Direction Change
        change_info = f"⚠️ **{signal['previous']} → {signal['current']}**\n"
        change_info += f"**Strength:** {'█' * signal['strength']}\n"
        block_value = signal['block_value']
        change_info += f"**Block Value:** ${block_value/1000000:.1f}M"
        
        embed['fields'].append({
            'name': '🔄 Flow Change',
            'value': change_info,
            'inline': False
        })
        
        # Action
        if signal['current'] == 'SELLING':
            action = "🚨 **ACTION: EXIT LONGS IMMEDIATELY**\n"
            action += "This is a REVERSAL signal!"
        else:
            action = "✅ **ACTION: EXIT SHORTS / PREPARE LONGS**\n"
            action += "Institutional flow reversed bullish!"
        
        embed['fields'].append({
            'name': '💡 Action',
            'value': action,
            'inline': False
        })
        
        embed['footer'] = {
            'text': f"⏰ {datetime.now().strftime('%I:%M %p ET')} | Changed in last check"
        }
        
        return embed
    
    def create_extreme_setup_embed(self, symbol: str, signal: dict) -> dict:
        """Create Discord embed for extreme confluence setup"""
        data = signal['data']
        wall = signal['gamma_wall']
        entry_targets = data.get('entry_targets', {})
        
        embed = {
            'title': f"🔥🔥🔥 EXTREME SETUP: {symbol} 🔥🔥🔥",
            'description': '💎 **HIGHEST CONVICTION SIGNAL**',
            'color': 0xff00ff,
            'timestamp': datetime.utcnow().isoformat(),
            'fields': []
        }
        
        # All Factors
        factors = f"**Dark Pool:** {'█' * signal['dark_pool_strength']} (HEAVY)\n"
        factors += f"**RVOL:** {signal['rvol']:.1f}x (EXTREME)\n"
        factors += f"**Spike:** {signal['spike_ratio']:.1f}x 🚀\n"
        factors += f"**Gamma Wall:** ${wall['strike']} ({wall['distance_pct']:.1f}% away)\n"
        factors += f"**Confluence:** {signal['confluence']}/10"
        
        embed['fields'].append({
            'name': '🎯 Perfect Alignment',
            'value': factors,
            'inline': False
        })
        
        # Entry Plan
        if entry_targets.get('entry'):
            entry_info = f"**{signal['direction']} ZONE:** ${entry_targets['entry']:.2f}\n"
            entry_info += f"**STOP:** ${entry_targets['stop_loss']:.2f}\n"
            entry_info += f"**TARGET 1:** ${entry_targets['tp1']:.2f}\n"
            entry_info += f"**TARGET 2:** ${entry_targets.get('tp2', 0):.2f}\n"
            entry_info += f"\n**R/R:** {entry_targets.get('risk_reward', 0):.1f}:1"
            
            embed['fields'].append({
                'name': '📈 Trade Plan',
                'value': entry_info,
                'inline': False
            })
        
        # Warning
        embed['fields'].append({
            'name': '🚀 HIGH PRIORITY',
            'value': '**THIS IS A RARE SETUP - MAXIMUM CONVICTION!**',
            'inline': False
        })
        
        embed['footer'] = {
            'text': f"⏰ {datetime.now().strftime('%I:%M %p ET')} | Confidence: 97%"
        }
        
        return embed
    
    def check_symbol(self, symbol: str):
        """Check a single symbol for momentum signals"""
        try:
            # Get full analysis
            data = self.analyzer.generate_professional_signal(symbol)
            
            if data.get('error'):
                return
            
            # Filter by price
            if data.get('current_price', 0) < self.min_price:
                return
            
            # Check all triggers
            
            # Trigger 5: Extreme Setup (check first - highest priority)
            extreme = self.check_extreme_setup(symbol, data)
            if extreme and self.can_alert(symbol, 'extreme_setup'):
                embed = self.create_extreme_setup_embed(symbol, extreme)
                if self.send_discord_alert(embed):
                    self.mark_alerted(symbol, 'extreme_setup')
                    self.stats['extreme_setups'] += 1
                    self.logger.info(f"🔥 EXTREME SETUP ALERT: {symbol}")
                return  # Don't check other triggers if extreme detected
            
            # Trigger 4: Dark Pool Flip (check second - time sensitive)
            flip = self.check_dark_pool_flip(symbol, data)
            if flip and self.can_alert(symbol, 'dark_pool_flip'):
                embed = self.create_dark_pool_flip_embed(symbol, flip)
                if self.send_discord_alert(embed):
                    self.mark_alerted(symbol, 'dark_pool_flip')
                    self.stats['dark_pool_flips'] += 1
                    self.logger.info(f"🔄 DARK POOL FLIP ALERT: {symbol} ({flip['previous']} → {flip['current']})")
            
            # Trigger 3: Gamma Wall Approach
            gamma = self.check_gamma_wall_approach(symbol, data)
            if gamma and self.can_alert(symbol, 'gamma_approach'):
                embed = self.create_gamma_approach_embed(symbol, gamma)
                if self.send_discord_alert(embed):
                    self.mark_alerted(symbol, 'gamma_approach')
                    self.stats['gamma_approaches'] += 1
                    self.logger.info(f"⚡ GAMMA APPROACH ALERT: {symbol} (${gamma['wall']['strike']})")
            
            # Trigger 1: Momentum Buy Signal
            buy_signal = self.check_momentum_buy_signal(symbol, data)
            if buy_signal and self.can_alert(symbol, 'momentum_signal'):
                embed = self.create_momentum_signal_embed(symbol, buy_signal)
                if self.send_discord_alert(embed):
                    self.mark_alerted(symbol, 'momentum_signal')
                    self.stats['momentum_buy_signals'] += 1
                    self.logger.info(f"🟢 MOMENTUM BUY ALERT: {symbol} ({buy_signal['factor_count']} factors)")
            
            # Trigger 2: Momentum Sell Signal
            sell_signal = self.check_momentum_sell_signal(symbol, data)
            if sell_signal and self.can_alert(symbol, 'momentum_signal'):
                embed = self.create_momentum_signal_embed(symbol, sell_signal)
                if self.send_discord_alert(embed):
                    self.mark_alerted(symbol, 'momentum_signal')
                    self.stats['momentum_sell_signals'] += 1
                    self.logger.info(f"🔴 MOMENTUM SELL ALERT: {symbol} ({sell_signal['factor_count']} factors)")
            
            # FEATURE #5: Confluence Alert (75%+ confidence)
            confluence = self.check_confluence_alert(symbol, data)
            if confluence and self.can_alert(symbol, 'confluence_alert'):
                embed = self.create_confluence_embed(symbol, confluence)
                if self.send_discord_alert(embed):
                    self.mark_alerted(symbol, 'confluence_alert')
                    self.stats['total_alerts_sent'] += 1
                    priority = confluence['confluence']['priority']
                    confidence = confluence['confluence']['confidence']
                    self.logger.info(f"🎯 CONFLUENCE ALERT: {symbol} ({confidence:.0f}% - {priority})")
            
        except Exception as e:
            self.logger.error(f"Error checking {symbol}: {str(e)}")
    
    def run_single_check(self) -> int:
        """Run a single check cycle, returns number of alerts sent"""
        alerts_before = self.stats['total_alerts_sent']
        
        try:
            # Get watchlist
            if self.watchlist_only:
                symbols = self.watchlist_manager.load_symbols()
            else:
                symbols = ['SPY', 'QQQ', 'NVDA', 'TSLA', 'AAPL']
            
            self.logger.info(f"🔍 Checking {len(symbols)} symbols for momentum signals...")
            
            # Check each symbol
            for symbol in symbols:
                self.check_symbol(symbol)
            
            self.stats['total_checks'] += 1
            
        except Exception as e:
            self.logger.error(f"Error in check cycle: {str(e)}")
        
        return self.stats['total_alerts_sent'] - alerts_before
    
    def run_continuous(self):
        """Run continuous monitoring loop"""
        self.logger.info("🚀 Starting Momentum Signal Monitor...")
        self.logger.info(f"   Market Hours Only: {self.market_hours_only}")
        
        while self.enabled:
            try:
                # Reset daily counters if needed
                self.reset_daily_counters()
                
                # Check if should run
                if self.market_hours_only and not self.is_market_hours():
                    self.logger.debug("Outside market hours, skipping check")
                    time.sleep(60)
                    continue
                
                # Run check
                alerts_sent = self.run_single_check()
                
                if alerts_sent > 0:
                    self.logger.info(f"✅ Sent {alerts_sent} alerts in this cycle")
                
                # Sleep until next check
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                self.logger.info("Momentum Signal Monitor stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {str(e)}")
                time.sleep(60)


    # ========================================================================
    # FEATURE #5: CONFLUENCE ALERT METHODS
    # ========================================================================
    
    def check_confluence_alert(self, symbol: str, data: Dict) -> Optional[Dict]:
        """
        Check if confluence alert should be sent (75%+ confidence)
        
        Returns confluence analysis if should alert, None otherwise
        """
        try:
            # Analyze confluence
            confluence_result = self.confluence_system.analyze_confluence(symbol, data)
            
            if not confluence_result.get('available'):
                return None
            
            confluence_data = confluence_result['confluence']
            
            # Check if meets alert threshold (75%+)
            if not confluence_data['should_alert']:
                return None
            
            # Check cooldown (use same as momentum_signal)
            alert_type = 'confluence_alert'
            if not self.confluence_system.check_cooldown(symbol, alert_type):
                return None
            
            # Mark as sent
            self.confluence_system.mark_alert_sent(symbol, alert_type)
            
            return confluence_result
            
        except Exception as e:
            self.logger.error(f"Error checking confluence for {symbol}: {str(e)}")
            return None
    
    def create_confluence_embed(self, symbol: str, confluence_result: Dict) -> dict:
        """Create Discord embed for confluence alert"""
        
        confluence = confluence_result['confluence']
        confidence = confluence['confidence']
        direction = confluence['direction']
        priority = confluence['priority']
        setup_type = confluence['setup_type']
        signals = confluence_result['active_signals']
        current_price = confluence_result['current_price']
        targets = confluence_result.get('targets', {})
        
        # Determine color based on priority
        if priority == 'EXTREME':
            color = 0xFF0000  # Red - Extreme
            emoji = '🔥🔥🔥'
        elif priority == 'HIGH':
            color = 0xFF6600  # Orange - High
            emoji = '🔥🔥'
        else:
            color = 0xFFD700  # Gold - Medium
            emoji = '🔥'
        
        # Direction emoji
        dir_emoji = '📈' if direction == 'BULLISH' else '📉'
        
        embed = {
            'title': f"{emoji} {priority} CONFLUENCE - {symbol}",
            'description': f"**{confidence:.0f}% Confidence** {dir_emoji} {direction} {setup_type}",
            'color': color,
            'timestamp': datetime.utcnow().isoformat(),
            'fields': []
        }
        
        # Current price
        embed['fields'].append({
            'name': '💰 Current Price',
            'value': f"**${current_price:.2f}**",
            'inline': True
        })
        
        # Signals count
        embed['fields'].append({
            'name': '✅ Signals Aligned',
            'value': f"**{len(signals)}/{len(confluence_result['all_signals'])}** factors",
            'inline': True
        })
        
        # Priority
        embed['fields'].append({
            'name': '⚡ Priority',
            'value': f"**{priority}**",
            'inline': True
        })
        
        # Active signals breakdown
        signals_text = ""
        for signal in signals:
            name = signal['name'].replace('_', ' ').title()
            strength_pct = int(signal['strength'] * 100)
            reason = signal['reason']
            
            if signal['direction'] == 'BULLISH':
                emoji_dir = '🟢'
            else:
                emoji_dir = '🔴'
            
            signals_text += f"{emoji_dir} **{name}** ({strength_pct}%)\n└─ {reason}\n\n"
        
        embed['fields'].append({
            'name': '📊 Active Signals',
            'value': signals_text.strip(),
            'inline': False
        })
        
        # Targets (if available)
        if targets.get('entry'):
            targets_text = (
                f"**Entry:** ${targets['entry']:.2f}\n"
                f"**TP1:** ${targets['tp1']:.2f}\n"
                f"**TP2:** ${targets['tp2']:.2f}\n"
                f"**Stop:** ${targets['stop_loss']:.2f}\n"
                f"**R:R:** {targets.get('risk_reward', 0):.1f}"
            )
            embed['fields'].append({
                'name': '🎯 Targets',
                'value': targets_text,
                'inline': False
            })
        
        # Interpretation
        interpretation = confluence_result.get('interpretation', '')
        if interpretation:
            # Truncate if too long
            if len(interpretation) > 500:
                interpretation = interpretation[:497] + "..."
            
            embed['fields'].append({
                'name': '💡 Analysis',
                'value': interpretation,
                'inline': False
            })
        
        # Footer
        embed['footer'] = {
            'text': f'Confluence Alert System • {priority} • {datetime.now().strftime("%H:%M:%S ET")}'
        }
        
        return embed


# CLI Testing
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    import yaml
    from utils.watchlist_manager import WatchlistManager
    
    load_dotenv()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    API_KEY = os.getenv('POLYGON_API_KEY')
    WEBHOOK = os.getenv('DISCORD_MOMENTUM_SIGNALS')
    
    # Load config
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize
    watchlist_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'watchlist.txt')
    watchlist_manager = WatchlistManager(watchlist_file=watchlist_path)
    
    monitor = MomentumSignalMonitor(
        polygon_api_key=API_KEY,
        config=config,
        watchlist_manager=watchlist_manager
    )
    
    if WEBHOOK:
        monitor.set_discord_webhook(WEBHOOK)
    
    print("=" * 80)
    print("MOMENTUM SIGNAL MONITOR - TEST MODE")
    print("=" * 80)
    print(f"Check Interval: {monitor.check_interval}s")
    print(f"Min RVOL: {monitor.min_rvol}x")
    print(f"Market Hours Only: {monitor.market_hours_only}")
    print("\nRunning single check...")
    print("=" * 80)
    
    alerts = monitor.run_single_check()
    
    print("\n" + "=" * 80)
    print(f"RESULTS: {alerts} alerts sent")
    print(f"Stats: {monitor.stats}")
    print("=" * 80)