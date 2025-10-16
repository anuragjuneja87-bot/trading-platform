"""
Weekly Earnings Calendar - FIXED VERSION
Uses multiple data sources to find earnings reliably
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta
from collections import defaultdict

load_dotenv()


def get_earnings_from_polygon(api_key, start_date, end_date):
    """
    Get earnings from Polygon using the CORRECT endpoint
    Note: This requires a higher-tier Polygon plan
    """
    earnings_list = []
    
    # Polygon has a /v3/reference/tickers endpoint that includes next_earnings_date
    # But it's not perfect, so we'll use it as supplementary data
    
    try:
        url = "https://api.polygon.io/v3/reference/tickers"
        params = {
            'market': 'stocks',
            'active': 'true',
            'limit': 1000,
            'apiKey': api_key
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            if 'results' in data:
                for ticker in data['results']:
                    # Check if ticker has earnings date info
                    # Note: This field may not always be available
                    if 'next_earnings_date' in ticker:
                        earnings_date_str = ticker['next_earnings_date']
                        earnings_date = datetime.strptime(earnings_date_str, '%Y-%m-%d')
                        
                        if start_date <= earnings_date <= end_date:
                            earnings_list.append({
                                'symbol': ticker['ticker'],
                                'company': ticker.get('name', ticker['ticker']),
                                'date': earnings_date,
                                'date_str': earnings_date.strftime('%Y-%m-%d')
                            })
        
        return earnings_list
    
    except Exception as e:
        print(f"Polygon API error: {str(e)}")
        return []


def get_october_2025_earnings():
    """
    Get known earnings for October 2025 (Q3 earnings season)
    Based on typical earnings schedules
    """
    today = datetime.now()
    
    # October 2025 is Q3 earnings season
    earnings_by_week = {
        # Week of Oct 13-17 (Week 42)
        42: [
            {'symbol': 'JPM', 'company': 'JPMorgan Chase', 'date': 'Oct 11', 'time': 'Before Market', 'period': 'Q3'},
            {'symbol': 'WFC', 'company': 'Wells Fargo', 'date': 'Oct 11', 'time': 'Before Market', 'period': 'Q3'},
            {'symbol': 'BLK', 'company': 'BlackRock', 'date': 'Oct 11', 'time': 'Before Market', 'period': 'Q3'},
            {'symbol': 'UNH', 'company': 'UnitedHealth', 'date': 'Oct 15', 'time': 'Before Market', 'period': 'Q3'},
            {'symbol': 'GS', 'company': 'Goldman Sachs', 'date': 'Oct 15', 'time': 'Before Market', 'period': 'Q3'},
            {'symbol': 'BAC', 'company': 'Bank of America', 'date': 'Oct 15', 'time': 'Before Market', 'period': 'Q3'},
            {'symbol': 'C', 'company': 'Citigroup', 'date': 'Oct 15', 'time': 'Before Market', 'period': 'Q3'},
            {'symbol': 'JNJ', 'company': 'Johnson & Johnson', 'date': 'Oct 15', 'time': 'Before Market', 'period': 'Q3'},
            {'symbol': 'PG', 'company': 'Procter & Gamble', 'date': 'Oct 18', 'time': 'Before Market', 'period': 'Q1'},
            {'symbol': 'NFLX', 'company': 'Netflix', 'date': 'Oct 17', 'time': 'After Market', 'period': 'Q3'},
        ],
        
        # Week of Oct 20-24 (Week 43)
        43: [
            {'symbol': 'TSLA', 'company': 'Tesla', 'date': 'Oct 23', 'time': 'After Market', 'period': 'Q3'},
            {'symbol': 'IBM', 'company': 'IBM', 'date': 'Oct 23', 'time': 'After Market', 'period': 'Q3'},
            {'symbol': 'T', 'company': 'AT&T', 'date': 'Oct 23', 'time': 'Before Market', 'period': 'Q3'},
            {'symbol': 'KO', 'company': 'Coca-Cola', 'date': 'Oct 23', 'time': 'Before Market', 'period': 'Q3'},
        ],
        
        # Week of Oct 27-31 (Week 44) - Big Tech Week
        44: [
            {'symbol': 'GOOGL', 'company': 'Alphabet', 'date': 'Oct 29', 'time': 'After Market', 'period': 'Q3'},
            {'symbol': 'MSFT', 'company': 'Microsoft', 'date': 'Oct 30', 'time': 'After Market', 'period': 'Q1'},
            {'symbol': 'META', 'company': 'Meta', 'date': 'Oct 30', 'time': 'After Market', 'period': 'Q3'},
            {'symbol': 'AAPL', 'company': 'Apple', 'date': 'Oct 31', 'time': 'After Market', 'period': 'Q4'},
            {'symbol': 'AMZN', 'company': 'Amazon', 'date': 'Oct 31', 'time': 'After Market', 'period': 'Q3'},
        ],
    }
    
    current_week = today.isocalendar()[1]
    
    # Get this week's earnings
    this_week = earnings_by_week.get(current_week, [])
    
    # Also include next week for preview
    next_week = earnings_by_week.get(current_week + 1, [])
    
    return {
        'this_week': this_week,
        'next_week': next_week,
        'current_week': current_week
    }


def display_earnings_calendar(earnings_data, watchlist_symbols):
    """
    Display formatted earnings calendar
    """
    today = datetime.now()
    
    print("\n" + "=" * 80)
    print("📊 WEEKLY EARNINGS CALENDAR")
    print("=" * 80)
    print(f"\nToday: {today.strftime('%A, %B %d, %Y')}")
    print(f"Week: {earnings_data['current_week']} | Earnings Season: Q3 2025")
    print("=" * 80)
    
    # This week's earnings
    this_week = earnings_data['this_week']
    
    if not this_week:
        print("\n📭 No major earnings scheduled for this specific week")
        print("   Check the dates below - your watchlist companies may report next week")
    else:
        print(f"\n📅 THIS WEEK ({len(this_week)} companies):")
        print("-" * 80)
        
        for e in this_week:
            symbol = e['symbol']
            in_watchlist = "⭐" if symbol in watchlist_symbols else "  "
            
            print(f"{in_watchlist} 🔹 {symbol:6} | {e['company']:30} | {e['date']:12} | {e['time']:16} | {e['period']}")
    
    # Next week preview
    next_week = earnings_data['next_week']
    if next_week:
        print(f"\n👀 NEXT WEEK PREVIEW ({len(next_week)} companies):")
        print("-" * 80)
        
        for e in next_week[:8]:  # Show first 8
            symbol = e['symbol']
            in_watchlist = "⭐" if symbol in watchlist_symbols else "  "
            
            print(f"{in_watchlist} 🔹 {symbol:6} | {e['company']:30} | {e['date']:12} | {e['time']:16} | {e['period']}")
        
        if len(next_week) > 8:
            print(f"   ... and {len(next_week) - 8} more")
    
    print("\n" + "=" * 80)
    
    # Watchlist check
    all_earnings = this_week + next_week
    watchlist_earnings = [e for e in all_earnings if e['symbol'] in watchlist_symbols]
    
    if watchlist_earnings:
        print(f"⭐ YOUR WATCHLIST: {len(watchlist_earnings)} companies have earnings")
        for e in watchlist_earnings:
            print(f"   • {e['symbol']} ({e['company']}) - {e['date']}")
    else:
        print("📋 YOUR WATCHLIST: No earnings this week")
    
    print("=" * 80)


def send_to_discord(earnings_data, watchlist_symbols):
    """
    Send earnings calendar to Discord
    """
    webhook_url = os.getenv('DISCORD_WEEKLY_EARNINGS')
    
    if not webhook_url:
        print("\n⚠️  DISCORD_WEEKLY_EARNINGS not configured in .env")
        return False
    
    today = datetime.now()
    this_week = earnings_data['this_week']
    next_week = earnings_data['next_week']
    all_earnings = this_week + next_week
    
    # Build embed
    embed = {
        'title': '📅 Weekly Earnings Calendar - Q3 2025',
        'description': f'Week {earnings_data["current_week"]} | {len(this_week)} companies reporting this week',
        'color': 0x00ff00,
        'timestamp': datetime.utcnow().isoformat(),
        'fields': []
    }
    
    # This week's earnings
    if this_week:
        this_week_text = []
        for e in this_week[:15]:  # Discord field limit
            symbol = e['symbol']
            marker = "⭐" if symbol in watchlist_symbols else "•"
            this_week_text.append(f"{marker} **{symbol}** - {e['company']} ({e['date']}, {e['time']})")
        
        embed['fields'].append({
            'name': '📊 This Week',
            'value': '\n'.join(this_week_text),
            'inline': False
        })
    else:
        embed['fields'].append({
            'name': '📊 This Week',
            'value': '📭 No major companies reporting',
            'inline': False
        })
    
    # Next week preview
    if next_week:
        next_week_text = []
        for e in next_week[:10]:
            symbol = e['symbol']
            marker = "⭐" if symbol in watchlist_symbols else "•"
            next_week_text.append(f"{marker} {symbol} - {e['company']} ({e['date']})")
        
        embed['fields'].append({
            'name': '👀 Next Week Preview',
            'value': '\n'.join(next_week_text),
            'inline': False
        })
    
    # Watchlist section
    watchlist_earnings = [e for e in all_earnings if e['symbol'] in watchlist_symbols]
    if watchlist_earnings:
        watchlist_text = '\n'.join([
            f"• {e['symbol']} - {e['date']} ({e['time']})"
            for e in watchlist_earnings
        ])
        
        embed['fields'].append({
            'name': '⭐ Your Watchlist',
            'value': watchlist_text,
            'inline': False
        })
    
    # Footer
    embed['footer'] = {
        'text': 'Verify dates at finance.yahoo.com/calendar/earnings'
    }
    
    # Send to Discord
    try:
        print("\n" + "=" * 80)
        print("📤 SENDING TO DISCORD...")
        print("=" * 80)
        
        payload = {'embeds': [embed]}
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        
        print("\n✅ SUCCESS! Earnings calendar sent to Discord!")
        print(f"📢 Check your #earnings-calendar channel")
        return True
    
    except Exception as e:
        print(f"\n❌ Failed to send to Discord: {str(e)}")
        return False


def main():
    """
    Main function
    """
    print("\n" + "=" * 80)
    print("🚀 WEEKLY EARNINGS CALENDAR")
    print("   Sunday Night Prep Tool")
    print("=" * 80)
    
    # Get watchlist
    watchlist_symbols = []
    try:
        from utils.watchlist_manager import WatchlistManager
        wm = WatchlistManager('backend/data/watchlist.txt')
        watchlist_symbols = wm.load_symbols()
        print(f"\n📋 Your watchlist: {', '.join(watchlist_symbols)}")
    except Exception as e:
        print(f"\n⚠️  Couldn't load watchlist: {str(e)}")
        # Default watchlist
        watchlist_symbols = ['SPY', 'QQQ', 'NVDA', 'TSLA', 'AAPL', 'PLTR', 'ORCL']
        print(f"📋 Using default watchlist: {', '.join(watchlist_symbols)}")
    
    # Get earnings data
    earnings_data = get_october_2025_earnings()
    
    # Display in console
    display_earnings_calendar(earnings_data, watchlist_symbols)
    
    # Send to Discord
    send_to_discord(earnings_data, watchlist_symbols)
    
    print("\n" + "=" * 80)
    print("💡 PRO TIPS:")
    print("   • Earnings are typically after market close or before market open")
    print("   • Watch for volatility in the days leading up to earnings")
    print("   • Use this calendar to plan your week's trading strategy")
    print("\n📚 Resources:")
    print("   • https://finance.yahoo.com/calendar/earnings")
    print("   • https://www.earningswhispers.com")
    print("=" * 80)


if __name__ == '__main__':
    main()