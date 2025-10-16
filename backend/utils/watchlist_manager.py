"""
Watchlist Manager - Load and manage trading symbols
"""
from pathlib import Path
from typing import List
import logging

logger = logging.getLogger(__name__)

class WatchlistManager:
    def __init__(self, watchlist_file: str = 'backend/data/watchlist.txt'):
        """
        Initialize watchlist manager
        
        Args:
            watchlist_file: Path to watchlist file
        """
        self.watchlist_file = Path(watchlist_file)
        
        # Create default watchlist if doesn't exist
        if not self.watchlist_file.exists():
            self._create_default_watchlist()
    
    def _create_default_watchlist(self):
        """Create default watchlist.txt file"""
        default_symbols = [
            "# Trading Watchlist",
            "# Add one symbol per line",
            "# Lines starting with # are comments",
            "",
            "# Indices",
            "SPY",
            "QQQ",
            "",
            "# Big Tech",
            "NVDA",
            "TSLA",
            "AAPL",
            "",
            "# AI/Tech Growth",
            "PLTR",
            "ORCL",
            "",
            "# Add your symbols below:",
            ""
        ]
        
        # Ensure directory exists
        self.watchlist_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.watchlist_file, 'w') as f:
            f.write('\n'.join(default_symbols))
        
        logger.info(f"Created default watchlist: {self.watchlist_file}")
    
    def load_symbols(self) -> List[str]:
        """
        Load symbols from watchlist file
        
        Returns:
            List of uppercase symbol strings
        """
        symbols = []
        
        try:
            with open(self.watchlist_file, 'r') as f:
                for line in f:
                    # Remove whitespace
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    # Extract symbol (first word, uppercase)
                    symbol = line.split()[0].upper()
                    
                    # Validate symbol (basic check)
                    if symbol.isalpha() and len(symbol) <= 5:
                        symbols.append(symbol)
            
            if not symbols:
                logger.warning("No symbols found in watchlist, using defaults")
                return ['SPY', 'QQQ', 'NVDA', 'TSLA', 'AAPL', 'PLTR', 'ORCL']
            
            logger.info(f"Loaded {len(symbols)} symbols from watchlist")
            return symbols
            
        except Exception as e:
            logger.error(f"Error loading watchlist: {str(e)}")
            return ['SPY', 'QQQ', 'NVDA', 'TSLA', 'AAPL', 'PLTR', 'ORCL']
    
    def add_symbol(self, symbol: str) -> bool:
        """
        Add a symbol to watchlist
        
        Args:
            symbol: Symbol to add
        
        Returns:
            True if added successfully
        """
        symbol = symbol.upper().strip()
        
        # Check if already exists
        current_symbols = self.load_symbols()
        if symbol in current_symbols:
            logger.info(f"{symbol} already in watchlist")
            return False
        
        # Append to file
        try:
            with open(self.watchlist_file, 'a') as f:
                f.write(f"\n{symbol}")
            
            logger.info(f"Added {symbol} to watchlist")
            return True
            
        except Exception as e:
            logger.error(f"Error adding symbol: {str(e)}")
            return False
    
    def remove_symbol(self, symbol: str) -> bool:
        """
        Remove a symbol from watchlist
        
        Args:
            symbol: Symbol to remove
        
        Returns:
            True if removed successfully
        """
        symbol = symbol.upper().strip()
        
        try:
            # Read all lines
            with open(self.watchlist_file, 'r') as f:
                lines = f.readlines()
            
            # Filter out the symbol
            new_lines = []
            removed = False
            
            for line in lines:
                line_symbol = line.strip().split()[0].upper() if line.strip() and not line.strip().startswith('#') else ''
                
                if line_symbol == symbol:
                    removed = True
                    continue
                
                new_lines.append(line)
            
            # Write back
            if removed:
                with open(self.watchlist_file, 'w') as f:
                    f.writelines(new_lines)
                
                logger.info(f"Removed {symbol} from watchlist")
                return True
            else:
                logger.info(f"{symbol} not found in watchlist")
                return False
                
        except Exception as e:
            logger.error(f"Error removing symbol: {str(e)}")
            return False

# Global instance
watchlist_manager = WatchlistManager()