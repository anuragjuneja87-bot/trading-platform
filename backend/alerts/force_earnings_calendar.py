"""
Force Push Real Weekly Earnings Calendar
Shows what earnings are coming up this week and sends to Discord
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from dotenv import load_dotenv
from alert_manager import AlertManager
from utils.watchlist_manager import WatchlistManager
from datetime import datetime, timedelta
import requests

load_dotenv()

def get_detailed_earnings(manager, symbols):
    """
    Get detailed earnings data for the next 7 days
    """
    print("\n" + "=" * 80)
    print("📅 FETCHING REAL WEEKLY EARNINGS DATA")
    print("=" * 80)
    
    today = datetime.now()
    week_end = today + timedelta(days=7)
    
    earnings_list = []
    
    for symbol in symbols:
        try:
            print(f"\nChecking {symbol}...", end=" ")
            
            # Check for earnings in next 7 days
            start_date = today.strftime('%Y-%m-%d')
            end_date = week_end.strftime('%Y-%m-%d')
            
            endpoint = f"https://api.polygon.io/vX/reference/financials"
            params = {
                'ticker': symbol,
                'filing_date.gte': start_date,
                'filing_date.lte': end_date,
                'limit': 5,
                'timeframe': 'quarterly',
                'apiKey': manager.api_key
            }
            
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'results' in data and data['results']:
                for result in data['results']:
                    filing_date = result.get('filing_date')
                    if filing_date:
                        filing_datetime = datetime.strptime(filing_date, '%Y-%m-%d')
                        
                        if today <= filing_datetime <= week_end:
                            fiscal_period = result.get('fiscal_period', 'Q')
                            fiscal_year = result.get('fiscal_year', '')
                            company_name = result.get('company_name', symbol)
                            
                            # Get time of day (estimate)
                            filing_hour = datetime.now().hour
                            if filing_hour < 9:
                                time_str = "Before Market Open"
                            else:
                                time_str = "After Market Close"
                            
                            earnings_info = {
                                'symbol': symbol,
                                'company_name': company_name,
                                'date': filing_date,
                                'day_name': filing_datetime.strftime('%A, %B %d'),
                                'time': time_str,
                                'fiscal_period': f"{fiscal_period} {fiscal_year}"
                            }
                            
                            earnings_list.append(earnings_info)
                            print(f"✅ Found earnings on {filing_date}")
                            break
                else:
                    print("No earnings this week")
            else:
                print("No earnings this week")
            
            import time
            time.sleep(0.3)  # Rate limiting
            
        except Exception as e:
            print(f"Error: {str(e)}")
            continue
    
    return earnings_list


def display_earnings_calendar(earnings_list):
    """
    Display formatted earnings calendar
    """
    if not earnings_list:
        print("\n❌ No earnings found for your watchlist this week")
        return
    
    print("\n" + "=" * 80)
    print("📊 EARNINGS CALENDAR - THIS WEEK")
    print("=" * 80)
    
    # Group by date
    from collections import defaultdict
    by_date = defaultdict(list)
    for earnings in earnings_list:
        date = earnings['date']
        by_date[date].append(earnings)
    
    # Sort and display
    for date in sorted(by_date.keys()):
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        day_name = date_obj.strftime('%A, %B %d, %Y')
        
        print(f"\n📅 {day_name}")
        print("-" * 80)
        
        for earnings in by_date[date]:
            symbol = earnings['symbol']
            company = earnings.get('company_name', symbol)
            time_str = earnings['time']
            period = earnings['fiscal_period']
            
            print(f"  🔹 {symbol:6} | {company[:40]:40} | {time_str:20} | {period}")
    
    print("\n" + "=" * 80)
    print(f"Total: {len(earnings_list)} companies reporting this week")
    print("=" * 80)


def main():
    """
    Main function: Get real earnings and push to Discord
    """
    print("\n" + "=" * 80)
    print("🚀 FORCE PUSH WEEKLY EARNINGS CALENDAR")
    print("=" * 80)
    
    # Initialize
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        print("❌ Error: POLYGON_API_KEY not found in .env")
        return
    
    manager = AlertManager(polygon_api_key=api_key)
    watchlist_manager = WatchlistManager('backend/data/watchlist.txt')
    
    # Get symbols
    symbols = watchlist_manager.load_symbols()
    print(f"\n📋 Checking {len(symbols)} symbols from watchlist:")
    print(f"   {', '.join(symbols)}")
    
    # Get earnings data
    earnings_list = get_detailed_earnings(manager, symbols)
    
    # Display in console
    display_earnings_calendar(earnings_list)
    
    # Send to Discord
    if earnings_list:
        print("\n" + "=" * 80)
        print("📢 SENDING TO DISCORD...")
        print("=" * 80)
        
        # Override the weekly check to send now
        manager.weekly_earnings_sent = False
        
        if manager.discord:
            success = manager.discord.send_weekly_earnings(earnings_list)
            
            if success:
                print("\n✅ SUCCESS! Weekly earnings calendar sent to Discord!")
                print(f"📅 Check your #earnings-calendar channel")
                print(f"   Sent: {len(earnings_list)} companies")
            else:
                print("\n❌ Failed to send to Discord")
                print("   Check webhook configuration")
        else:
            print("\n⚠️ Discord alerter not enabled")
    else:
        print("\n📭 No earnings found this week for your watchlist")
        print("   The companies in your watchlist don't have earnings scheduled")
        print("   for the next 7 days")
    
    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
