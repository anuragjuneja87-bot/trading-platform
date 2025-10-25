import sys
from pathlib import Path
print(f"Current directory: {Path.cwd()}")
print(f"Python path: {sys.path[:3]}")

# Check if files exist
print("\nChecking files:")
print(f"analyzers/ exists: {Path('analyzers').exists()}")
print(f"Files in analyzers/:")
for f in Path('analyzers').glob('*.py'):
    print(f"  - {f.name}")
