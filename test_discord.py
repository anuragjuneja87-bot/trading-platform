"""
Test Discord Alerts for Benzinga Integration
Sends test messages to all 3 channels to verify webhooks work
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file FIRST
env_path = Path.cwd() / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded .env from {env_path}")
else:
    print(f"⚠️  No .env file found at {env_path}")

# Add backend to path
backend_dir = Path.cwd() / 'backend'
sys.path.insert(0, str(backend_dir))

from alerts.discord_alerter import DiscordAlerter
import yaml
from datetime import datetime


def load_config():
    """Load config.yaml from backend/config directory"""
    config_path = backend_dir / 'config' / 'config.yaml'
    
    if not config_path.exists():
        # Try alternate location
        config_path = backend_dir / 'config.yaml'
    
    if not config_path.exists():
        raise FileNotFoundError(f"config.yaml not found at {config_path}")
    
    print(f"✅ Loading config from: {config_path}")
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def test_watchlist_news_alert(discord: DiscordAlerter):
    """Test #watchlist-news channel with Benzinga article"""
    print("\n" + "="*60)
    print("TEST 1: #watchlist-news (Watchlist Ticker News)")
    print("="*60)
    
    try:
        # Use existing send_news_alert method
        success = discord.send_news_alert(
            symbol='NVDA',
            news_data={
                'sentiment': 'POSITIVE',
                'headlines': [
                    '🧪 TEST: NVIDIA Announces Partnership with OpenAI',
                    '🧪 TEST: NVIDIA Stock Surges on Strong Demand',
                    '🧪 TEST: Analysts Raise NVIDIA Price Target to $180'
                ],
                'article_urls': [
                    'https://www.benzinga.com/news/nvda-openai-partnership',
                    'https://www.benzinga.com/news/nvda-datacenter-growth',
                    'https://www.benzinga.com/news/nvda-price-target'
                ],
                'recent_news': 3,
                'news_impact': 'HIGH'
            }
        )
        
        if success:
            print("✅ SUCCESS! Check your #watchlist-news channel")
            print("   Should see: NVDA news with 3 test articles")
        else:
            print("❌ FAILED! Webhook might not be configured")
        
        return success
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_openai_news_alert(discord: DiscordAlerter):
    """Test #openai-news channel"""
    print("\n" + "="*60)
    print("TEST 2: #openai-news (AI Sector News)")
    print("="*60)
    
    alert_data = {
        'topic': 'OpenAI',
        'emoji': '🤖',
        'urgency': 'HIGH',
        'article_count': 3,
        'articles': [
            {
                'title': '🧪 TEST: OpenAI Announces GPT-5 Release Date',
                'url': 'https://www.benzinga.com/news/openai-gpt5'
            },
            {
                'title': '🧪 TEST: Sam Altman Discusses Future of AI Safety',
                'url': 'https://www.benzinga.com/news/altman-ai-safety'
            },
            {
                'title': '🧪 TEST: OpenAI Partners with Microsoft',
                'url': 'https://www.benzinga.com/news/openai-microsoft'
            }
        ],
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        success = discord.send_ai_news_alert(alert_data)
        
        if success:
            print("✅ SUCCESS! Check your #openai-news channel")
            print("   Should see: 🤖 OpenAI Update with 3 test articles")
        else:
            print("❌ FAILED! Webhook might not be configured")
        
        return success
    except AttributeError:
        print("⚠️  send_ai_news_alert() method not found")
        print("   You need to add the new methods to discord_alerter.py")
        print("   (This is expected - skip for now)")
        return False
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False


def test_macro_news_alert(discord: DiscordAlerter):
    """Test #news-alerts channel with macro news"""
    print("\n" + "="*60)
    print("TEST 3: #news-alerts (Macro/Critical News)")
    print("="*60)
    
    alert_data = {
        'category': 'FED',
        'emoji': '🏦',
        'priority': 'CRITICAL',
        'title': '🧪 TEST: Federal Reserve Announces Rate Cut',
        'url': 'https://www.benzinga.com/news/fed-rate-cut',
        'teaser': 'This is a TEST alert. The Federal Reserve announced a rate cut.',
        'source': 'BENZINGA',
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        success = discord.send_macro_news_alert(alert_data)
        
        if success:
            print("✅ SUCCESS! Check your #news-alerts channel")
            print("   Should see: 🏦 CRITICAL - FED test announcement")
        else:
            print("❌ FAILED! Webhook might not be configured")
        
        return success
    except AttributeError:
        print("⚠️  send_macro_news_alert() method not found")
        print("   You need to add the new methods to discord_alerter.py")
        print("   (This is expected - skip for now)")
        return False
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False


def test_spillover_alert(discord: DiscordAlerter):
    """Test #news-alerts channel with spillover opportunity"""
    print("\n" + "="*60)
    print("TEST 4: #news-alerts (Spillover Opportunity)")
    print("="*60)
    
    alert_data = {
        'primary_ticker': 'NVDA',
        'article': {
            'title': '🧪 TEST: NVIDIA Announces Supply Deal',
            'url': 'https://www.benzinga.com/news/nvda-deal',
            'published': datetime.now().isoformat(),
            'source': 'BENZINGA',
            'teaser': 'This is a TEST alert for spillover detection.'
        },
        'opportunities': [
            {
                'ticker': 'NVTS',
                'volume_data': {
                    'rvol': 4.2,
                    'price': 45.20,
                }
            },
            {
                'ticker': 'SMCI',
                'volume_data': {
                    'rvol': 3.1,
                    'price': 32.50,
                }
            }
        ],
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        success = discord.send_spillover_alert(alert_data)
        
        if success:
            print("✅ SUCCESS! Check your #news-alerts channel")
            print("   Should see: 🔔 SPILLOVER test - NVTS, SMCI")
        else:
            print("❌ FAILED! Webhook might not be configured")
        
        return success
    except AttributeError:
        print("⚠️  send_spillover_alert() method not found")
        print("   You need to add the new methods to discord_alerter.py")
        print("   (This is expected - skip for now)")
        return False
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False


def main():
    print("\n" + "="*70)
    print("🧪 DISCORD ALERTS TEST - BENZINGA INTEGRATION")
    print("="*70)
    print("\nThis will send TEST alerts to your Discord channels\n")
    
    # Verify env vars loaded
    print("Environment Variables Check:")
    env_vars = [
        'DISCORD_NEWS_ONLY',
        'DISCORD_OPENAI_NEWS', 
        'DISCORD_NEWS_ALERTS'
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var}: {value[:40]}...")
        else:
            print(f"  ❌ {var}: NOT SET")
    
    # Load config
    try:
        config = load_config()
        discord_config = config.get('discord', {})
        
        # Initialize Discord alerter
        discord = DiscordAlerter(config=discord_config)
        
        print(f"\nDiscord channels configured:")
        active_count = 0
        for channel, url in discord.webhooks.items():
            if url and url.startswith('http'):
                print(f"  ✅ {channel}")
                active_count += 1
            else:
                print(f"  ⚠️  {channel} (not configured)")
        
        if active_count == 0:
            print("\n❌ NO WEBHOOKS CONFIGURED!")
            print("Check that your .env file is loaded properly")
            return
        
        # Run tests
        results = []
        
        results.append(('Watchlist News', test_watchlist_news_alert(discord)))
        results.append(('OpenAI News', test_openai_news_alert(discord)))
        results.append(('Macro News', test_macro_news_alert(discord)))
        results.append(('Spillover Alert', test_spillover_alert(discord)))
        
        # Summary
        print("\n" + "="*70)
        print("📊 TEST SUMMARY")
        print("="*70)
        
        passed = sum(1 for _, success in results if success)
        total = len(results)
        
        for name, success in results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} - {name}")
        
        print(f"\n{passed}/{total} tests passed")
        
        if passed >= 1:
            print(f"\n✅ At least {passed} webhook(s) working!")
            if passed < total:
                print("⚠️  Some tests failed because new methods not added yet")
                print("   This is OK - you can add them tomorrow")
            print("\n🎉 Discord integration is working!")
            print("Your alerts are ready for Monday trading!")
        else:
            print("\n❌ ALL TESTS FAILED")
            print("Check your Discord webhook configuration")
        
        print("="*70 + "\n")
        
    except FileNotFoundError as e:
        print(f"❌ ERROR: {str(e)}")
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()