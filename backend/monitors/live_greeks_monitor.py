"""
backend/monitors/live_greeks_monitor.py
Live Delta/Gamma Monitor for Fast Scalping
Updates every 10s, Discord alerts on significant changes
"""

import threading
import time
import logging
from datetime import datetime
from typing import Dict, Optional


class LiveGreeksMonitor:
    def __init__(self, analyzer, discord_alerter, check_interval: int = 10):
        """
        Initialize Live Greeks Monitor
        
        Args:
            analyzer: EnhancedProfessionalAnalyzer instance
            discord_alerter: DiscordAlerter instance
            check_interval: Check interval in seconds (default 10s)
        """
        self.analyzer = analyzer
        self.discord = discord_alerter
        self.check_interval = check_interval
        self.logger = logging.getLogger(__name__)
        
        self.running = False
        self.thread = None
        
        # Track previous greeks for delta detection
        self.previous_greeks = {}  # {symbol: {'delta': float, 'gamma': float, 'timestamp': str}}
        
        # Alert thresholds
        self.delta_change_threshold = 0.05  # Alert if delta changes >5%
        self.gamma_wall_proximity_pct = 3.0  # Alert if within 3% of gamma wall
        
        self.stats = {
            'checks_performed': 0,
            'alerts_sent': 0,
            'last_check': None
        }
    
    def start(self, watchlist):
        """Start monitoring"""
        if self.running:
            self.logger.warning("Live greeks monitor already running")
            return
        
        self.running = True
        self.watchlist = watchlist
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        self.logger.info(f"🔴 Live Greeks Monitor started (every {self.check_interval}s)")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self.logger.info("Live greeks monitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                for symbol in self.watchlist:
                    self.check_symbol_greeks(symbol)
                
                self.stats['checks_performed'] += 1
                self.stats['last_check'] = datetime.now().isoformat()
                
                time.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(f"Error in greeks monitor loop: {str(e)}")
                time.sleep(30)
    
    def get_live_greeks(self, symbol: str) -> Optional[Dict]:
        """Get current greeks for a symbol"""
        try:
            # Get current quote
            quote = self.analyzer.get_real_time_quote(symbol)
            current_price = quote['price']
            
            if current_price == 0:
                return None
            
            # Get gamma analysis
            oi_data = self.analyzer.analyze_open_interest(symbol, current_price)
            
            if not oi_data.get('available'):
                return None
            
            # Calculate closest gamma wall
            gamma_levels = oi_data.get('gamma_levels', [])
            closest_wall = None
            min_distance = float('inf')
            
            for level in gamma_levels:
                distance_pct = abs(level['distance_pct'])
                if distance_pct < min_distance:
                    min_distance = distance_pct
                    closest_wall = level
            
            # Get ATM option greeks (approximate)
            delta = self._estimate_delta(current_price, closest_wall, oi_data)
            gamma = closest_wall.get('gamma_exposure', 0) if closest_wall else 0
            
            result = {
                'symbol': symbol,
                'price': current_price,
                'delta': delta,
                'gamma': gamma,
                'wall_strike': closest_wall['strike'] if closest_wall else None,
                'wall_distance_pct': min_distance if closest_wall else None,
                'wall_type': closest_wall['direction'] if closest_wall else None,
                'timestamp': datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting greeks for {symbol}: {str(e)}")
            return None
    
    def _estimate_delta(self, current_price, wall, oi_data):
        """Estimate delta based on position relative to gamma wall"""
        if not wall:
            return 0.50  # Default ATM
        
        # Rough estimation based on distance from wall
        distance_pct = wall['distance_pct']
        
        if wall['direction'] == 'ABOVE':  # Resistance
            # Above resistance = high delta (bullish positioning)
            if distance_pct > 0:
                return min(0.70, 0.50 + (distance_pct / 10))
            else:
                return max(0.30, 0.50 + (distance_pct / 10))
        else:  # Support
            if distance_pct < 0:
                return max(0.30, 0.50 + (distance_pct / 10))
            else:
                return min(0.70, 0.50 - (distance_pct / 10))
    
    def check_symbol_greeks(self, symbol: str):
        """Check greeks for symbol and alert on significant changes"""
        try:
            current = self.get_live_greeks(symbol)
            
            if not current:
                return
            
            # Check if we have previous data
            if symbol in self.previous_greeks:
                prev = self.previous_greeks[symbol]
                
                # Calculate delta change
                delta_change = abs(current['delta'] - prev['delta'])
                
                # Alert conditions
                should_alert = False
                alert_type = None
                
                # 1. Large delta swing
                if delta_change >= self.delta_change_threshold:
                    should_alert = True
                    alert_type = 'DELTA_SWING'
                
                # 2. Near gamma wall
                if current['wall_distance_pct'] and current['wall_distance_pct'] < self.gamma_wall_proximity_pct:
                    should_alert = True
                    alert_type = 'GAMMA_WALL_APPROACH'
                
                if should_alert:
                    self._send_greeks_alert(current, prev, alert_type, delta_change)
            
            # Store current as previous
            self.previous_greeks[symbol] = current
            
        except Exception as e:
            self.logger.error(f"Error checking greeks for {symbol}: {str(e)}")
    
    def _send_greeks_alert(self, current: Dict, prev: Dict, alert_type: str, delta_change: float):
        """Send Discord alert for greek changes"""
        if not self.discord:
            return
        
        symbol = current['symbol']
        
        if alert_type == 'DELTA_SWING':
            emoji = '⚡'
            title = f"{emoji} DELTA SWING - {symbol}"
            color = 0xffaa00  # Orange
            
            description = f"Significant delta movement detected"
            
            fields = [
                {
                    'name': '📊 Delta Change',
                    'value': f"**{prev['delta']:.2f} → {current['delta']:.2f}**\nChange: {delta_change:+.2f}",
                    'inline': True
                },
                {
                    'name': '💰 Current Price',
                    'value': f"**${current['price']:.2f}**",
                    'inline': True
                },
                {
                    'name': '🎯 Gamma',
                    'value': f"**{current['gamma']:.3f}**",
                    'inline': True
                }
            ]
            
        else:  # GAMMA_WALL_APPROACH
            emoji = '🔥'
            title = f"{emoji} NEAR GAMMA WALL - {symbol}"
            color = 0xff0000  # Red
            
            wall_type = current['wall_type']
            distance = current['wall_distance_pct']
            
            description = f"Price approaching {wall_type} gamma wall"
            
            fields = [
                {
                    'name': '🎯 Wall Strike',
                    'value': f"**${current['wall_strike']:.2f}** {wall_type}",
                    'inline': True
                },
                {
                    'name': '📍 Distance',
                    'value': f"**{distance:.1f}%** away",
                    'inline': True
                },
                {
                    'name': '💰 Current Price',
                    'value': f"**${current['price']:.2f}**",
                    'inline': True
                },
                {
                    'name': '📊 Delta',
                    'value': f"**{current['delta']:.2f}**",
                    'inline': True
                },
                {
                    'name': '🎯 Gamma',
                    'value': f"**{current['gamma']:.3f}**",
                    'inline': True
                }
            ]
        
        embed = {
            'title': title,
            'description': description,
            'color': color,
            'fields': fields,
            'timestamp': datetime.utcnow().isoformat(),
            'footer': {
                'text': f'Live Greeks Monitor • {datetime.now().strftime("%H:%M:%S ET")}'
            }
        }
        
        try:
            import requests
            webhook_url = self.discord.webhook_momentum_signals  # Reuse momentum channel
            
            response = requests.post(
                webhook_url,
                json={'embeds': [embed]},
                timeout=10
            )
            response.raise_for_status()
            
            self.stats['alerts_sent'] += 1
            self.logger.info(f"✅ Live greeks alert sent: {symbol} - {alert_type}")
            
        except Exception as e:
            self.logger.error(f"Error sending greeks alert: {str(e)}")
    
    def get_statistics(self) -> Dict:
        """Get monitor statistics"""
        return self.stats.copy()
