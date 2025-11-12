cd ~/Desktop/trading-platform/backend
python3 -c "
from dotenv import load_dotenv
import os
load_dotenv()
webhook = os.getenv('DISCORD_MOMENTUM_SIGNALS')
print(f'Webhook URL: {webhook}')
print(f'Length: {len(webhook) if webhook else 0}')
print(f'Starts with https: {webhook.startswith(\"https\") if webhook else False}')
"
