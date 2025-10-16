"""
Pushover Alerter - Send push notifications to mobile devices
Fixed for your directory structure
"""

import sys
from pathlib import Path

# ========================================
# PATH SETUP - Add backend to Python path
# ========================================
backend_dir = Path(__file__).parent.parent  # Gets to backend/
sys.path.insert(0, str(backend_dir))

import requests
import logging
from typing import Dict, Optional


class PushoverAlerter:
    """
    Sends push notifications via Pushover API
    """
    
    def __init__(self, user_key: str, api_token: str, config: Optional[Dict] = None):
        """
        Initialize Pushover alerter
        
        Args:
            user_key: Pushover user key
            api_token: Pushover API token
            config: Optional configuration dict
        """
        self.user_key = user_key
        self.api_token = api_token
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        self.api_url = "https://api.pushover.net/1/messages.json"
        
        # Sound mappings
        self.sounds = self.config.get('sounds', {
            'strong_buy': 'cashregister',
            'strong_sell': 'alien',
            'momentum_shift': 'intermission',
            'default': 'pushover'
        })
        
        # Priority mappings
        self.priorities = self.config.get('priority', {
            'strong_signals': 1,      # High priority
            'momentum_shift': 1,      # High priority
            'regular_signals': 0      # Normal priority
        })
        
        self.logger.info("Pushover alerter initialized")
    
    def _get_sound(self, alert_type: str) -> str:
        """Get sound for alert type"""
        alert_lower = alert_type.lower().replace(' ', '_')
        return self.sounds.get(alert_lower, self.sounds.get('default', 'pushover'))
    
    def _get_priority(self, alert_type: str) -> int:
        """Get priority level for alert type"""
        if 'STRONG' in alert_type:
            return self.priorities.get('strong_signals', 1)
        elif 'MOMENTUM' in alert_type:
            return self.priorities.get('momentum_shift', 1)
        else:
            return self.priorities.get('regular_signals', 0)
    
    def _format_message(self, analysis: Dict) -> Dict:
        """
        Format analysis into Pushover message
        
        Args:
            analysis: Analysis result
        
        Returns:
            Message dict for Pushover API
        """
        symbol = analysis['symbol']
        alert_type = analysis.get('alert_type', 'MONITOR')
        confidence = analysis.get('confidence', 0)
        price = analysis.get('current_price', 0)
        
        # Title
        title = f"{symbol} - {alert_type}"
        
        # Message body
        message = f"Confidence: {confidence:.1f}%\n"
        message += f"Price: ${price:.2f}\n"
        
        # Add bias
        bias_1h = analysis.get('bias_1h')
        if bias_1h:
            message += f"1H: {bias_1h}\n"
        
        # Add gap if present
        gap_data = analysis.get('gap_data', {})
        if gap_data.get('gap_type') in ['GAP_UP', 'GAP_DOWN']:
            message += f"\nGap {gap_data['gap_type']}: {gap_data['gap_size']}%\n"
        
        # Add news if significant
        news = analysis.get('news', {})
        if news.get('sentiment') not in ['NEUTRAL', None]:
            message += f"\nNews: {news['sentiment']}"
        
        # Add entry targets if available
        entry_targets = analysis.get('entry_targets', {})
        if entry_targets and entry_targets.get('entry'):
            message += f"\n\nEntry: ${entry_targets['entry']:.2f}"
            message += f"\nTP1: ${entry_targets['tp1']:.2f}"
            message += f"\nSL: ${entry_targets['stop_loss']:.2f}"
        
        # Build payload
        payload = {
            'user': self.user_key,
            'token': self.api_token,
            'title': title,
            'message': message,
            'sound': self._get_sound(alert_type),
            'priority': self._get_priority(alert_type),
            'url': f"https://www.tradingview.com/chart/?symbol={symbol}",
            'url_title': f"View {symbol} Chart"
        }
        
        return payload
    
    def send_notification(self, analysis: Dict) -> bool:
        """
        Send push notification
        
        Args:
            analysis: Analysis result dict
        
        Returns:
            True if sent successfully
        """
        try:
            payload = self._format_message(analysis)
            
            response = requests.post(
                self.api_url,
                data=payload,
                timeout=10
            )
            
            response.raise_for_status()
            
            self.logger.info(f"Pushover notification sent: {analysis['symbol']} - {analysis.get('alert_type')}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to send Pushover notification: {str(e)}")
            return False
    
    def send_test_notification(self):
        """Send a test notification to verify setup"""
        test_analysis = {
            'symbol': 'SPY',
            'alert_type': 'TEST ALERT',
            'confidence': 100,
            'current_price': 450.00,
            'bias_1h': 'BULLISH'
        }
        
        return self.send_notification(test_analysis)


# CLI for testing
def main():
    """Command-line interface"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    user_key = os.getenv('PUSHOVER_USER_KEY')
    api_token = os.getenv('PUSHOVER_API_TOKEN')
    
    if not user_key or not api_token:
        print("❌ Error: PUSHOVER_USER_KEY or PUSHOVER_API_TOKEN not found in .env")
        return
    
    alerter = PushoverAlerter(user_key, api_token)
    
    print("Sending test notification to Pushover...")
    
    if alerter.send_test_notification():
        print("✅ Test notification sent successfully!")
        print("Check your device for the notification")
    else:
        print("❌ Failed to send test notification")


if __name__ == '__main__':
    main()