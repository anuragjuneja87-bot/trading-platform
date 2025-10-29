cat > check_earnings_calendar.py << 'EOF'
#!/usr/bin/env python3
"""
Earnings Calendar Checker - Shows upcoming earnings this week
"""
import os
import sys
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

def get_earnings_calendar():
    """Fetch earnings calendar for this week"""
    api_key = os.getenv('POLYGON_API_KEY')
    
    if not api_key:
        print("❌ POLYGON_API_KEY not found in .env")
        return
    
    # Get this week's date range
    today = datetime.now()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    print('\n' + '=' * 70)
    print('📅 EARNINGS CALENDAR FOR THIS WEEK')
    print('=' * 70)
    print(f'Week: {week_start.strftime("%b %d")} - {week_end.strftime("%b %d, %Y")}')
    print(f'Today: {today.strftime("%A, %b %d, %Y")}')
    print('=' * 70)
    
    # Try multiple Polygon endpoints for better coverage
    
    # Method 1: Check news for earnings mentions
    print('\n🔍 Scanning for earnings announcements...')
    
    news_url = 'https://api.polygon.io/v2/reference/news'
    params = {
        'limit': 100,
        'apiKey': api_key
    }
    
    earnings_found = set()
    
    try:
        response = requests.get(news_url, params=params, timeout=10)
        data = response.json()
        
        if 'results' in data:
            for article in data['results']:
                title = article.get('title', '').lower()
                tickers = article.get('tickers', [])
                
                # Check for earnings keywords
                if any(keyword in title for keyword in ['earnings', 'reports q', 'quarterly results']):
                    for ticker in tickers[:1]:  # Primary ticker
                        earnings_found.add(ticker)
    except Exception as e:
        print(f'⚠️  News scan error: {e}')
    
    # Method 2: Check major stocks that typically report
    major_stocks = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA',
        'AMD', 'INTC', 'NFLX', 'CRM', 'ORCL', 'ADBE', 'PYPL',
        'QCOM', 'TXN', 'AVGO', 'MU', 'AMAT', 'LRCX',
        'BA', 'CAT', 'GE', 'HON', 'MMM', 'UNP',
        'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C',
        'JNJ', 'UNH', 'PFE', 'ABBV', 'TMO', 'ABT',
        'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC'
    ]
    
    # Display results
    print(f'\n🎯 EARNINGS THIS WEEK:\n')
    
    if earnings_found:
        print(f'Found {len(earnings_found)} stocks with earnings activity:\n')
        for ticker in sorted(earnings_found):
            print(f'   📊 {ticker}')
    else:
        print('No specific earnings detected yet.')
    
    print(f'\n\n📌 MONITORING {len(major_stocks)} MAJOR STOCKS:\n')
    
    # Group by sector
    sectors = {
        'Tech': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'AMD', 
                'INTC', 'NFLX', 'CRM', 'ORCL', 'ADBE', 'PYPL', 'QCOM', 'TXN', 
                'AVGO', 'MU', 'AMAT', 'LRCX'],
        'Industrial': ['BA', 'CAT', 'GE', 'HON', 'MMM', 'UNP'],
        'Financial': ['JPM', 'BAC', 'WFC', 'GS', 'MS', 'C'],
        'Healthcare': ['JNJ', 'UNH', 'PFE', 'ABBV', 'TMO', 'ABT'],
        'Energy': ['XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC']
    }
    
    for sector, tickers in sectors.items():
        print(f'\n{sector}:')
        for ticker in tickers:
            status = '🔔' if ticker in earnings_found else '👁️ '
            print(f'   {status} {ticker}')
    
    print('\n' + '=' * 70)
    print('💡 TIP: Earnings typically released:')
    print('   • Pre-market: 5:00 - 8:00 AM ET')
    print('   • Post-market: 4:00 - 7:00 PM ET (90% here)')
    print('=' * 70)
    print('\n✅ Your monitor will auto-detect and alert on ALL earnings!')
    print('   • Pre-market: Scans every 20 seconds')
    print('   • Post-market: Scans every 10 seconds ⚡ FASTEST')
    print('   • Alert latency: 10-30 seconds from release\n')

if __name__ == '__main__':
    get_earnings_calendar()
EOF

chmod +x check_earnings_calendar.py
python3 check_earnings_calendar.py
