#!/usr/bin/env python3
"""
Project Structure Detector
Finds all relevant files and shows correct import paths
"""

import os
from pathlib import Path

def find_project_root():
    """Find the trading-platform directory"""
    current = Path.cwd()
    
    # Look for trading-platform in current path
    for parent in [current] + list(current.parents):
        if parent.name == 'trading-platform':
            return parent
    
    # Not found, use current directory
    return current

def find_files(root_dir, patterns):
    """Find files matching patterns"""
    found = {}
    
    for pattern in patterns:
        matches = list(root_dir.rglob(pattern))
        if matches:
            found[pattern] = matches
    
    return found

def main():
    print("=" * 70)
    print("  PROJECT STRUCTURE DETECTOR")
    print("=" * 70)
    print()
    
    # Find root
    root = find_project_root()
    print(f"Project Root: {root}")
    print()
    
    # Files to find
    patterns = [
        'watchlist.txt',
        'watchlist_manager.py',
        'enhanced_professional_analyzer.py',
        'market_scheduler.py',
        'alert_manager.py',
        'discord_alerter.py',
        'pushover_alerter.py',
        'config.yaml',
        '.env'
    ]
    
    # Find all files
    print("Searching for project files...")
    print()
    
    found_files = find_files(root, patterns)
    
    # Display results
    print("=" * 70)
    print("  FOUND FILES")
    print("=" * 70)
    print()
    
    all_paths = {}
    
    for pattern, paths in found_files.items():
        print(f"📄 {pattern}:")
        for path in paths:
            rel_path = path.relative_to(root)
            print(f"   └─ {rel_path}")
            all_paths[pattern] = path
        print()
    
    # Check for missing files
    missing = [p for p in patterns if p not in found_files]
    if missing:
        print("=" * 70)
        print("  MISSING FILES")
        print("=" * 70)
        print()
        for pattern in missing:
            print(f"❌ {pattern}")
        print()
    
    # Determine backend directory
    backend_dir = None
    if 'market_scheduler.py' in all_paths:
        backend_dir = all_paths['market_scheduler.py'].parent.parent
    elif 'config.yaml' in all_paths:
        backend_dir = all_paths['config.yaml'].parent.parent
    
    if backend_dir:
        print("=" * 70)
        print("  RECOMMENDED STRUCTURE")
        print("=" * 70)
        print()
        print(f"Backend Directory: {backend_dir.relative_to(root)}")
        print()
        print("Suggested directory structure:")
        print()
        print(f"{backend_dir.name}/")
        print("├── __init__.py")
        print("├── config/")
        print("│   ├── __init__.py")
        print("│   └── config.yaml")
        print("├── scheduler/")
        print("│   ├── __init__.py")
        print("│   └── market_scheduler.py")
        print("├── alerters/")
        print("│   ├── __init__.py")
        print("│   ├── discord_alerter.py")
        print("│   └── pushover_alerter.py")
        print("├── analyzer/")
        print("│   ├── __init__.py")
        print("│   ├── enhanced_professional_analyzer.py")
        print("│   └── watchlist_manager.py")
        print("├── watchlist.txt")
        print("└── .env")
        print()
    
    # Generate import fix code
    if backend_dir and 'market_scheduler.py' in all_paths:
        print("=" * 70)
        print("  IMPORT FIX CODE")
        print("=" * 70)
        print()
        print("Add this to the TOP of market_scheduler.py:")
        print()
        print("```python")
        print("import sys")
        print("from pathlib import Path")
        print()
        print("# Add backend directory to Python path")
        print(f"backend_dir = Path(__file__).parent.parent  # Gets to {backend_dir.name}/")
        print("sys.path.insert(0, str(backend_dir))")
        print()
        print("# Now imports will work from backend root")
        
        # Determine where watchlist_manager is
        if 'watchlist_manager.py' in all_paths:
            wm_path = all_paths['watchlist_manager.py']
            wm_rel = wm_path.parent.relative_to(backend_dir)
            
            if str(wm_rel) == '.':
                print("from watchlist_manager import WatchlistManager")
            else:
                wm_import = str(wm_rel).replace('/', '.').replace('\\', '.')
                print(f"from {wm_import}.watchlist_manager import WatchlistManager")
        
        print("```")
        print()
    
    # Generate config path fix
    if 'config.yaml' in all_paths and 'market_scheduler.py' in all_paths:
        config_path = all_paths['config.yaml']
        scheduler_path = all_paths['market_scheduler.py']
        
        # Calculate relative path
        rel_config = os.path.relpath(config_path, scheduler_path.parent)
        
        print("=" * 70)
        print("  CONFIG PATH FIX")
        print("=" * 70)
        print()
        print("In market_scheduler.py, update the config path:")
        print()
        print("```python")
        print("# From:")
        print("# self.config = self._load_config('config.yaml')")
        print()
        print("# To:")
        print(f"config_path = Path(__file__).parent / '{rel_config}'")
        print("self.config = self._load_config(str(config_path))")
        print("```")
        print()
    
    # Test commands
    print("=" * 70)
    print("  TEST COMMANDS")
    print("=" * 70)
    print()
    print("Run these to test your imports:")
    print()
    
    if backend_dir:
        print(f"cd {backend_dir}")
        print("export PYTHONPATH=\"$(pwd):$PYTHONPATH\"")
        print()
    
    print("# Test individual imports")
    print("python3 -c 'from watchlist_manager import WatchlistManager; print(\"✅ WatchlistManager\")'")
    print("python3 -c 'import market_scheduler; print(\"✅ market_scheduler\")'")
    print("python3 -c 'import yaml; print(\"✅ yaml\")'")
    print()
    
    if 'market_scheduler.py' in all_paths:
        scheduler_dir = all_paths['market_scheduler.py'].parent
        print(f"# Test scheduler")
        print(f"cd {scheduler_dir}")
        print("python3 market_scheduler.py status")
    
    print()
    print("=" * 70)
    print()


if __name__ == '__main__':
    main()
