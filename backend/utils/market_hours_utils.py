"""
utils/market_hours_utils.py
Market hours detection utility
"""

from datetime import datetime
import pytz

def is_market_hours(include_extended=False):
    """
    Check if currently in market hours
    
    Args:
        include_extended: If True, includes pre-market (4:00 AM) and after-hours (8:00 PM)
    
    Returns:
        bool: True if in market hours
    """
    et = pytz.timezone('America/New_York')
    now = datetime.now(et)
    
    # Skip weekends (Saturday=5, Sunday=6)
    if now.weekday() >= 5:
        return False
    
    if include_extended:
        # Extended hours: 4:00 AM - 8:00 PM ET
        market_open = now.replace(hour=4, minute=0, second=0, microsecond=0)
        market_close = now.replace(hour=20, minute=0, second=0, microsecond=0)
    else:
        # Regular hours: 9:30 AM - 4:00 PM ET
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    
    return market_open <= now <= market_close


def get_market_status():
    """
    Get detailed market status
    
    Returns:
        dict: Market status information
    """
    et = pytz.timezone('America/New_York')
    now = datetime.now(et)
    
    weekday = now.weekday()
    
    if weekday >= 5:
        return {
            'status': 'WEEKEND',
            'is_open': False,
            'session': 'CLOSED',
            'message': f"Markets closed - {now.strftime('%A')}"
        }
    
    # Check regular market hours
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    
    # Check extended hours
    premarket_open = now.replace(hour=4, minute=0, second=0, microsecond=0)
    afterhours_close = now.replace(hour=20, minute=0, second=0, microsecond=0)
    
    if now < premarket_open:
        return {
            'status': 'CLOSED',
            'is_open': False,
            'session': 'OVERNIGHT',
            'message': 'Before pre-market'
        }
    elif premarket_open <= now < market_open:
        return {
            'status': 'PREMARKET',
            'is_open': True,
            'session': 'PREMARKET',
            'message': 'Pre-market hours'
        }
    elif market_open <= now < market_close:
        return {
            'status': 'OPEN',
            'is_open': True,
            'session': 'REGULAR',
            'message': 'Regular trading hours'
        }
    elif market_close <= now < afterhours_close:
        return {
            'status': 'AFTERHOURS',
            'is_open': True,
            'session': 'AFTERHOURS',
            'message': 'After-hours trading'
        }
    else:
        return {
            'status': 'CLOSED',
            'is_open': False,
            'session': 'OVERNIGHT',
            'message': 'After extended hours'
        }


def should_fetch_options_data():
    """
    Determine if options data should be fetched
    Options data is only useful during extended hours (4 AM - 8 PM ET) on weekdays
    
    Returns:
        bool: True if options data should be fetched
    """
    return is_market_hours(include_extended=True)
