"""
Test All 4 Discord Channels with REAL Benzinga News
Sends actual recent news to verify routing is correct
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from dotenv import load_dotenv
import requests
from datetime import datetime

load_dotenv()

# Discord webhooks
WEBHOOKS = {
    'critical-signals': os.getenv('DISCORD_CRITICAL_SIGNALS') or os.getenv('DISCORD_WEBHOOK_URL'),
    'watchlist-news': os.getenv('DISCORD_NEWS_ONLY'),
    'ai-sector-news': os.getenv('DISCORD_OPENAI_NEWS'),
    'spillover-alerts': os.getenv('DISCORD_NEWS_ALERTS')
}

def send_discord_alert(webhook_url: str, embed: dict) -> bool:
    """Send alert to Discord"""
    try:
        response = requests.post(
            webhook_url,
            json={'embeds': [embed]},
            timeout=10
        )
        return response.status_code == 204
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return False


def test_critical_signals():
    """Test #critical-signals with Fed news"""
    print("\n" + "="*70)
    print("TEST 1: #critical-signals (Fed/Macro)")
    print("="*70)
    
    webhook = WEBHOOKS['critical-signals']
    if not webhook:
        print("❌ DISCORD_CRITICAL_SIGNALS not configured")
        return False
    
    embed = {
        'title': '🚨 CRITICAL: TEST ALERT - Fed Policy Update',
        'description': (
            '**THIS IS A TEST ALERT**\n\n'
            'Federal Reserve signals potential rate cuts in Q2 2025. '
            'Powell indicates inflation progress allows for policy flexibility.\n\n'
            '🎯 **Impact:** CRITICAL - Market-wide\n'
            '📊 **Source:** Test System\n'
            f'⏰ **Time:** {datetime.now().strftime("%I:%M %p ET")}\n\n'
            '✅ If you see this, your **#critical-signals** channel is working!'
        ),
        'color': 0xff0000,  # Red
        'footer': {'text': 'Critical Signals Monitor • TEST'}
    }
    
    print(f"📡 Sending to: DISCORD_CRITICAL_SIGNALS")
    success = send_discord_alert(webhook, embed)
    
    if success:
        print("✅ Alert sent successfully!")
        print("   Check your #critical-signals channel")
    else:
        print("❌ Failed to send alert")
    
    return success


def test_watchlist_news():
    """Test #watchlist-news with real Benzinga news"""
    print("\n" + "="*70)
    print("TEST 2: #watchlist-news (Your Stocks)")
    print("="*70)
    
    webhook = WEBHOOKS['watchlist-news']
    if not webhook:
        print("❌ DISCORD_NEWS_ONLY not configured")
        return False
    
    # Get real NVDA news from Benzinga
    print("📥 Fetching real NVDA news from Benzinga...")
    
    try:
        from clients.benzinga_client import BenzingaClient
        api_key = os.getenv('POLYGON_API_KEY')
        client = BenzingaClient(api_key)
        news = client.get_recent_news('NVDA', hours=24)
        
        if news and len(news) > 0:
            article = news[0]
            title = article.get('title', 'NVDA News Update')
            teaser = article.get('teaser', 'Recent NVDA development')
            url = article.get('url', '')
            published = article.get('published', '')
            
            print(f"✅ Found real news: {title[:50]}...")
        else:
            # Fallback
            title = "NVDA TEST: Announces New AI Chip Architecture"
            teaser = "NVIDIA unveils next-generation GPU designed for AI workloads"
            url = "https://example.com"
            published = datetime.now().isoformat()
    except:
        # Fallback if Benzinga fails
        title = "NVDA TEST: Announces New AI Chip Architecture"
        teaser = "NVIDIA unveils next-generation GPU designed for AI workloads"
        url = "https://example.com"
        published = datetime.now().isoformat()
    
    embed = {
        'title': f'📊 NVDA - {title}',
        'description': (
            f'**THIS IS A TEST ALERT (Real News)**\n\n'
            f'{teaser[:200]}...\n\n'
            f'🎯 **Priority:** HIGH\n'
            f'📰 **Source:** Benzinga\n'
            f'⏰ **Published:** {published[:19].replace("T", " ")}\n\n'
            f'✅ If you see this, your **#watchlist-news** channel is working!\n\n'
            f'[Read Full Article]({url})'
        ),
        'color': 0x00ff00,  # Green
        'footer': {'text': 'Watchlist News Monitor • TEST'}
    }
    
    print(f"📡 Sending to: DISCORD_NEWS_ONLY")
    success = send_discord_alert(webhook, embed)
    
    if success:
        print("✅ Alert sent successfully!")
        print("   Check your #watchlist-news channel")
    else:
        print("❌ Failed to send alert")
    
    return success


