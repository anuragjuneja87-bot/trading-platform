python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from analyzers.gex_calculator import GEXCalculator

gex_calc = GEXCalculator()

# Create minimal test data
test_options = [
    {'strike': 670, 'open_interest': 1000, 'gamma': 0.05, 'delta': 0.5, 'option_type': 'call'},
    {'strike': 672, 'open_interest': 2000, 'gamma': 0.08, 'delta': 0.6, 'option_type': 'call'},
    {'strike': 674, 'open_interest': 1500, 'gamma': 0.09, 'delta': 0.4, 'option_type': 'put'},
    {'strike': 676, 'open_interest': 1800, 'gamma': 0.07, 'delta': -0.5, 'option_type': 'put'},
]

print("Testing with minimal synthetic data...")
result = gex_calc.calculate_net_gex('SPY', test_options, 674.0)

print(f"Available: {result.get('available')}")
if result.get('available'):
    print(f"✅ GEX calculator works!")
    print(f"Total GEX: {result.get('total_gex')}")
else:
    print(f"❌ Still fails: {result.get('error')}")
EOF
