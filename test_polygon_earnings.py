#!/usr/bin/env python3
"""
Test Polygon Earnings API to see data structure
Run this to see what earnings data looks like
"""

import requests
import json
from datetime import datetime, timedelta

API_KEY = "k6FIYK4k_5YrSlIn3qwnPCrnebB6PDrj"

def test_earnings_endpoint():
    """Test Polygon Benzinga earnings endpoint"""
    
    # Get tomorrow's date
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    print("=" * 80)
    print("POLYGON EARNINGS CALENDAR TEST")
    print("=" * 80)
    print(f"\nTesting for date: {tomorrow}\n")
    
    # Endpoint: /partners/benzinga/earnings
    url = "https://api.polygon.io/benzinga/v1/earnings"
    
    params = {
        'apiKey': API_KEY,
        'date.gte': tomorrow,  # Tomorrow onwards
        'date.lte': tomorrow,  # Just tomorrow
        'limit': 50
    }
    
    print(f"Requesting: {url}")
    print(f"Parameters: {params}\n")
    
    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"Status Code: {response.status_code}\n")
        
        if response.status_code == 200:
            data = response.json()
            
            # Pretty print the response
            print("RAW RESPONSE:")
            print("=" * 80)
            print(json.dumps(data, indent=2))
            print("=" * 80)
            
            # Parse results
            if 'results' in data and data['results']:
                print(f"\n✅ Found {len(data['results'])} earnings scheduled for {tomorrow}:\n")
                
                for earning in data['results'][:10]:  # Show first 10
                    ticker = earning.get('ticker', 'N/A')
                    company = earning.get('company_name', 'N/A')
                    time = earning.get('time', 'N/A')
                    eps_actual = earning.get('eps_actual', 'N/A')
                    eps_estimate = earning.get('eps_estimate', 'N/A')
                    revenue_actual = earning.get('revenue_actual', 'N/A')
                    revenue_estimate = earning.get('revenue_estimate', 'N/A')
                    
                    print(f"📊 {ticker} - {company}")
                    print(f"   Time: {time}")
                    print(f"   EPS: Actual={eps_actual}, Est={eps_estimate}")
                    print(f"   Revenue: Actual={revenue_actual}, Est={revenue_estimate}")
                    print()
            else:
                print(f"\n⚠️  No earnings found for {tomorrow}")
                print("   (This is normal if no companies report tomorrow)")
        
        elif response.status_code == 401:
            print("❌ Authentication failed - check API key")
        elif response.status_code == 403:
            print("❌ Access denied - may need upgraded Polygon plan for earnings data")
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
    
    except Exception as e:
        print(f"❌ Request failed: {str(e)}")

def test_specific_ticker():
    """Test getting earnings for specific ticker (MSFT)"""
    
    print("\n" + "=" * 80)
    print("TEST 2: SPECIFIC TICKER (MSFT)")
    print("=" * 80)
    
    url = "https://api.polygon.io/benzinga/v1/earnings"
    
    params = {
        'apiKey': API_KEY,
        'ticker': 'MSFT',
        'limit': 5
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(json.dumps(data, indent=2))
        else:
            print(f"Status: {response.status_code}")
            print(response.text)
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == '__main__':
    test_earnings_endpoint()
    test_specific_ticker()
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
