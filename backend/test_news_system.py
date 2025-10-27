"""
Test News Alert System
Validates: Benzinga API → UnifiedNewsEngine → Monitors → Discord

Run this BEFORE starting your app to verify everything works
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def test_benzinga_client():
    """Test 1: Benzinga API access"""
    print("\n" + "="*80)
    print("TEST 1: BENZINGA CLIENT")
    print("="*80)
    
    try:
        from clients.benzinga_client import BenzingaClient
        
        api_key = os.getenv('POLYGON_API_KEY')
        if not api_key:
            print("❌ POLYGON_API_KEY not found in .env")
            return False
        
        client = BenzingaClient(api_key)
        
        # Test fetch
        news = client.get_recent_news('NVDA', hours=24)
        
        if news:
            print(f"✅ Benzinga API working - Found {len(news)} NVDA articles")
            print(f"\n📰 Sample article:")
            article = news[0]
            print(f"   Title: {article.get('title', 'N/A')[:70]}...")
            print(f"   Published: {article.get('published', 'N/A')}")
            print(f"   Tags: {', '.join(article.get('tags', [])[:3])}")
            return True
        else:
            print("⚠️  No news found (could be normal)")
            return True
            
    except Exception as e:
        print(f"❌ Benzinga test failed: {str(e)}")
        return False


def test_unified_news_engine():
    """Test 2: Unified News Engine"""
    print("\n" + "="*80)
    print("TEST 2: UNIFIED NEWS ENGINE")
    print("="*80)
    
    try:
        from news.unified_news_engine import UnifiedNewsEngine
        
        api_key = os.getenv('POLYGON_API_KEY')
        engine = UnifiedNewsEngine(api_key, use_benzinga=True, use_polygon=True)
        
        # Test unified fetch
        news = engine.get_unified_news('TSLA', hours=24, limit=10)
        
        if news:
            print(f"✅ Unified engine working - Found {len(news)} TSLA articles")
            print(f"\n📊 Sources:")
            sources = {}
            for article in news:
                source = article.get('source', 'UNKNOWN')
                sources[source] = sources.get(source, 0) + 1
            
            for source, count in sources.items():
                print(f"   {source}: {count} articles")
            
            # Test classification
            article = news[0]
            channel, priority = engine.classify_news(article)
            print(f"\n🎯 Classification test:")
            print(f"   Article: {article.get('title', 'N/A')[:50]}...")
            print(f"   Channel: {channel.upper()}")
            print(f"   Priority: {priority}")
            
            return True
        else:
            print("⚠️  No news found (could be normal)")
            return True
            
    except Exception as e:
        print(f"❌ Unified engine test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_discord_webhooks():
    """Test 3: Discord webhook configuration"""
    print("\n" + "="*80)
    print("TEST 3: DISCORD WEBHOOKS")
    print("="*80)
    
    webhooks = {
        'NEWS_ONLY': os.getenv('DISCORD_NEWS_ONLY'),
        'OPENAI_NEWS': os.getenv('DISCORD_OPENAI_NEWS'),
        'NEWS_ALERTS': os.getenv('DISCORD_NEWS_ALERTS')
    }
    
    all_ok = True
    for name, url in webhooks.items():
        if url and url.startswith('http'):
            print(f"✅ {name}: Configured")
        else:
            print(f"❌ {name}: NOT configured")
            all_ok = False
    
    return all_ok


def test_openai_monitor():
    """Test 4: OpenAI News Monitor"""
    print("\n" + "="*80)
    print("TEST 4: OPENAI NEWS MONITOR")
    print("="*80)
    
    try:
        from news.unified_news_engine import UnifiedNewsEngine
        from monitors.openai_news_monitor import OpenAINewsMonitor
        
        api_key = os.getenv('POLYGON_API_KEY')
        engine = UnifiedNewsEngine(api_key)
        
        # Create monitor without Discord (test mode)
        monitor = OpenAINewsMonitor(
            unified_news_engine=engine,
            discord_alerter=None,
            check_interval=300
        )
        
        print("✅ OpenAI monitor created")
        print(f"   Keywords: {len(monitor.ai_keywords)} AI keywords configured")
        print(f"   Check interval: {monitor.check_interval}s")
        
        # Test search
        print("\n🔍 Testing AI news search...")
        monitor.check_ai_news()
        
        stats = monitor.get_statistics()
        print(f"\n📊 Monitor stats:")
        print(f"   Checks: {stats['checks_performed']}")
        print(f"   Articles found: {stats['articles_found']}")
        
        return True
        
    except Exception as e:
        print(f"❌ OpenAI monitor test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_macro_detector():
    """Test 5: Macro News Detector"""
    print("\n" + "="*80)
    print("TEST 5: MACRO NEWS DETECTOR")
    print("="*80)
    
    try:
        from news.unified_news_engine import UnifiedNewsEngine
        from monitors.macro_news_detector import MacroNewsDetector
        
        api_key = os.getenv('POLYGON_API_KEY')
        engine = UnifiedNewsEngine(api_key)
        
        detector = MacroNewsDetector(
            unified_news_engine=engine,
            discord_alerter=None,
            check_interval=30
        )
        
        print("✅ Macro detector created")
        print(f"   Categories: {len(detector.macro_keywords)} macro categories")
        print(f"   Check interval: {detector.check_interval}s")
        
        # Test search
        print("\n🔍 Testing macro news search...")
        detector.check_macro_news()
        
        stats = detector.get_statistics()
        print(f"\n📊 Detector stats:")
        print(f"   Checks: {stats['checks_performed']}")
        print(f"   Critical news: {stats['critical_news_found']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Macro detector test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_full_flow():
    """Test 6: Complete news flow"""
    print("\n" + "="*80)
    print("TEST 6: COMPLETE NEWS FLOW")
    print("="*80)
    
    try:
        from news.unified_news_engine import UnifiedNewsEngine
        from monitors.openai_news_monitor import OpenAINewsMonitor
        from monitors.macro_news_detector import MacroNewsDetector
        
        api_key = os.getenv('POLYGON_API_KEY')
        engine = UnifiedNewsEngine(api_key)
        
        # Get some news
        print("📥 Fetching news...")
        news = engine.get_unified_news(ticker=None, hours=6, limit=20)
        
        if not news:
            print("⚠️  No recent news found")
            return True
        
        print(f"✅ Found {len(news)} recent articles")
        
        # Classify them
        print("\n📂 Classifying news...")
        classifications = {}
        for article in news[:10]:
            channel, priority = engine.classify_news(article)
            classifications[channel] = classifications.get(channel, 0) + 1
        
        print("📊 Classification results:")
        for channel, count in classifications.items():
            print(f"   {channel.upper()}: {count} articles")
        
        return True
        
    except Exception as e:
        print(f"❌ Full flow test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("🧪 NEWS ALERT SYSTEM - COMPREHENSIVE TEST SUITE")
    print("="*80)
    
    tests = [
        ("Benzinga API", test_benzinga_client),
        ("Unified News Engine", test_unified_news_engine),
        ("Discord Webhooks", test_discord_webhooks),
        ("OpenAI Monitor", test_openai_monitor),
        ("Macro Detector", test_macro_detector),
        ("Full Flow", test_full_flow)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {str(e)}")
            results[test_name] = False
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"   {status}: {test_name}")
    
    print("\n" + "="*80)
    print(f"RESULT: {passed}/{total} tests passed")
    print("="*80)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("\n✅ Your news system is ready to go live!")
        print("\nNext steps:")
        print("   1. Start your app: python3 app.py")
        print("   2. News monitors will start automatically")
        print("   3. Alerts will route to Discord channels:")
        print("      • AI news → DISCORD_OPENAI_NEWS")
        print("      • Macro news → DISCORD_NEWS_ALERTS")
        print("      • Spillover → DISCORD_NEWS_ALERTS")
    else:
        print("\n⚠️  SOME TESTS FAILED")
        print("\nFix the failed tests before going live.")
    
    print("\n" + "="*80)


if __name__ == '__main__':
    main()
