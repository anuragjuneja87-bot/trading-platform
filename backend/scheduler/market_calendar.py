"""
Market Calendar - Trading Hours and Holidays
Fixed for your directory structure
"""

import sys
from pathlib import Path

# ========================================
# PATH SETUP - Add backend to Python path
# ========================================
backend_dir = Path(__file__).parent.parent  # Gets to backend/
sys.path.insert(0, str(backend_dir))

import pytz
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional
import logging


class MarketCalendar:
    """
    Manages market hours, holidays, and trading sessions
    """
    
    def __init__(self, timezone: str = "America/New_York"):
        """
        Initialize market calendar
        
        Args:
            timezone: Market timezone (default: America/New_York)
        """
        self.logger = logging.getLogger(__name__)
        self.tz = pytz.timezone(timezone)
        
        # Standard market hours (ET)
        self.pre_market_start = time(4, 0)   # 4:00 AM
        self.pre_market_end = time(9, 30)    # 9:30 AM
        self.market_open = time(9, 30)       # 9:30 AM
        self.market_close = time(16, 0)      # 4:00 PM
        self.after_hours_start = time(16, 0) # 4:00 PM
        self.after_hours_end = time(20, 0)   # 8:00 PM
        
        # Market holidays (2024-2025)
        self.holidays = [
            # 2024
            datetime(2024, 1, 1),   # New Year's Day
            datetime(2024, 1, 15),  # MLK Day
            datetime(2024, 2, 19),  # Presidents Day
            datetime(2024, 3, 29),  # Good Friday
            datetime(2024, 5, 27),  # Memorial Day
            datetime(2024, 6, 19),  # Juneteenth
            datetime(2024, 7, 4),   # Independence Day
            datetime(2024, 9, 2),   # Labor Day
            datetime(2024, 11, 28), # Thanksgiving
            datetime(2024, 12, 25), # Christmas
            
            # 2025
            datetime(2025, 1, 1),   # New Year's Day
            datetime(2025, 1, 20),  # MLK Day
            datetime(2025, 2, 17),  # Presidents Day
            datetime(2025, 4, 18),  # Good Friday
            datetime(2025, 5, 26),  # Memorial Day
            datetime(2025, 6, 19),  # Juneteenth
            datetime(2025, 7, 4),   # Independence Day
            datetime(2025, 9, 1),   # Labor Day
            datetime(2025, 11, 27), # Thanksgiving
            datetime(2025, 12, 25), # Christmas
        ]
        
        # Early close days (1:00 PM close)
        self.early_close_days = [
            # Day before Independence Day (if weekday)
            datetime(2024, 7, 3),
            datetime(2025, 7, 3),
            
            # Day after Thanksgiving
            datetime(2024, 11, 29),
            datetime(2025, 11, 28),
            
            # Christmas Eve (if weekday)
            datetime(2024, 12, 24),
            datetime(2025, 12, 24),
        ]
        
        self.logger.info("Market calendar initialized")
    
    def is_market_holiday(self, date: Optional[datetime] = None) -> bool:
        """
        Check if a date is a market holiday
        
        Args:
            date: Date to check (defaults to today)
        
        Returns:
            True if market is closed for holiday
        """
        if date is None:
            date = datetime.now(self.tz)
        
        # Check if date matches any holiday
        check_date = date.date() if isinstance(date, datetime) else date
        
        for holiday in self.holidays:
            if holiday.date() == check_date:
                return True
        
        return False
    
    def is_early_close_day(self, date: Optional[datetime] = None) -> bool:
        """
        Check if a date has early market close (1:00 PM)
        
        Args:
            date: Date to check (defaults to today)
        
        Returns:
            True if market closes early
        """
        if date is None:
            date = datetime.now(self.tz)
        
        check_date = date.date() if isinstance(date, datetime) else date
        
        for early_day in self.early_close_days:
            if early_day.date() == check_date:
                return True
        
        return False
    
    def is_trading_day(self, date: Optional[datetime] = None) -> bool:
        """
        Check if a date is a valid trading day
        
        Args:
            date: Date to check (defaults to today)
        
        Returns:
            True if market is open for trading
        """
        if date is None:
            date = datetime.now(self.tz)
        
        # Check if weekend
        if date.weekday() >= 5:  # Saturday or Sunday
            return False
        
        # Check if holiday
        if self.is_market_holiday(date):
            return False
        
        return True
    
    def get_market_hours(self, date: Optional[datetime] = None) -> Dict:
        """
        Get market hours for a specific date
        
        Args:
            date: Date to check (defaults to today)
        
        Returns:
            Dictionary with market hours or None if closed
        """
        if date is None:
            date = datetime.now(self.tz)
        
        # Not a trading day
        if not self.is_trading_day(date):
            return {
                'date': date.date(),
                'trading_day': False,
                'pre_market_start': None,
                'market_open': None,
                'market_close': None,
                'after_hours_end': None
            }
        
        # Check if early close
        if self.is_early_close_day(date):
            close_time = time(13, 0)  # 1:00 PM
        else:
            close_time = self.market_close
        
        return {
            'date': date.date(),
            'trading_day': True,
            'pre_market_start': self.pre_market_start,
            'market_open': self.market_open,
            'market_close': close_time,
            'after_hours_end': self.after_hours_end,
            'early_close': self.is_early_close_day(date)
        }
    
    def get_current_session(self) -> str:
        """
        Get current trading session
        
        Returns:
            'pre_market', 'market_hours', 'after_hours', 'closed', or 'holiday'
        """
        now = datetime.now(self.tz)
        current_time = now.time()
        
        # Check if holiday
        if self.is_market_holiday(now):
            return 'holiday'
        
        # Check if weekend
        if now.weekday() >= 5:
            return 'closed'
        
        # Check time ranges
        if self.pre_market_start <= current_time < self.pre_market_end:
            return 'pre_market'
        elif self.market_open <= current_time < self.market_close:
            return 'market_hours'
        elif self.after_hours_start <= current_time < self.after_hours_end:
            return 'after_hours'
        else:
            return 'closed'
    
    def get_next_market_open(self) -> datetime:
        """
        Get the next market open time
        
        Returns:
            DateTime of next market open
        """
        now = datetime.now(self.tz)
        current_session = self.get_current_session()
        
        # If currently in pre-market or market hours, next open is today
        if current_session in ['pre_market', 'market_hours']:
            return now.replace(hour=9, minute=30, second=0, microsecond=0)
        
        # Otherwise find next trading day
        check_date = now + timedelta(days=1)
        
        while not self.is_trading_day(check_date):
            check_date += timedelta(days=1)
        
        # Return market open time for that day
        return check_date.replace(hour=9, minute=30, second=0, microsecond=0)
    
    def get_next_market_close(self) -> datetime:
        """
        Get the next market close time
        
        Returns:
            DateTime of next market close
        """
        now = datetime.now(self.tz)
        
        # If market is currently open, return today's close
        if self.get_current_session() == 'market_hours':
            hours = self.get_market_hours(now)
            close_time = hours['market_close']
            return now.replace(
                hour=close_time.hour,
                minute=close_time.minute,
                second=0,
                microsecond=0
            )
        
        # Otherwise find next trading day's close
        next_open = self.get_next_market_open()
        hours = self.get_market_hours(next_open)
        close_time = hours['market_close']
        
        return next_open.replace(
            hour=close_time.hour,
            minute=close_time.minute,
            second=0,
            microsecond=0
        )
    
    def get_session_info(self) -> Dict:
        """
        Get detailed information about current session
        
        Returns:
            Dictionary with session details
        """
        now = datetime.now(self.tz)
        session = self.get_current_session()
        hours = self.get_market_hours(now)
        
        return {
            'current_time': now,
            'session': session,
            'trading_day': hours['trading_day'],
            'is_holiday': self.is_market_holiday(now),
            'is_early_close': self.is_early_close_day(now),
            'market_hours': hours,
            'next_market_open': self.get_next_market_open(),
            'next_market_close': self.get_next_market_close()
        }
    
    def print_session_info(self):
        """Print current session information"""
        info = self.get_session_info()
        
        print("=" * 60)
        print("MARKET CALENDAR")
        print("=" * 60)
        print(f"Current Time: {info['current_time'].strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"Session: {info['session'].upper()}")
        print(f"Trading Day: {'YES ✅' if info['trading_day'] else 'NO ❌'}")
        
        if info['is_holiday']:
            print(f"Holiday: YES 🏖️")
        
        if info['is_early_close']:
            print(f"Early Close: YES (1:00 PM) ⚠️")
        
        print()
        print("Market Hours Today:")
        hours = info['market_hours']
        if hours['trading_day']:
            print(f"  Pre-Market: {hours['pre_market_start'].strftime('%H:%M')}")
            print(f"  Market Open: {hours['market_open'].strftime('%H:%M')}")
            print(f"  Market Close: {hours['market_close'].strftime('%H:%M')}")
            print(f"  After Hours End: {hours['after_hours_end'].strftime('%H:%M')}")
        else:
            print(f"  Market Closed")
        
        print()
        print(f"Next Market Open: {info['next_market_open'].strftime('%Y-%m-%d %H:%M')}")
        print(f"Next Market Close: {info['next_market_close'].strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)


# CLI for testing
def main():
    """Command-line interface"""
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(message)s'
    )
    
    calendar = MarketCalendar()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'info':
            calendar.print_session_info()
        
        elif command == 'session':
            session = calendar.get_current_session()
            print(f"Current session: {session}")
        
        elif command == 'holiday':
            is_holiday = calendar.is_market_holiday()
            print(f"Is today a holiday? {'YES' if is_holiday else 'NO'}")
        
        elif command == 'trading':
            is_trading = calendar.is_trading_day()
            print(f"Is today a trading day? {'YES' if is_trading else 'NO'}")
        
        else:
            print(f"Unknown command: {command}")
            print()
            print("Usage:")
            print("  python3 market_calendar.py info     - Show detailed info")
            print("  python3 market_calendar.py session  - Show current session")
            print("  python3 market_calendar.py holiday  - Check if today is holiday")
            print("  python3 market_calendar.py trading  - Check if today is trading day")
    
    else:
        # Default: show info
        calendar.print_session_info()


if __name__ == '__main__':
    main()
