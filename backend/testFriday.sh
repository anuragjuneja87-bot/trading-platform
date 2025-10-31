curl -s "http://localhost:5001/api/analyze/SPY" | python3 -c "
import json, sys
data = json.load(sys.stdin)
oi = data.get('open_interest', {})
print('=' * 70)
print('DATA SOURCE VERIFICATION')
print('=' * 70)
print(f\"Data Source: {oi.get('data_source', 'MISSING').upper()}\")
print(f\"Available: {oi.get('available', False)}\")
print(f\"Expiration: {oi.get('expiration', 'N/A')}\")
print(f\"0DTE: {oi.get('expires_today', False)}\")
print(f\"Current Price: \${oi.get('current_price', 0):.2f}\")
print(f\"Gamma Walls: {len(oi.get('gamma_walls', []))} detected\")
print(f\"Data Delay: {oi.get('data_delay', 'N/A')}\")
print('=' * 70)
if oi.get('data_source') == 'thetadata':
    print('✅ SUCCESS: Using ThetaData (fastest)')
elif oi.get('data_source') == 'tradier':
    print('⚠️  WARNING: Using Tradier fallback (check ThetaData Terminal)')
else:
    print('❌ ERROR: Unknown data source')
"
```

**Expected Output (GOOD):**
```
======================================================================
DATA SOURCE VERIFICATION
======================================================================
Data Source: THETADATA
Available: True
Expiration: 2025-11-01
0DTE: True
Current Price: $585.23
Gamma Walls: 12 detected
Data Delay: realtime
======================================================================
✅ SUCCESS: Using ThetaData (fastest)
