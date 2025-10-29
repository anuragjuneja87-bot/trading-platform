#!/usr/bin/env python3
"""
Manually send earnings preview for tomorrow
Tests the 6 PM preview feature RIGHT NOW
"""

import requests
from datetime import datetime, timedelta

API_KEY = "k6FIYK4k_5YrSlIn3qwnPCrnebB6PDrj"
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1427168277150564516/jVpIERY-Za7r77JG8lizRTe4g8qQ5uSBjlIMLud7GBy5qs9x33iRRN7o770Q-FDl-9LN"

def send_preview_now():
    """Send earnings preview for tomorrow"""
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"📅 Fetching earnings for {tomorrow}...")
    
    # Get tomorrow's earnings
    url = "https://api.polygon.io/benzinga/v1/earnings"
    params = {
        'apiKey': API_KEY,
        'date.gte': tomorrow,
        'date.lte': tomorrow,
        'limit': 250
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        results = data.get('results', [])
        
        # Filter confirmed
        confirmed = [e for e in results if e.get('date_status') == 'confirmed']
        
        print(f"✅ Found {len(confirmed)} confirmed earnings\n")
        
        # Group by importance
        major = [e for e in confirmed if e.get('importance', 0) >= 4]
        others = [e for e in confirmed if e.get('importance', 0) < 4]
        
        # Build major earnings list
        major_lines = []
        for e in major[:15]:
            ticker = e.get('ticker')
            company = e.get('company_name', ticker)
            time = e.get('time', 'N/A')[:5]
            eps_est = e.get('estimated_eps', 0)
            rev_est = e.get('estimated_revenue', 0) / 1e9 if e.get('estimated_revenue') else 0
            
            major_lines.append(
                f"**{ticker}** - {company}\n"
                f"  ⏰ {time} ET | EPS Est: ${eps_est:.2f} | Rev Est: ${rev_est:.2f}B"
            )
        
        # Build Discord embed
        embed = {
            'title': f'📅 EARNINGS PREVIEW - {tomorrow}',
            'description': f'**{len(confirmed)} companies reporting earnings**',
            'color': 0x5865F2,
            'fields': [
                {
                    'name': f'🔥 Major Earnings ({len(major)} companies)',
                    'value': '\n\n'.join(major_lines[:10]) if major_lines else 'None',
                    'inline': False
                }
            ],
            'footer': {
                'text': 'Daily Preview • Monitor active 3:50-7 PM ET'
            },
            'timestamp': datetime.now().isoformat()
        }
        
        if len(major) > 10:
            embed['fields'].append({
                'name': '📊 More Major Earnings',
                'value': '\n\n'.join(major_lines[10:15]),
                'inline': False
            })
        
        if others:
            other_tickers = ', '.join([e['ticker'] for e in others[:30]])
            embed['fields'].append({
                'name': f'ℹ️ Other Earnings ({len(others)} companies)',
                'value': other_tickers + ('...' if len(others) > 30 else ''),
                'inline': False
            })
        
        # Send to Discord
        payload = {'embeds': [embed]}
        
        print("📤 Sending to Discord...\n")
        
        discord_response = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        discord_response.raise_for_status()
        
        print("=" * 80)
        print("✅ PREVIEW SENT TO DISCORD!")
        print("=" * 80)
        print(f"\nCheck your #earnings-realtime channel")
        print(f"\nThis is what you'll receive automatically at 6:00 PM ET daily")
        print(f"\nMajor earnings tomorrow:")
        for e in major[:5]:
            print(f"  • {e['ticker']} - {e.get('company_name')} at {e.get('time', 'N/A')[:5]} ET")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == '__main__':
    send_preview_now()
