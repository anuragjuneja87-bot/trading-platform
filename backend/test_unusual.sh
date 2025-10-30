# Load .env file first, then run
source .env && curl -X POST "$DISCORD_UNUSUAL_ACTIVITY" \
  -H "Content-Type: application/json" \
  -d '{
    "embeds": [{
      "title": "🔥⚡ UNUSUAL ACTIVITY - NVDA • 🎯 PRIME HOURS",
      "description": "**HIGH PRIORITY** • Score: 7.2/10 ⭐",
      "color": 16737280,
      "timestamp": "2025-10-29T14:30:00.000Z",
      "fields": [
        {
          "name": "📍 Strike & Type",
          "value": "**Strike:** $150 CALL\n**Classification:** BULLISH BUYING\n**Score:** 7.2/10",
          "inline": true
        },
        {
          "name": "📊 Open Interest",
          "value": "**Current OI:** 8,543\n**Change:** +1,234 (+16.9%)\n**Status:** INCREASING 📈",
          "inline": true
        },
        {
          "name": "📦 Volume Activity",
          "value": "**Current Volume:** 2,450\n**Average Volume:** 850\n**Ratio:** 2.9x 🔥🔥",
          "inline": true
        },
        {
          "name": "💰 Premium Swept",
          "value": "**Total:** $367K 💰💰\n**Last Price:** $1.50\n**Contracts:** 2,450",
          "inline": true
        }
      ],
      "footer": {
        "text": "Unusual Activity Monitor v2.0 • Professional mode • Score: 7.2/10"
      }
    }]
  }'
