"""
Market Scheduler with Watchlist Integration
Fixed for your project structure
"""

import sys
from pathlib import Path

# ========================================
# PATH SETUP - Add backend to Python path
# ========================================
backend_dir = Path(__file__).parent.parent  # Gets to backend/
sys.path.insert(0, str(backend_dir))

# Now we can import from backend root
from utils.watchlist_manager import WatchlistManager

import pytz
import yaml
from datetime import datetime, time
from typing import List, Dict, Optional
import logging
from collections import defaultdict


class MarketScheduler:
    def __init__(self, config_path: str = None):
        """
        Initialize market scheduler with config
        
        Args:
            config_path: Path to config.yaml file (auto-detected if None)
        """
        self.logger = logging.getLogger(__name__)
        
        # Auto-detect config path if not provided
        if config_path is None:
            # Config is in ../config/config.yaml relative to this file
            config_path = Path(__file__).parent / '../config/config.yaml'
        
        self.config_path = str(config_path)
        self.config = self._load_config(self.config_path)
        
        # Initialize watchlist manager
        watchlist_file = self.config['watchlist']['file']
        
        # If relative path, make it relative to backend directory
        if not Path(watchlist_file).is_absolute():
            watchlist_file = str(backend_dir / watchlist_file)
        
        self.watchlist_manager = WatchlistManager(watchlist_file)
        
        # Set timezone
        self.tz = pytz.timezone(self.config['market_schedule']['timezone'])
        
        # Load market hours
        self.market_hours = self.config['market_schedule']['trading_hours']['monday_friday']
        
        # Parse time ranges
        self.pre_market_start, self.pre_market_end = self._parse_time_range(self.market_hours['pre_market'])
        self.market_open, self.market_close = self._parse_time_range(self.market_hours['market_open'])
        self.after_hours_start, self.after_hours_end = self._parse_time_range(self.market_hours['after_hours'])
        
        self.logger.info(f"Market scheduler initialized (config: {self.config_path})")
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except Exception as e:
            self.logger.error(f"Error loading config: {str(e)}")
            raise
    
    def _parse_time_range(self, time_range: str) -> tuple:
        """Parse time range string like '09:30-16:00' into time objects"""
        start_str, end_str = time_range.split('-')
        start_time = time(*map(int, start_str.split(':')))
        end_time = time(*map(int, end_str.split(':')))
        return start_time, end_time
    
    def get_current_market_state(self) -> str:
        """
        Determine current market state
        
        Returns:
            'market_hours', 'pre_market', 'after_hours', 'weekend', or 'closed'
        """
        now = datetime.now(self.tz)
        current_time = now.time()
        current_day = now.weekday()  # 0=Monday, 6=Sunday
        
        # Weekend
        if current_day >= 5:  # Saturday or Sunday
            return 'weekend'
        
        # Weekday - check time ranges
        if self.market_open <= current_time < self.market_close:
            return 'market_hours'
        elif self.pre_market_start <= current_time < self.pre_market_end:
            return 'pre_market'
        elif self.after_hours_start <= current_time < self.after_hours_end:
            return 'after_hours'
        else:
            return 'closed'
    
    def should_scan_now(self) -> bool:
        """Check if we should run a scan right now"""
        state = self.get_current_market_state()
        
        # Never scan when market is closed (except weekend macro monitoring)
        if state == 'closed':
            return False
        
        return True
    
    def get_scan_interval(self) -> int:
        """
        Get appropriate scan interval based on market state
        
        Returns:
            Interval in seconds
        """
        state = self.get_current_market_state()
        intervals = self.config['market_schedule']['scan_intervals']
        
        interval_map = {
            'market_hours': intervals['market_hours'],
            'pre_market': intervals['pre_market'],
            'after_hours': intervals['after_hours'],
            'weekend': intervals['weekend']
        }
        
        return interval_map.get(state, 300)  # Default 5 minutes
    
    def get_watchlist_for_state(self, state: Optional[str] = None) -> List[str]:
        """
        Get appropriate watchlist based on market state
        Integrates with existing watchlist.txt system
        
        Args:
            state: Market state (if None, will detect automatically)
        
        Returns:
            List of symbols to monitor
        """
        if state is None:
            state = self.get_current_market_state()
        
        # Load all symbols from watchlist.txt
        all_symbols = self.watchlist_manager.load_symbols()
        
        if not all_symbols:
            self.logger.warning("No symbols loaded from watchlist, using defaults")
            return ['SPY', 'QQQ']
        
        # Get filtering config for this state
        filtering_config = self.config['watchlist']['filtering'].get(state, {})
        mode = filtering_config.get('mode', 'all')
        
        self.logger.info(f"Market state: {state} | Mode: {mode} | Total symbols in watchlist: {len(all_symbols)}")
        
        # Apply filtering based on mode
        if mode == 'all':
            # Market hours: use ALL symbols
            result = all_symbols
            
        elif mode == 'priority':
            # After-hours/pre-market: use priority symbols if they exist, otherwise first N
            priority_symbols = filtering_config.get('priority_symbols', [])
            fallback_count = filtering_config.get('fallback_count', 3)
            
            # Check which priority symbols are in the watchlist
            available_priority = [s for s in priority_symbols if s in all_symbols]
            
            if available_priority:
                result = available_priority
                self.logger.info(f"Using {len(result)} priority symbols: {result}")
            else:
                result = all_symbols[:fallback_count]
                self.logger.info(f"No priority symbols found, using first {fallback_count}: {result}")
        
        elif mode == 'specific':
            # Weekend: use only specific symbols
            specific_symbols = filtering_config.get('symbols', ['SPY'])
            
            # Only include if they're in the watchlist
            result = [s for s in specific_symbols if s in all_symbols]
            
            if not result:
                # Fallback to SPY if nothing matches
                result = ['SPY'] if 'SPY' in all_symbols else all_symbols[:1]
            
            self.logger.info(f"Using {len(result)} specific symbols for {state}: {result}")
        
        else:
            # Unknown mode, use all
            self.logger.warning(f"Unknown filter mode '{mode}', using all symbols")
            result = all_symbols
        
        return result
    
    def is_first_scan_time(self) -> bool:
        """
        Check if this is a "first scan" time (e.g., market open, pre-market start)
        Used to trigger immediate scans at key times
        """
        now = datetime.now(self.tz)
        current_time = now.time()
        
        first_scan_config = self.config['market_schedule'].get('first_scan', {})
        
        # Check if we're within 1 minute of a first scan time
        threshold = 60  # seconds
        
        if first_scan_config.get('pre_market_start'):
            if self._is_near_time(current_time, self.pre_market_start, threshold):
                return True
        
        if first_scan_config.get('market_open'):
            if self._is_near_time(current_time, self.market_open, threshold):
                return True
        
        if first_scan_config.get('after_hours_start'):
            if self._is_near_time(current_time, self.after_hours_start, threshold):
                return True
        
        return False
    
    def _is_near_time(self, current: time, target: time, threshold_seconds: int) -> bool:
        """Check if current time is within threshold seconds of target time"""
        # Convert to seconds since midnight
        current_seconds = current.hour * 3600 + current.minute * 60 + current.second
        target_seconds = target.hour * 3600 + target.minute * 60
        
        diff = abs(current_seconds - target_seconds)
        return diff <= threshold_seconds
    
    def get_next_scan_time(self) -> datetime:
        """Calculate when the next scan should occur"""
        now = datetime.now(self.tz)
        interval = self.get_scan_interval()
        
        # Round to nearest interval
        next_scan = now.timestamp() + interval
        next_scan = (next_scan // interval) * interval
        
        return datetime.fromtimestamp(next_scan, tz=self.tz)
    
    def get_schedule_summary(self) -> Dict:
        """Get a summary of the current schedule"""
        state = self.get_current_market_state()
        symbols = self.get_watchlist_for_state(state)
        interval = self.get_scan_interval()
        
        return {
            'market_state': state,
            'should_scan': self.should_scan_now(),
            'scan_interval': interval,
            'symbols_count': len(symbols),
            'symbols': symbols,
            'next_scan': self.get_next_scan_time().strftime('%Y-%m-%d %H:%M:%S %Z'),
            'is_first_scan': self.is_first_scan_time(),
            'backend_dir': str(backend_dir),
            'config_path': self.config_path
        }
    
    def print_schedule(self):
        """Print current schedule information"""
        summary = self.get_schedule_summary()
        
        print("=" * 60)
        print("ALWAYS-ON-TRADER SCHEDULE")
        print("=" * 60)
        print(f"Current Time: {datetime.now(self.tz).strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"Market State: {summary['market_state'].upper()}")
        print(f"Should Scan: {'YES ✅' if summary['should_scan'] else 'NO ❌'}")
        print(f"Scan Interval: {summary['scan_interval']} seconds ({summary['scan_interval']//60} min)")
        print(f"Watching: {summary['symbols_count']} symbols")
        print(f"Symbols: {', '.join(summary['symbols'])}")
        print(f"Next Scan: {summary['next_scan']}")
        print(f"First Scan Priority: {'YES 🚀' if summary['is_first_scan'] else 'NO'}")
        print("=" * 60)
        print(f"Backend Dir: {summary['backend_dir']}")
        print(f"Config: {summary['config_path']}")
        print("=" * 60)


# CLI tool for testing scheduler
def main():
    """Command-line interface for testing scheduler"""
    import sys
    
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        scheduler = MarketScheduler()
    except Exception as e:
        print(f"❌ Error initializing scheduler: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'status':
            scheduler.print_schedule()
        
        elif command == 'symbols':
            state = sys.argv[2] if len(sys.argv) > 2 else None
            symbols = scheduler.get_watchlist_for_state(state)
            print(f"Symbols for {state or 'current'} state:")
            for sym in symbols:
                print(f"  • {sym}")
        
        elif command == 'states':
            print("Testing all market states:")
            for state in ['market_hours', 'pre_market', 'after_hours', 'weekend']:
                symbols = scheduler.get_watchlist_for_state(state)
                print(f"\n{state.upper()}:")
                print(f"  Symbols ({len(symbols)}): {', '.join(symbols)}")
        
        elif command == 'paths':
            print("Current paths:")
            print(f"  Backend: {backend_dir}")
            print(f"  Scheduler: {Path(__file__).parent}")
            print(f"  Config: {scheduler.config_path}")
            print(f"  Watchlist: {scheduler.config['watchlist']['file']}")
        
        else:
            print(f"Unknown command: {command}")
            print()
            print("Usage:")
            print("  python3 market_scheduler.py status   - Show current schedule")
            print("  python3 market_scheduler.py symbols  - Show current symbols")
            print("  python3 market_scheduler.py states   - Test all market states")
            print("  python3 market_scheduler.py paths    - Show all paths")
    
    else:
        # Default: print schedule
        scheduler.print_schedule()


if __name__ == '__main__':
    main()