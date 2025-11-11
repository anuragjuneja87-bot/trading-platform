#!/bin/bash

echo "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "="
echo "🧪 TESTING RS/OR MONITOR SETUP"
echo "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "="

echo ""
echo "📊 Testing NVDA analysis..."
curl -s http://localhost:5001/api/analyze/NVDA | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"Symbol: {data.get('symbol')}\\nRS vs SPY: {data.get('rs_spy', 'MISSING')}\\nRS vs QQQ: {data.get('rs_qqq', 'MISSING')}\\nPrice: \${data.get('current_price', 0):.2f}\")"

echo ""
echo "📊 Testing SPY analysis..."
curl -s http://localhost:5001/api/analyze/SPY | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"Symbol: {data.get('symbol')}\\nRS vs SPY: {data.get('rs_spy', 'MISSING')} (should be 0)\\nRS vs QQQ: {data.get('rs_qqq', 'MISSING')}\")"

echo ""
echo "✅ Test complete!"
echo "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "="
