"""
Earnings State Manager
Manages earnings monitoring state and symbol list
Save as: backend/utils/earnings_state_manager.py
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict


class EarningsStateManager:
    def __init__(self, data_dir: str = None):
        """
        Initialize Earnings State Manager
        
        Args:
            data_dir: Path to data directory (default: backend/data)
        """
        self.logger = logging.getLogger(__name__)
        
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / 'data'
        
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.state_file = self.data_dir / 'earnings_state.json'
        self.watchlist_file = self.data_dir / 'earnings_watchlist.json'
        
        self.state = self._load_state()
        self.earnings_symbols = self._load_earnings_watchlist()
    
    def _load_state(self) -> Dict:
        """Load earnings monitoring state"""
        default_state = {
            'enabled': True,
            'week_number': datetime.now().isocalendar()[1],
            'last_updated': datetime.now().isoformat(),
            'disabled_by_user': False
        }
        
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                
                # Auto-reset on new week
                current_week = datetime.now().isocalendar()[1]
                if state.get('week_number') != current_week:
                    self.logger.info(f"📅 New week detected: {current_week}. Resetting earnings monitoring to ENABLED")
                    state['enabled'] = True
                    state['week_number'] = current_week
                    state['disabled_by_user'] = False
                    self._save_state(state)
                
                return state
            except Exception as e:
                self.logger.error(f"Error loading state: {str(e)}")
                return default_state
        
        self._save_state(default_state)
        return default_state
    
    def _save_state(self, state: Dict):
        """Save state to file"""
        try:
            state['last_updated'] = datetime.now().isoformat()
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            self.logger.debug(f"State saved: enabled={state['enabled']}, week={state['week_number']}")
        except Exception as e:
            self.logger.error(f"Error saving state: {str(e)}")
    
    def _load_earnings_watchlist(self) -> List[str]:
        """Load earnings watchlist"""
        if self.watchlist_file.exists():
            try:
                with open(self.watchlist_file, 'r') as f:
                    data = json.load(f)
                symbols = data.get('symbols', [])
                self.logger.info(f"📊 Loaded {len(symbols)} earnings symbols")
                return symbols
            except Exception as e:
                self.logger.error(f"Error loading earnings watchlist: {str(e)}")
                return []
        return []
    
    def _save_earnings_watchlist(self, symbols: List[str], week_data: Dict = None):
        """Save earnings watchlist"""
        try:
            data = {
                'symbols': symbols,
                'week_number': datetime.now().isocalendar()[1],
                'last_updated': datetime.now().isoformat(),
                'source': 'sunday_routine'
            }
            
            if week_data:
                data['week_data'] = week_data
            
            with open(self.watchlist_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.logger.info(f"✅ Saved {len(symbols)} earnings symbols for the week")
        except Exception as e:
            self.logger.error(f"Error saving earnings watchlist: {str(e)}")
    
    def is_enabled(self) -> bool:
        """Check if earnings monitoring is enabled"""
        return self.state.get('enabled', True)
    
    def enable(self):
        """Enable earnings monitoring"""
        self.state['enabled'] = True
        self.state['disabled_by_user'] = False
        self._save_state(self.state)
        self.logger.info("✅ Earnings monitoring ENABLED")
    
    def disable(self):
        """Disable earnings monitoring for this week"""
        self.state['enabled'] = False
        self.state['disabled_by_user'] = True
        self._save_state(self.state)
        self.logger.info("🔕 Earnings monitoring DISABLED for this week")
    
    def get_earnings_symbols(self) -> List[str]:
        """Get list of symbols to monitor for earnings"""
        return self.earnings_symbols
    
    def update_earnings_symbols(self, symbols: List[str], week_data: Dict = None):
        """
        Update the earnings watchlist (called by Sunday routine)
        
        Args:
            symbols: List of symbols with earnings this week + next week
            week_data: Optional metadata about the week's earnings
        """
        self.earnings_symbols = symbols
        self._save_earnings_watchlist(symbols, week_data)
        self.logger.info(f"📅 Updated earnings watchlist: {len(symbols)} symbols")
    
    def get_status(self) -> Dict:
        """Get current status"""
        return {
            'enabled': self.is_enabled(),
            'symbols_count': len(self.earnings_symbols),
            'symbols': self.earnings_symbols,
            'week_number': self.state.get('week_number'),
            'disabled_by_user': self.state.get('disabled_by_user', False),
            'last_updated': self.state.get('last_updated')
        }
    
    def get_combined_symbols(self, trading_watchlist: List[str]) -> List[str]:
        """
        Get combined list of symbols (trading watchlist + earnings symbols)
        
        Args:
            trading_watchlist: Regular trading watchlist
        
        Returns:
            Unique list of all symbols to monitor
        """
        if not self.is_enabled():
            # If earnings disabled, only return trading watchlist
            return trading_watchlist
        
        # Combine and deduplicate
        combined = list(set(trading_watchlist + self.earnings_symbols))
        self.logger.debug(
            f"Combined watchlist: {len(trading_watchlist)} trading + "
            f"{len(self.earnings_symbols)} earnings = {len(combined)} total"
        )
        return combined


# CLI for testing
def main():
    """Command-line interface for testing"""
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    manager = EarningsStateManager()
    
    if len(sys.argv) < 2:
        print("\nEarnings State Manager")
        print("=" * 60)
        print("\nUsage:")
        print("  python earnings_state_manager.py status    - Show current status")
        print("  python earnings_state_manager.py enable    - Enable earnings monitoring")
        print("  python earnings_state_manager.py disable   - Disable earnings monitoring")
        print("  python earnings_state_manager.py symbols   - List earnings symbols")
        print("  python earnings_state_manager.py test      - Test with sample data")
        return
    
    command = sys.argv[1].lower()
    
    if command == 'status':
        status = manager.get_status()
        print("\n" + "=" * 60)
        print("EARNINGS MONITORING STATUS")
        print("=" * 60)
        print(f"Enabled: {'✅ YES' if status['enabled'] else '🔕 NO'}")
        print(f"Week Number: {status['week_number']}")
        print(f"Symbols Count: {status['symbols_count']}")
        print(f"Disabled by User: {status['disabled_by_user']}")
        print(f"Last Updated: {status['last_updated']}")
        if status['symbols']:
            print(f"\nSymbols: {', '.join(status['symbols'][:10])}")
            if len(status['symbols']) > 10:
                print(f"  ... and {len(status['symbols']) - 10} more")
        print("=" * 60)
    
    elif command == 'enable':
        manager.enable()
        print("✅ Earnings monitoring enabled")
    
    elif command == 'disable':
        manager.disable()
        print("🔕 Earnings monitoring disabled for this week")
    
    elif command == 'symbols':
        symbols = manager.get_earnings_symbols()
        print(f"\n📊 Earnings Symbols ({len(symbols)}):")
        for symbol in symbols:
            print(f"  • {symbol}")
    
    elif command == 'test':
        # Test with sample data
        test_symbols = ['JPM', 'WFC', 'NFLX', 'TSLA', 'GOOGL', 'MSFT', 'META', 'AAPL']
        manager.update_earnings_symbols(test_symbols, {
            'week': datetime.now().isocalendar()[1],
            'description': 'Test earnings week'
        })
        print(f"✅ Updated earnings watchlist with {len(test_symbols)} test symbols")
        print(f"Symbols: {', '.join(test_symbols)}")
    
    else:
        print(f"❌ Unknown command: {command}")


if __name__ == '__main__':
    main()
