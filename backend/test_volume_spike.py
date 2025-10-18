"""
test_volume_spike.py
Quick test script to send synthetic volume spike alerts to Discord
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK = os.getenv('DISCORD_VOLUME_SPIKE')

if not DISCORD_WEBHOOK:
    print("❌ Error: DISCORD_VOLUME_SPIKE not found in .env")
    exit(1)

print("🧪 Testing Volume Spike Alerts with Synthetic Data")
print("=" * 60)

# Test 1: Pre-Market Spike (EXTREME)
print("\n1️⃣ Testing Pre-Market EXTREME Spike...")

premarket_alert = {
    'embeds': [{
        'title': '🔥 NVDA - PRE-MARKET VOLUME SPIKE',
        'description': '**EXTREME** volume detected during extended hours',
        'color': 0xff0000,  # Red
        'fields': [
            {
                'name': '📊 Relative Volume (RVOL)',
                'value': '**5.2x** (EXTREME)',
                'inline': True
            },
            {
                'name': '⏰ Session',
                'value': 'PRE-MARKET',
                'inline': True
            },
            {
                'name': '📦 Current Volume',
                'value': '1.2M shares',
                'inline': True
            },
            {
                'name': '📉 Expected Volume',
                'value': '230K shares',
                'inline': True
            },
            {
                'name': '📈 Volume vs Expected',
                'value': '+426%',
                'inline': True
            },
            {
                'name': '⚠️ Action',
                'value': '**EXTREME volume** - Check for news catalyst!',
                'inline': False
            }
        ],
        'footer': {
            'text': 'Pre-Market Volume Monitor • TEST MODE • Cooldown: 30min'
        }
    }]
}

try:
    response = requests.post(DISCORD_WEBHOOK, json=premarket_alert, timeout=10)
    response.raise_for_status()
    print("   ✅ Pre-market EXTREME alert sent!")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# Test 2: Intraday Spike (HIGH) - Breakout
print("\n2️⃣ Testing Intraday HIGH Spike (BREAKOUT)...")

intraday_breakout = {
    'embeds': [{
        'title': '🔥 AMD - VOLUME SPIKE (REGULAR HOURS) 🚀 BREAKOUT',
        'description': '**HIGH** volume detected - HIGH priority',
        'color': 0xff6600,  # Orange
        'fields': [
            {
                'name': '📊 Volume Metrics',
                'value': '**Spike Ratio:** 4.1x\n**Classification:** HIGH\n**Session:** REGULAR HOURS',
                'inline': True
            },
            {
                'name': '📈 Price Movement',
                'value': '**Change:** +2.3%\n**Direction:** BREAKOUT',
                'inline': True
            },
            {
                'name': '📦 Volume Details',
                'value': '**Current Bar:** 620K\n**Avg (10 bars):** 151K',
                'inline': True
            },
            {
                'name': '🎯 Action Items',
                'value': '⚠️ **HIGH PRIORITY**\n✅ Monitor in Bookmap\n✅ Prepare for entry\n✅ Check for news',
                'inline': False
            }
        ],
        'footer': {
            'text': 'Volume Spike Monitor • TEST MODE • 09:45:23 ET'
        }
    }]
}

try:
    response = requests.post(DISCORD_WEBHOOK, json=intraday_breakout, timeout=10)
    response.raise_for_status()
    print("   ✅ Intraday BREAKOUT alert sent!")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# Test 3: Intraday Spike (ELEVATED) - Breakdown
print("\n3️⃣ Testing Intraday ELEVATED Spike (BREAKDOWN)...")

intraday_breakdown = {
    'embeds': [{
        'title': '🔥 TSLA - VOLUME SPIKE (REGULAR HOURS) ⬇️ BREAKDOWN',
        'description': '**ELEVATED** volume detected - MEDIUM priority',
        'color': 0xffff00,  # Yellow
        'fields': [
            {
                'name': '📊 Volume Metrics',
                'value': '**Spike Ratio:** 2.8x\n**Classification:** ELEVATED\n**Session:** REGULAR HOURS',
                'inline': True
            },
            {
                'name': '📉 Price Movement',
                'value': '**Change:** -1.5%\n**Direction:** BREAKDOWN',
                'inline': True
            },
            {
                'name': '📦 Volume Details',
                'value': '**Current Bar:** 385K\n**Avg (10 bars):** 137K',
                'inline': True
            },
            {
                'name': '🎯 Action Items',
                'value': '👀 **WATCH CLOSELY**\n✅ Add to watchlist\n✅ Monitor for continuation',
                'inline': False
            }
        ],
        'footer': {
            'text': 'Volume Spike Monitor • TEST MODE • 10:23:15 ET'
        }
    }]
}

try:
    response = requests.post(DISCORD_WEBHOOK, json=intraday_breakdown, timeout=10)
    response.raise_for_status()
    print("   ✅ Intraday BREAKDOWN alert sent!")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# Test 4: After-Hours Spike
print("\n4️⃣ Testing After-Hours HIGH Spike...")

afterhours_alert = {
    'embeds': [{
        'title': '📈 AAPL - AFTER-HOURS VOLUME SPIKE',
        'description': '**HIGH** volume detected during extended hours',
        'color': 0xff6600,  # Orange
        'fields': [
            {
                'name': '📊 Relative Volume (RVOL)',
                'value': '**3.7x** (HIGH)',
                'inline': True
            },
            {
                'name': '⏰ Session',
                'value': 'AFTER-HOURS',
                'inline': True
            },
            {
                'name': '📦 Current Volume',
                'value': '680K shares',
                'inline': True
            },
            {
                'name': '📉 Expected Volume',
                'value': '184K shares',
                'inline': True
            },
            {
                'name': '📈 Volume vs Expected',
                'value': '+270%',
                'inline': True
            },
            {
                'name': '👀 Action',
                'value': 'Significant volume - Monitor for entry opportunity',
                'inline': False
            }
        ],
        'footer': {
            'text': 'Pre-Market Volume Monitor • TEST MODE • 17:15:42 ET'
        }
    }]
}

try:
    response = requests.post(DISCORD_WEBHOOK, json=afterhours_alert, timeout=10)
    response.raise_for_status()
    print("   ✅ After-hours alert sent!")
except Exception as e:
    print(f"   ❌ Failed: {e}")

print("\n" + "=" * 60)
print("✅ Test Complete! Check your Discord channel.")
print("=" * 60)
print("\n📱 You should see 4 alerts:")
print("   1. NVDA - Pre-market EXTREME (red)")
print("   2. AMD - Intraday BREAKOUT (orange)")
print("   3. TSLA - Intraday BREAKDOWN (yellow)")
print("   4. AAPL - After-hours HIGH (orange)")
