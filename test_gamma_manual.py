import sys
sys.path.insert(0, 'backend')

from analyzers.enhanced_professional_analyzer import EnhancedProfessionalAnalyzer
from alerts.alert_manager import AlertManager
from dotenv import load_dotenv
import os

load_dotenv()

# Initialize
analyzer = EnhancedProfessionalAnalyzer(api_key=os.getenv('POLYGON_API_KEY'))
alert_manager = AlertManager()

# Test with a few symbols
test_symbols = ['SPY', 'QQQ', 'NVDA', 'TSLA', 'AAPL']

print("🎯 Generating 0DTE Report...\n")

for symbol in test_symbols:
    print(f"Analyzing {symbol}...")
    result = analyzer.generate_professional_signal(symbol)
    
    if result.get('gamma_walls'):
        gamma = result['gamma_walls']
        price = result['current_price']
        
        print(f"  Current: ${price:.2f}")
        print(f"  Put Wall: ${gamma.get('put_wall', 0):.2f}")
        print(f"  Call Wall: ${gamma.get('call_wall', 0):.2f}")
        print(f"  Max Pain: ${gamma.get('max_pain', 0):.2f}")
        
        # Check if near any wall
        walls = [gamma.get('put_wall', 0), gamma.get('call_wall', 0)]
        for wall in walls:
            if wall > 0:
                distance_pct = abs(price - wall) / price * 100
                if 1.0 <= distance_pct <= 2.0:
                    print(f"  ⚠️ NEAR GAMMA WALL! Distance: {distance_pct:.2f}%")
    print()