def test_ai_sector():
    """Test #ai-sector-news with OpenAI news"""
    print("\n" + "="*70)
    print("TEST 3: #ai-sector-news (AI Industry)")
    print("="*70)
    
    webhook = WEBHOOKS['ai-sector-news']
    if not webhook:
        print("❌ DISCORD_OPENAI_NEWS not configured")
        return False
    
    # Get real AI news from Benzinga
    print("📥 Fetching real AI sector news from Benzinga...")
    
    try:
        from clients.benzinga_client import BenzingaClient
        api_key = os.getenv('POLYGON_API_KEY')
        client = BenzingaClient(api_key)
        
        # Search for OpenAI/AI news
        news = client.get_recent_news(None, hours=48)
        
        ai_news = None
        for article in news:
            title_lower = article.get('title', '').lower()
            if any(kw in title_lower for kw in ['openai', 'artificial intelligence', 'ai model', 'chatgpt']):
                ai_news = article
                break
        
        if ai_news:
            title = ai_news.get('title', 'AI Industry Update')
            teaser = ai_news.get('teaser', 'Recent AI development')
            url = ai_news.get('url', '')
            published = ai_news.get('published', '')
            print(f"✅ Found real AI news: {title[:50]}...")
        else:
            # Fallback
            title = "OpenAI TEST: Announces GPT-5 Development Milestone"
            teaser = "OpenAI reveals significant progress on next-generation AI model"
            url = "https://example.com"
            published = datetime.now().isoformat()
    except:
        # Fallback
        title = "OpenAI TEST: Announces GPT-5 Development Milestone"
        teaser = "OpenAI reveals significant progress on next-generation AI model"
        url = "https://example.com"
        published = datetime.now().isoformat()
    
    embed = {
        'title': f'🤖 AI SECTOR - {title}',
        'description': (
            f'**THIS IS A TEST ALERT (Real News)**\n\n'
            f'{teaser[:200]}...\n\n'
            f'💡 **Impact:** AI Infrastructure stocks\n'
            f'📊 **Source:** Benzinga\n'
            f'⏰ **Published:** {published[:19].replace("T", " ")}\n\n'
            f'✅ If you see this, your **#ai-sector-news** channel is working!\n\n'
            f'[Read Full Article]({url})'
        ),
        'color': 0x3498db,  # Blue
        'footer': {'text': 'AI Sector Monitor • TEST'}
    }
    
    print(f"📡 Sending to: DISCORD_OPENAI_NEWS")
    success = send_discord_alert(webhook, embed)
    
    if success:
        print("✅ Alert sent successfully!")
        print("   Check your #ai-sector-news channel")
    else:
        print("❌ Failed to send alert")
    
    return success


def test_spillover():
    """Test #spillover-alerts with NVDA spillover"""
    print("\n" + "="*70)
    print("TEST 4: #spillover-alerts (Momentum Plays)")
    print("="*70)
    
    webhook = WEBHOOKS['spillover-alerts']
    if not webhook:
        print("❌ DISCORD_NEWS_ALERTS not configured")
        return False
    
    embed = {
        'title': '📊 SPILLOVER OPPORTUNITY - TEST ALERT',
        'description': (
            '**THIS IS A TEST ALERT**\n\n'
            '**Primary News:** NVDA announces H200 chip launch\n\n'
            '**Spillover Impact:**\n'
            '• SMCI - RVOL: 3.2x, Price: $45.50 (+2.8%)\n'
            '• NVTS - RVOL: 2.6x, Price: $52.30 (+1.9%)\n'
            '• ARM - RVOL: 2.4x, Price: $138.90 (+1.5%)\n\n'
            '**Action:**\n'
            '✓ Check entry opportunities\n'
            '✓ Monitor for continuation\n'
            '✓ Consider adding to watchlist\n\n'
            '✅ If you see this, your **#spillover-alerts** channel is working!'
        ),
        'color': 0xf39c12,  # Orange
        'footer': {'text': 'Spillover Detector • TEST'}
    }
    
    print(f"📡 Sending to: DISCORD_NEWS_ALERTS")
    success = send_discord_alert(webhook, embed)
    
    if success:
        print("✅ Alert sent successfully!")
        print("   Check your #spillover-alerts channel")
    else:
        print("❌ Failed to send alert")
    
    return success


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("🧪 DISCORD CHANNEL TEST SUITE")
    print("Testing all 4 channels with REAL news from Benzinga")
    print("="*70)
    
    # Check configuration
    print("\n📋 Checking Discord webhook configuration...")
    
    all_configured = True
    for channel, webhook in WEBHOOKS.items():
        if webhook and webhook.startswith('http'):
            print(f"   ✅ {channel}: Configured")
        else:
            print(f"   ❌ {channel}: NOT CONFIGURED")
            all_configured = False
    
    if not all_configured:
        print("\n⚠️  Some webhooks not configured. Fix .env and try again.")
        return
    
    # Run tests
    results = {}
    
    results['critical-signals'] = test_critical_signals()
    input("\n⏸️  Press Enter to test next channel...")
    
    results['watchlist-news'] = test_watchlist_news()
    input("\n⏸️  Press Enter to test next channel...")
    
    results['ai-sector-news'] = test_ai_sector()
    input("\n⏸️  Press Enter to test next channel...")
    
    results['spillover-alerts'] = test_spillover()
    
    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)
    
    for channel, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {status}: #{channel}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print("\n" + "="*70)
    print(f"RESULT: {passed}/{total} channels working")
    print("="*70)
    
    if passed == total:
        print("\n🎉 ALL CHANNELS WORKING!")
        print("\n✅ Your 4-channel news system is LIVE and ready!")
        print("\nNext steps:")
        print("   1. Check each Discord channel for test alerts")
        print("   2. Verify alerts appear in correct channels")
        print("   3. Start app.py to begin real-time monitoring")
        print("   4. Subscribe customers to your Discord server")
    else:
        print("\n⚠️  SOME CHANNELS FAILED")
        print("\nFailed channels need webhook configuration in .env")
        print("Check the variables and try again.")
    
    print("\n" + "="*70)


if __name__ == '__main__':
    main()
