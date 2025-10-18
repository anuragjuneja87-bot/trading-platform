import requests
from datetime import datetime

# Your production credentials
PROD_API_KEY = "udxXgn4SSW3ktAY7il2GsUGKHybp"
PROD_URL = "https://api.tradier.com"

def test_production_api():
    """Test Tradier production API"""
    
    print("=" * 60)
    print("TRADIER PRODUCTION API TEST")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Test 1: Get SPY quote
    print("Test 1: Real-time Stock Quote (SPY)")
    print("-" * 60)
    
    headers = {
        'Authorization': f'Bearer {PROD_API_KEY}',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.get(
            f"{PROD_URL}/v1/markets/quotes",
            params={'symbols': 'SPY', 'greeks': 'false'},
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            quote = data['quotes']['quote']
            print(f"✅ SUCCESS!")
            print(f"Symbol: {quote['symbol']}")
            print(f"Price: ${quote['last']:.2f}")
            print(f"Bid: ${quote['bid']:.2f}")
            print(f"Ask: ${quote['ask']:.2f}")
            print(f"Volume: {quote['volume']:,}")
            print(f"Timestamp: {quote.get('trade_date', 'N/A')}")
        else:
            print(f"❌ FAILED: {response.status_code}")
            print(response.text)
    
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
    
    print()
    
    # Test 2: Get options chain
    print("Test 2: Real-time Options Chain (SPY)")
    print("-" * 60)
    
    try:
        # Get expirations
        exp_response = requests.get(
            f"{PROD_URL}/v1/markets/options/expirations",
            params={'symbol': 'SPY'},
            headers=headers
        )
        
        if exp_response.status_code == 200:
            expirations = exp_response.json()['expirations']['date']
            nearest_exp = expirations[0]
            
            print(f"✅ Found {len(expirations)} expirations")
            print(f"Nearest expiration: {nearest_exp}")
            print()
            
            # Get chain for nearest expiration
            chain_response = requests.get(
                f"{PROD_URL}/v1/markets/options/chains",
                params={
                    'symbol': 'SPY',
                    'expiration': nearest_exp,
                    'greeks': 'true'
                },
                headers=headers
            )
            
            if chain_response.status_code == 200:
                chain_data = chain_response.json()
                options = chain_data['options']['option'][:5]  # First 5
                
                print(f"✅ Got {len(chain_data['options']['option'])} strikes")
                print()
                print("Sample strikes (first 5):")
                for opt in options:
                    print(f"  {opt['option_type'].upper()} ${opt['strike']} - "
                          f"OI: {opt.get('open_interest', 0):,} | "
                          f"Vol: {opt.get('volume', 0):,} | "
                          f"Gamma: {opt.get('greeks', {}).get('gamma', 'N/A')}")
            else:
                print(f"❌ Chain failed: {chain_response.status_code}")
        else:
            print(f"❌ Expirations failed: {exp_response.status_code}")
    
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
    
    print()
    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == '__main__':
    test_production_api()
