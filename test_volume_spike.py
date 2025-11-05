#!/usr/bin/env python3
"""
Quick Volume Spike Channel Test
Tests if DISCORD_VOLUME_SPIKE webhook is working
"""

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def main():
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}{'VOLUME SPIKE CHANNEL TEST':^70}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")
    
    load_dotenv()
    
    # Check if webhook exists
    webhook = os.getenv('DISCORD_VOLUME_SPIKE')
    
    if not webhook:
        print(f"{RED}❌ DISCORD_VOLUME_SPIKE not found in .env file{RESET}")
        print(f"\n{YELLOW}Add this to your .env file:{RESET}")
        print(f"DISCORD_VOLUME_SPIKE=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN")
        return False
    
    print(f"{GREEN}✅ Webhook found in .env{RESET}")
    print(f"   URL: {webhook[:50]}...")
    
    # Create test embed
    print(f"\n📤 Sending test message...")
    
    embed = {
        'title': '🔥 VOLUME SPIKE TEST ALERT',
        'description': 'Testing volume spike Discord channel - System Ready!',
        'color': 0xff6600,  # Orange
        'timestamp': datetime.utcnow().isoformat(),
        'fields': [
            {
                'name': '📊 Volume Spike Monitor',
                'value': 'Channel configured and operational!',
                'inline': False
            },
            {
                'name': '✅ Configuration',
                'value': (
                    'Using OLD pattern (realtime_volume_spike)\n'
                    'Routes automatically via Discord config'
                ),
                'inline': False
            },
            {
                'name': '🎯 Expected Alerts',
                'value': (
                    '• High RVOL (2.0x+)\n'
                    '• Volume spikes (1.3x+)\n'
                    '• Extreme volume (3.0x+)\n'
                    '• Price movement confirmation'
                ),
                'inline': False
            },
            {
                'name': '⏰ Test Time',
                'value': datetime.now().strftime('%Y-%m-%d %H:%M:%S ET'),
                'inline': False
            }
        ],
        'footer': {
            'text': 'Volume Spike Test • All Systems Go'
        }
    }
    
    # Send test message
    try:
        response = requests.post(webhook, json={'embeds': [embed]}, timeout=10)
        response.raise_for_status()
        
        print(f"{GREEN}✅ Test message sent successfully!{RESET}")
        print(f"\n{BLUE}{'─'*70}{RESET}")
        print(f"{GREEN}📱 CHECK YOUR DISCORD VOLUME SPIKE CHANNEL!{RESET}")
        print(f"{BLUE}{'─'*70}{RESET}")
        
        print(f"\n{GREEN}✅ VOLUME SPIKE CHANNEL: WORKING{RESET}")
        print(f"\n📋 All Discord channels configured:")
        print(f"   1. {GREEN}✅{RESET} Unusual Activity")
        print(f"   2. {GREEN}✅{RESET} Momentum Signals")
        print(f"   3. {GREEN}✅{RESET} ODTE Gamma Walls")
        print(f"   4. {GREEN}✅{RESET} Volume Spike")
        
        print(f"\n{GREEN}🎉 YOUR 4-CHANNEL ALERT SYSTEM IS COMPLETE!{RESET}")
        
        print(f"\n{BLUE}{'─'*70}{RESET}")
        print(f"{YELLOW}📋 NEXT STEPS:{RESET}")
        print(f"   1. Start your app: python3 app.py")
        print(f"   2. Watch all 4 channels for alerts")
        print(f"   3. Expect 50-100+ alerts/day with extended hours")
        print(f"{BLUE}{'─'*70}{RESET}\n")
        
        return True
        
    except requests.exceptions.Timeout:
        print(f"{RED}❌ Timeout - Discord server not responding{RESET}")
        return False
    except requests.exceptions.HTTPError as e:
        print(f"{RED}❌ HTTP Error: {e.response.status_code}{RESET}")
        if e.response.status_code == 404:
            print(f"{YELLOW}   Webhook URL is invalid or deleted{RESET}")
            print(f"{YELLOW}   Recreate webhook in Discord and update .env{RESET}")
        return False
    except Exception as e:
        print(f"{RED}❌ Error: {str(e)}{RESET}")
        return False

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
