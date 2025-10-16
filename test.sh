cd backend/analyzers
python3 << 'EOF'
import os
from dotenv import load_dotenv
load_dotenv('../../.env')

token = os.getenv('TWITTER_BEARER_TOKEN')
print(f"Token exists: {bool(token)}")
print(f"Token length: {len(token) if token else 0}")
print(f"Token starts with AAAA: {token.startswith('AAAA') if token else False}")

# Test actual API call
import requests
headers = {'Authorization': f'Bearer {token}'}
response = requests.get(
    'https://api.twitter.com/2/tweets/search/recent',
    headers=headers,
    params={'query': 'TSLA', 'max_results': 10}
)
print(f"API Status: {response.status_code}")
if response.status_code != 200:
    print(f"Error: {response.text}")
EOF
