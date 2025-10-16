"""
backend/app.py - COMPLETE VERSION
Your existing features + Phase 1 enhancements + OpenAI Monitor + MARKET IMPACT MONITOR + PRE-MARKET VOLUME MONITOR
Nothing removed, everything enhanced!
"""

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import logging
import threading
import yaml
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from analyzers.enhanced_professional_analyzer import EnhancedProfessionalAnalyzer
from utils.watchlist_manager import WatchlistManager
from utils.earnings_state_manager import EarningsStateManager
from alerts.alert_manager import AlertManager

# PHASE 1: Import new modules
try:
    from utils.signal_metrics import SignalMetricsTracker
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logging.warning("Signal metrics not available")

# OpenAI News Monitor
try:
    from monitors.openai_news_monitor import OpenAINewsMonitor
    OPENAI_MONITOR_AVAILABLE = True
except ImportError:
    OPENAI_MONITOR_AVAILABLE = False
    logging.warning("OpenAI News Monitor not available")

# Market Impact Monitor
try:
    from monitors.market_impact_monitor import MarketImpactMonitor
    MARKET_IMPACT_AVAILABLE = True
except ImportError:
    MARKET_IMPACT_AVAILABLE = False
    logging.warning("Market Impact Monitor not available")

# NEW: Pre-Market Volume Spike Monitor
try:
    from monitors.premarket_volume_monitor import PremarketVolumeMonitor
    PREMARKET_MONITOR_AVAILABLE = True
except ImportError:
    PREMARKET_MONITOR_AVAILABLE = False
    logging.warning("Pre-Market Volume Monitor not available")

load_dotenv()

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load config.yaml
config_yaml = {}
try:
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        config_yaml = yaml.safe_load(f)
    logger.info("✅ config.yaml loaded")
except Exception as e:
    logger.warning(f"⚠️ Failed to load config.yaml: {str(e)}")

# Initialize API keys
POLYGON_API_KEY = os.getenv('POLYGON_API_KEY')
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')

if not POLYGON_API_KEY:
    logger.error("❌ POLYGON_API_KEY not found in .env file!")
    exit(1)

# Initialize analyzer (Phase 1 enhanced)
analyzer = EnhancedProfessionalAnalyzer(
    polygon_api_key=POLYGON_API_KEY,
    twitter_bearer_token=TWITTER_BEARER_TOKEN,
    reddit_client_id=REDDIT_CLIENT_ID,
    reddit_client_secret=REDDIT_CLIENT_SECRET,
    debug_mode=False  # Set to True for detailed logging
)

# Initialize watchlist manager
watchlist_path = os.path.join(os.path.dirname(__file__), 'data', 'watchlist.txt')
watchlist_manager = WatchlistManager(watchlist_file=watchlist_path)

# Initialize earnings state manager
earnings_manager = EarningsStateManager()

# PHASE 1: Initialize Signal Metrics Tracker
metrics_tracker = None
if METRICS_AVAILABLE:
    try:
        metrics_tracker = SignalMetricsTracker()
        logger.info("✅ Signal Metrics Tracker initialized")
    except Exception as e:
        logger.error(f"⚠️ Signal Metrics Tracker failed: {str(e)}")

# Initialize Alert Manager (Phase 1 enhanced)
alert_manager = None
alert_thread = None

try:
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.yaml')
    alert_manager = AlertManager(config_path=config_path, polygon_api_key=POLYGON_API_KEY)
    logger.info("✅ Alert Manager (Phase 1) initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize Alert Manager: {str(e)}")

# Initialize OpenAI News Monitor
openai_monitor = None
openai_monitor_thread = None

if OPENAI_MONITOR_AVAILABLE:
    try:
        openai_monitor = OpenAINewsMonitor(
            polygon_api_key=POLYGON_API_KEY,
            config=config_yaml
        )
        
        # Set Discord webhook
        openai_webhook = os.getenv('DISCORD_OPENAI_NEWS')
        if openai_webhook:
            openai_monitor.set_discord_webhook(openai_webhook)
            logger.info("✅ OpenAI News Monitor initialized")
        else:
            logger.warning("⚠️ DISCORD_OPENAI_NEWS webhook not configured")
    except Exception as e:
        logger.error(f"❌ OpenAI News Monitor failed: {str(e)}")

# Initialize Market Impact Monitor
market_impact_monitor = None
market_impact_thread = None

if MARKET_IMPACT_AVAILABLE:
    try:
        market_impact_monitor = MarketImpactMonitor(
            polygon_api_key=POLYGON_API_KEY,
            config=config_yaml,
            watchlist_manager=watchlist_manager
        )
        
        # Set Discord webhook (DISCORD_NEWS_ALERTS)
        market_impact_webhook = os.getenv('DISCORD_NEWS_ALERTS')
        if market_impact_webhook:
            market_impact_monitor.set_discord_webhook(market_impact_webhook)
            logger.info("✅ Market Impact Monitor initialized")
            logger.info(f"   📊 Monitoring: Macro, M&A, Analyst, Spillover")
            logger.info(f"   🎯 Min RVOL: {market_impact_monitor.min_rvol}x")
        else:
            logger.warning("⚠️ DISCORD_NEWS_ALERTS webhook not configured")
    except Exception as e:
        logger.error(f"❌ Market Impact Monitor failed: {str(e)}")

# NEW: Initialize Pre-Market Volume Spike Monitor
premarket_monitor = None
premarket_monitor_thread = None

if PREMARKET_MONITOR_AVAILABLE:
    try:
        premarket_monitor = PremarketVolumeMonitor(
            polygon_api_key=POLYGON_API_KEY,
            config=config_yaml,
            watchlist_manager=watchlist_manager
        )
        
        # Set Discord webhook
        premarket_webhook = os.getenv('DISCORD_VOLUME_SPIKE')
        if premarket_webhook:
            premarket_monitor.set_discord_webhook(premarket_webhook)
            logger.info("✅ Pre-Market Volume Monitor initialized")
            logger.info(f"   📊 Monitoring: Pre-market + After-hours volume spikes")
            logger.info(f"   ⚡ Spike threshold: {premarket_monitor.spike_threshold}x RVOL")
            logger.info(f"   ⏱️  Cooldown: {premarket_monitor.cooldown_minutes} minutes")
        else:
            logger.warning("⚠️ DISCORD_VOLUME_SPIKE webhook not configured")
    except Exception as e:
        logger.error(f"❌ Pre-Market Volume Monitor failed: {str(e)}")

# Initialize scheduler for Sunday routines
scheduler = BackgroundScheduler()
scheduler.start()

logger.info("=" * 60)
logger.info("🚀 PROFESSIONAL TRADING DASHBOARD v4.0 (PHASE 1 + MARKET IMPACT + PRE-MARKET VOL)")
logger.info("=" * 60)
logger.info(f"✅ Polygon API: ENABLED")
logger.info(f"📂 Watchlist Path: {watchlist_path}")

# Load and display watchlist
try:
    symbols = watchlist_manager.load_symbols()
    logger.info(f"📊 Loaded {len(symbols)} symbols: {', '.join(symbols)}")
except Exception as e:
    logger.error(f"⚠️ Error loading watchlist: {str(e)}")

# Display earnings status
earnings_status = earnings_manager.get_status()
logger.info(f"📅 Earnings Monitoring: {'ENABLED' if earnings_status['enabled'] else 'DISABLED'}")
logger.info(f"📊 Earnings Symbols: {earnings_status['symbols_count']}")

if TWITTER_BEARER_TOKEN:
    logger.info(f"✅ Twitter API: ENABLED")
else:
    logger.info(f"⚠️ Twitter API: DISABLED")

if REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET:
    logger.info(f"✅ Reddit API: ENABLED")
else:
    logger.info(f"⚠️ Reddit API: DISABLED")

if alert_manager:
    logger.info(f"✅ Alert System (Phase 1): ENABLED")
    logger.info(f"   📊 Volume Analysis: ENABLED")
    logger.info(f"   🎯 Key Level Detection: ENABLED")
    logger.info(f"   💰 R:R Enforcement: DISABLED")
else:
    logger.info(f"⚠️ Alert System: DISABLED")

if metrics_tracker:
    logger.info(f"✅ Signal Metrics Tracking: ENABLED")
else:
    logger.info(f"⚠️ Signal Metrics Tracking: DISABLED")

if openai_monitor:
    logger.info(f"✅ OpenAI News Monitor: ENABLED")
    logger.info(f"   📡 Check interval: {openai_monitor.check_interval}s")
    logger.info(f"   📊 Volume confirmation: {'ENABLED' if openai_monitor.volume_enabled else 'DISABLED'}")
    logger.info(f"   🎯 Tech stocks: {len(openai_monitor.tech_stocks)}")
else:
    logger.info(f"⚠️ OpenAI News Monitor: DISABLED")

if market_impact_monitor:
    logger.info(f"✅ Market Impact Monitor: ENABLED")
    logger.info(f"   📡 Check interval: {market_impact_monitor.check_interval}s")
    logger.info(f"   📊 Volume confirmation: {'ENABLED' if market_impact_monitor.volume_enabled else 'DISABLED'}")
    logger.info(f"   🎯 Watchlist stocks: {len(market_impact_monitor.watchlist)}")
    logger.info(f"   🌍 Macro keywords: {len(market_impact_monitor.macro_keywords)}")
    logger.info(f"   🔗 Spillover maps: {len(market_impact_monitor.spillover_map)}")
else:
    logger.info(f"⚠️ Market Impact Monitor: DISABLED")

# NEW: Pre-Market Monitor status
if premarket_monitor:
    logger.info(f"✅ Pre-Market Volume Monitor: ENABLED")
    logger.info(f"   📡 Check interval: {premarket_monitor.check_interval}s")
    logger.info(f"   ⚡ Spike threshold: {premarket_monitor.spike_threshold}x RVOL")
    logger.info(f"   ⏱️  Cooldown: {premarket_monitor.cooldown_minutes}min")
    logger.info(f"   📊 Sessions: Pre-market (4-9:30 AM) + After-hours (4-8 PM)")
    logger.info(f"   📬 Routes to: DISCORD_VOLUME_SPIKE")
else:
    logger.info(f"⚠️ Pre-Market Volume Monitor: DISABLED")

logger.info("=" * 60)


# ============================================================================
# SUNDAY WEEKLY EARNINGS ROUTINE (PRESERVED FROM YOUR VERSION)
# ============================================================================

def get_october_2025_earnings():
    """Get known earnings for October 2025"""
    today = datetime.now()
    
    earnings_by_week = {
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
        43: [
            {'symbol': 'TSLA', 'company': 'Tesla', 'date': 'Oct 23', 'time': 'After Market', 'period': 'Q3'},
            {'symbol': 'IBM', 'company': 'IBM', 'date': 'Oct 23', 'time': 'After Market', 'period': 'Q3'},
            {'symbol': 'T', 'company': 'AT&T', 'date': 'Oct 23', 'time': 'Before Market', 'period': 'Q3'},
            {'symbol': 'KO', 'company': 'Coca-Cola', 'date': 'Oct 23', 'time': 'Before Market', 'period': 'Q3'},
        ],
        44: [
            {'symbol': 'GOOGL', 'company': 'Alphabet', 'date': 'Oct 29', 'time': 'After Market', 'period': 'Q3'},
            {'symbol': 'MSFT', 'company': 'Microsoft', 'date': 'Oct 30', 'time': 'After Market', 'period': 'Q1'},
            {'symbol': 'META', 'company': 'Meta', 'date': 'Oct 30', 'time': 'After Market', 'period': 'Q3'},
            {'symbol': 'AAPL', 'company': 'Apple', 'date': 'Oct 31', 'time': 'After Market', 'period': 'Q4'},
            {'symbol': 'AMZN', 'company': 'Amazon', 'date': 'Oct 31', 'time': 'After Market', 'period': 'Q3'},
        ],
    }
    
    current_week = today.isocalendar()[1]
    this_week = earnings_by_week.get(current_week, [])
    next_week = earnings_by_week.get(current_week + 1, [])
    
    return {
        'this_week': this_week,
        'next_week': next_week,
        'current_week': current_week
    }


def send_earnings_to_discord(earnings_data, watchlist_symbols):
    """Send earnings calendar to Discord"""
    import requests
    
    webhook_url = os.getenv('DISCORD_WEEKLY_EARNINGS')
    
    if not webhook_url:
        logger.warning("⚠️ DISCORD_WEEKLY_EARNINGS not configured")
        return False
    
    today = datetime.now()
    this_week = earnings_data['this_week']
    next_week = earnings_data['next_week']
    all_earnings = this_week + next_week
    
    embed = {
        'title': '📅 Weekly Earnings Calendar - Q3 2025',
        'description': f'Week {earnings_data["current_week"]} | {len(this_week)} companies reporting this week',
        'color': 0x00ff00,
        'timestamp': datetime.utcnow().isoformat(),
        'fields': []
    }
    
    if this_week:
        this_week_text = []
        for e in this_week[:15]:
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
            'value': '🔭 No major companies reporting',
            'inline': False
        })
    
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
    
    embed['footer'] = {
        'text': 'Verify dates at finance.yahoo.com/calendar/earnings'
    }
    
    try:
        payload = {'embeds': [embed]}
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        
        logger.info("✅ Weekly earnings calendar sent to Discord!")
        return True
    
    except Exception as e:
        logger.error(f"❌ Failed to send earnings to Discord: {str(e)}")
        return False


def sunday_earnings_routine():
    """Sunday evening routine - Send calendar AND populate earnings watchlist"""
    logger.info("\n" + "=" * 80)
    logger.info("🗓️ SUNDAY EARNINGS ROUTINE - STARTING")
    logger.info("=" * 80)
    
    try:
        watchlist_symbols = watchlist_manager.load_symbols()
        logger.info(f"📋 Watchlist: {', '.join(watchlist_symbols)}")
        
        earnings_data = get_october_2025_earnings()
        
        this_week = earnings_data['this_week']
        next_week = earnings_data['next_week']
        all_earnings = this_week + next_week
        
        logger.info(f"📊 This week: {len(this_week)} companies")
        logger.info(f"👀 Next week: {len(next_week)} companies")
        
        all_earnings_symbols = [e['symbol'] for e in all_earnings]
        
        earnings_manager.update_earnings_symbols(all_earnings_symbols, {
            'week': earnings_data['current_week'],
            'this_week_count': len(this_week),
            'next_week_count': len(next_week)
        })
        
        logger.info(f"✅ Updated earnings watchlist: {len(all_earnings_symbols)} symbols")
        logger.info(f"   Symbols: {', '.join(all_earnings_symbols)}")
        
        watchlist_earnings = [e for e in all_earnings if e['symbol'] in watchlist_symbols]
        
        if watchlist_earnings:
            logger.info(f"⭐ {len(watchlist_earnings)} watchlist companies have earnings:")
            for e in watchlist_earnings:
                logger.info(f"   • {e['symbol']} - {e['date']}")
        else:
            logger.info("📋 No watchlist companies have earnings this week")
        
        success = send_earnings_to_discord(earnings_data, watchlist_symbols)
        
        if success:
            logger.info("✅ Sunday earnings routine completed successfully")
        else:
            logger.warning("⚠️ Sunday earnings routine completed with warnings")
        
        if alert_manager:
            alert_manager.earnings_manager = EarningsStateManager()
            logger.info("🔄 Alert manager earnings state reloaded")
        
    except Exception as e:
        logger.error(f"❌ Sunday earnings routine failed: {str(e)}")
    
    logger.info("=" * 80 + "\n")


def schedule_sunday_routine():
    """Schedule the Sunday earnings routine"""
    scheduler.add_job(
        sunday_earnings_routine,
        CronTrigger(day_of_week='sun', hour=20, minute=0),
        id='sunday_earnings',
        name='Sunday Weekly Earnings Calendar',
        replace_existing=True
    )
    
    logger.info("📅 Scheduled: Sunday earnings routine (Every Sunday at 8:00 PM)")
    
    if datetime.now().weekday() == 6:
        logger.info("🗓️ It's Sunday! Running earnings routine now...")
        threading.Thread(target=sunday_earnings_routine, daemon=True).start()


# ============================================================================
# ALERT SYSTEM BACKGROUND THREAD (PHASE 1 ENHANCED)
# ============================================================================

def run_alert_system():
    """Run alert manager in background thread (Phase 1 enhanced)"""
    if alert_manager:
        logger.info("📢 Starting Phase 1 alert system in background...")
        logger.info("   ⏱️ Dynamic scan intervals enabled")
        logger.info("   📊 Volume analysis active")
        logger.info("   🎯 Key level detection active")
        try:
            alert_manager.run_continuous()
        except Exception as e:
            logger.error(f"❌ Alert system error: {str(e)}")


def run_openai_monitor():
    """Run OpenAI news monitor in background thread"""
    if openai_monitor:
        logger.info("🔍 Starting OpenAI news monitor in background...")
        try:
            openai_monitor.run_continuous()
        except Exception as e:
            logger.error(f"❌ OpenAI monitor error: {str(e)}")


def run_market_impact_monitor():
    """Run Market Impact monitor in background thread"""
    if market_impact_monitor:
        logger.info("🌍 Starting Market Impact monitor in background...")
        try:
            market_impact_monitor.run_continuous()
        except Exception as e:
            logger.error(f"❌ Market Impact monitor error: {str(e)}")


def run_premarket_monitor():
    """NEW: Run Pre-Market Volume monitor in background thread"""
    if premarket_monitor:
        logger.info("📊 Starting Pre-Market Volume Monitor in background...")
        try:
            premarket_monitor.run_continuous()
        except Exception as e:
            logger.error(f"❌ Pre-Market monitor error: {str(e)}")


# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route('/')
def index():
    """Serve the dashboard HTML"""
    return send_from_directory(app.static_folder, 'professional_dashboard.html')


@app.route('/api/analyze/<symbol>')
def analyze_symbol(symbol):
    """
    Analyze a single symbol (Phase 1 enhanced + DIAGNOSTICS)
    Now includes volume analysis and key level detection with detailed logging
    """
    try:
        symbol = symbol.upper()
        logger.info(f"Analyzing {symbol} (Phase 1 + Diagnostics)...")
        
        result = analyzer.generate_professional_signal(symbol)
        
        # NEW: DIAGNOSTIC LOGGING - Factor Breakdown
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 DIAGNOSTIC BREAKDOWN for {symbol}")
        logger.info(f"{'='*60}")
        logger.info(f"  Bullish Factors: {result.get('bullish_score', 0)}")
        logger.info(f"  Bearish Factors: {result.get('bearish_score', 0)}")
        logger.info(f"  Signal: {result.get('signal', 'None')}")
        logger.info(f"  Alert Type: {result.get('alert_type', 'MONITOR')}")
        logger.info(f"  Confidence: {result.get('confidence', 0):.1f}%")
        
        # NEW: Module Status Check
        logger.info(f"\n  Module Status:")
        logger.info(f"    Volume Analyzer: {'✅ ACTIVE' if analyzer.volume_analyzer else '❌ DISABLED'}")
        logger.info(f"    Key Level Detector: {'✅ ACTIVE' if analyzer.key_level_detector else '❌ DISABLED'}")
        
        # PHASE 1: Log enhanced data
        if result.get('volume_analysis'):
            vol = result['volume_analysis']
            rvol = vol.get('rvol', {})
            logger.info(f"\n  📊 Volume Analysis:")
            logger.info(f"    RVOL: {rvol.get('rvol', 0):.2f}x ({rvol.get('classification', 'N/A')})")
            logger.info(f"    Signal Strength: {rvol.get('signal_strength', 0)}")
            
            if vol.get('volume_spike', {}).get('spike_detected'):
                logger.info(f"    🔥 VOLUME SPIKE DETECTED!")
            
            if vol.get('volume_dryup', {}).get('dryup_detected'):
                logger.info(f"    💧 VOLUME DRY-UP DETECTED!")
        else:
            logger.warning(f"  ⚠️ No volume analysis data returned")
        
        if result.get('key_levels'):
            levels = result['key_levels']
            if 'error' not in levels:
                logger.info(f"\n  🎯 Key Levels:")
                logger.info(f"    Confluence Score: {levels.get('confluence_score', 0)}/10")
                logger.info(f"    At Resistance: {levels.get('at_resistance', False)}")
                logger.info(f"    At Support: {levels.get('at_support', False)}")
                
                if levels.get('confluence_score', 0) >= 7:
                    logger.info(f"    ⚡ HIGH CONFLUENCE DETECTED!")
            else:
                logger.warning(f"  ⚠️ Key level detection error: {levels.get('error')}")
        else:
            logger.warning(f"  ⚠️ No key level data returned")
        
        # NEW: Gap Detection Info
        if result.get('gap_data'):
            gap = result['gap_data']
            if gap.get('gap_type') != 'NO_GAP' and gap.get('gap_type') != 'UNKNOWN':
                logger.info(f"\n  📈 Gap Analysis:")
                logger.info(f"    Type: {gap.get('gap_type')}")
                logger.info(f"    Size: {gap.get('gap_size')}%")
                logger.info(f"    Amount: ${gap.get('gap_amount')}")
        
        # NEW: News Impact Info
        if result.get('news'):
            news = result['news']
            if news.get('news_impact') != 'NONE':
                logger.info(f"\n  📰 News Analysis:")
                logger.info(f"    Sentiment: {news.get('sentiment')}")
                logger.info(f"    Impact: {news.get('news_impact')}")
                logger.info(f"    Urgency: {news.get('urgency')}")
                logger.info(f"    Score: {news.get('sentiment_score')}")
        
        # NEW: Pre-Market RVOL Info
        if result.get('premarket_rvol'):
            pm = result['premarket_rvol']
            if pm.get('rvol', 0) > 0:
                logger.info(f"\n  🌅 Pre-Market RVOL:")
                logger.info(f"    RVOL: {pm.get('rvol', 0):.2f}x ({pm.get('classification', 'N/A')})")
                logger.info(f"    Current Volume: {pm.get('current_volume', 0):,}")
        
        # NEW: R:R Check
        if result.get('entry_targets'):
            et = result['entry_targets']
            if et.get('insufficient_rr'):
                logger.warning(f"\n  ⚠️ SIGNAL FILTERED: R:R {et.get('rr_ratio', 0):.2f} below minimum 2.0")
            else:
                logger.info(f"\n  💰 Entry & Targets:")
                logger.info(f"    R:R Ratio: {et.get('risk_reward', 0):.2f}")
                logger.info(f"    Entry: ${et.get('entry', 0):.2f}")
                logger.info(f"    TP1: ${et.get('tp1', 0):.2f}")
                logger.info(f"    Stop: ${et.get('stop_loss', 0):.2f}")
        
        logger.info(f"{'='*60}\n")
        
        # PHASE 1: Track signal if metrics enabled
        if metrics_tracker and result.get('alert_type') not in ['MONITOR', None]:
            try:
                signal_id = metrics_tracker.record_signal(result)
                logger.debug(f"  📊 Tracked signal: {signal_id}")
            except Exception as e:
                logger.error(f"  ⚠️ Metrics tracking failed: {str(e)}")
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'symbol': symbol,
            'error': str(e),
            'signal': None
        }), 500


@app.route('/api/watchlist')
def get_watchlist():
    """Get current watchlist"""
    try:
        symbols = watchlist_manager.load_symbols()
        logger.info(f"📋 API Request: Returning {len(symbols)} symbols from watchlist")
        return jsonify({
            'symbols': symbols,
            'count': len(symbols),
            'path': watchlist_path
        })
    except Exception as e:
        logger.error(f"Error loading watchlist: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# EARNINGS MONITORING API ENDPOINTS (PRESERVED FROM YOUR VERSION)
# ============================================================================

@app.route('/api/earnings/status')
def get_earnings_status():
    """Get earnings monitoring status"""
    try:
        status = earnings_manager.get_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting earnings status: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/earnings/enable', methods=['POST'])
def enable_earnings():
    """Enable earnings monitoring"""
    try:
        earnings_manager.enable()
        
        if alert_manager:
            alert_manager.earnings_manager = EarningsStateManager()
        
        logger.info("✅ Earnings monitoring enabled via API")
        
        return jsonify({
            'success': True,
            'message': 'Earnings monitoring enabled',
            'status': earnings_manager.get_status()
        })
    except Exception as e:
        logger.error(f"Error enabling earnings: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/earnings/disable', methods=['POST'])
def disable_earnings():
    """Disable earnings monitoring for this week"""
    try:
        earnings_manager.disable()
        
        if alert_manager:
            alert_manager.earnings_manager = EarningsStateManager()
        
        logger.info("📕 Earnings monitoring disabled via API")
        
        return jsonify({
            'success': True,
            'message': 'Earnings monitoring disabled for this week',
            'status': earnings_manager.get_status()
        })
    except Exception as e:
        logger.error(f"Error disabling earnings: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/earnings/symbols')
def get_earnings_symbols():
    """Get list of symbols being monitored for earnings"""
    try:
        symbols = earnings_manager.get_earnings_symbols()
        return jsonify({
            'symbols': symbols,
            'count': len(symbols)
        })
    except Exception as e:
        logger.error(f"Error getting earnings symbols: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/earnings/trigger', methods=['POST'])
def trigger_sunday_routine():
    """Manually trigger the Sunday earnings routine"""
    try:
        logger.info("🔄 Manually triggering Sunday earnings routine...")
        threading.Thread(target=sunday_earnings_routine, daemon=True).start()
        return jsonify({
            'message': 'Sunday earnings routine triggered',
            'status': 'running'
        })
    except Exception as e:
        logger.error(f"Error triggering routine: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/earnings/schedule')
def get_earnings_schedule():
    """Get the next scheduled Sunday routine"""
    try:
        job = scheduler.get_job('sunday_earnings')
        if job:
            next_run = job.next_run_time
            return jsonify({
                'scheduled': True,
                'next_run': next_run.isoformat() if next_run else None,
                'job_name': job.name,
                'trigger': 'Every Sunday at 8:00 PM'
            })
        else:
            return jsonify({'scheduled': False})
    except Exception as e:
        logger.error(f"Error getting schedule: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# PHASE 1: SIGNAL METRICS API ENDPOINTS
# ============================================================================

@app.route('/api/metrics/winrate')
def get_win_rate():
    """Get win rate statistics (Phase 1)"""
    try:
        if not metrics_tracker:
            return jsonify({'error': 'Metrics tracking not enabled'}), 503
        
        days = int(request.args.get('days', 7))
        stats = metrics_tracker.get_win_rate(days=days)
        
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting win rate: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/metrics/report')
def get_metrics_report():
    """Get formatted metrics report (Phase 1)"""
    try:
        if not metrics_tracker:
            return jsonify({'error': 'Metrics tracking not enabled'}), 503
        
        days = int(request.args.get('days', 7))
        report = metrics_tracker.generate_report(days=days)
        
        return jsonify({
            'report': report,
            'days': days
        })
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/metrics/symbol/<symbol>')
def get_symbol_performance(symbol):
    """Get performance for specific symbol (Phase 1)"""
    try:
        if not metrics_tracker:
            return jsonify({'error': 'Metrics tracking not enabled'}), 503
        
        symbol = symbol.upper()
        stats = metrics_tracker.get_performance_by_symbol(symbol)
        
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting symbol performance: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# OPENAI MONITOR API ENDPOINTS
# ============================================================================

@app.route('/api/openai/status')
def get_openai_monitor_status():
    """Get OpenAI monitor status"""
    if not openai_monitor:
        return jsonify({'enabled': False, 'error': 'Monitor not available'}), 503
    
    return jsonify({
        'enabled': openai_monitor.enabled,
        'check_interval': openai_monitor.check_interval,
        'volume_confirmation': openai_monitor.volume_enabled,
        'min_rvol': openai_monitor.min_rvol,
        'tech_stocks_count': len(openai_monitor.tech_stocks),
        'keywords': openai_monitor.keywords,
        'stats': openai_monitor.stats
    })


@app.route('/api/openai/check', methods=['POST'])
def trigger_openai_check():
    """Manually trigger OpenAI news check"""
    if not openai_monitor:
        return jsonify({'error': 'Monitor not available'}), 503
    
    try:
        alerts_sent = openai_monitor.run_single_check()
        return jsonify({
            'success': True,
            'alerts_sent': alerts_sent,
            'stats': openai_monitor.stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/openai/stats')
def get_openai_stats():
    """Get OpenAI monitor statistics"""
    if not openai_monitor:
        return jsonify({'error': 'Monitor not available'}), 503
    
    return jsonify(openai_monitor.stats)


# ============================================================================
# MARKET IMPACT MONITOR API ENDPOINTS
# ============================================================================

@app.route('/api/market-impact/status')
def get_market_impact_status():
    """Get Market Impact monitor status"""
    if not market_impact_monitor:
        return jsonify({'enabled': False, 'error': 'Monitor not available'}), 503
    
    return jsonify({
        'enabled': market_impact_monitor.enabled,
        'check_interval': market_impact_monitor.check_interval,
        'volume_confirmation': market_impact_monitor.volume_enabled,
        'min_rvol': market_impact_monitor.min_rvol,
        'watchlist_count': len(market_impact_monitor.watchlist),
        'macro_keywords': len(market_impact_monitor.macro_keywords),
        'spillover_maps': len(market_impact_monitor.spillover_map),
        'stats': market_impact_monitor.stats
    })


@app.route('/api/market-impact/check', methods=['POST'])
def trigger_market_impact_check():
    """Manually trigger market impact news check"""
    if not market_impact_monitor:
        return jsonify({'error': 'Monitor not available'}), 503
    
    try:
        alerts_sent = market_impact_monitor.run_single_check()
        return jsonify({
            'success': True,
            'alerts_sent': alerts_sent,
            'stats': market_impact_monitor.stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/market-impact/stats')
def get_market_impact_stats():
    """Get Market Impact monitor statistics"""
    if not market_impact_monitor:
        return jsonify({'error': 'Monitor not available'}), 503
    
    return jsonify(market_impact_monitor.stats)


# ============================================================================
# NEW: PRE-MARKET VOLUME SPIKE MONITOR API ENDPOINTS
# ============================================================================

@app.route('/api/premarket-volume/status')
def get_premarket_monitor_status():
    """Get Pre-Market Volume monitor status"""
    if not premarket_monitor:
        return jsonify({'enabled': False, 'error': 'Monitor not available'}), 503
    
    return jsonify({
        'enabled': premarket_monitor.enabled,
        'check_interval': premarket_monitor.check_interval,
        'spike_threshold': premarket_monitor.spike_threshold,
        'cooldown_minutes': premarket_monitor.cooldown_minutes,
        'watchlist_count': len(premarket_monitor.watchlist),
        'current_session': premarket_monitor.get_current_session(),
        'is_extended_hours': premarket_monitor.is_extended_hours(),
        'stats': premarket_monitor.stats
    })


@app.route('/api/premarket-volume/check', methods=['POST'])
def trigger_premarket_check():
    """Manually trigger pre-market volume check"""
    if not premarket_monitor:
        return jsonify({'error': 'Monitor not available'}), 503
    
    try:
        alerts_sent = premarket_monitor.run_single_check()
        return jsonify({
            'success': True,
            'alerts_sent': alerts_sent,
            'stats': premarket_monitor.stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/premarket-volume/stats')
def get_premarket_stats():
    """Get Pre-Market Volume monitor statistics"""
    if not premarket_monitor:
        return jsonify({'error': 'Monitor not available'}), 503
    
    return jsonify(premarket_monitor.stats)


# ============================================================================
# DIAGNOSTIC API ENDPOINTS
# ============================================================================

@app.route('/api/diagnostics/test/<symbol>')
def diagnostic_test(symbol):
    """
    NEW: Run comprehensive diagnostic test on a symbol
    Returns detailed breakdown of why signal did/didn't trigger
    """
    try:
        symbol = symbol.upper()
        result = analyzer.generate_professional_signal(symbol)
        
        # Build diagnostic report
        diagnostic = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'signal_generated': result.get('signal') is not None,
            'alert_type': result.get('alert_type', 'MONITOR'),
            'factor_scores': {
                'bullish': result.get('bullish_score', 0),
                'bearish': result.get('bearish_score', 0),
                'threshold': 8
            },
            'modules_status': {
                'volume_analyzer': analyzer.volume_analyzer is not None,
                'key_level_detector': analyzer.key_level_detector is not None,
            },
            'data_quality': {
                'has_volume_data': bool(result.get('volume_analysis')),
                'has_key_levels': bool(result.get('key_levels') and 'error' not in result.get('key_levels', {})),
                'has_news': bool(result.get('news') and result['news'].get('news_impact') != 'NONE'),
                'has_gap': result.get('gap_data', {}).get('gap_type') not in ['NO_GAP', 'UNKNOWN']
            },
            'filter_reasons': []
        }
        
        # Check why signal might have been filtered
        if result.get('entry_targets', {}).get('insufficient_rr'):
            diagnostic['filter_reasons'].append(
                f"R:R ratio {result['entry_targets'].get('rr_ratio', 0):.2f} below minimum 2.0"
            )
        
        if result.get('bullish_score', 0) < 8 and result.get('bearish_score', 0) < 8:
            diagnostic['filter_reasons'].append(
                f"Factor scores below threshold (need 8, got B:{result.get('bullish_score', 0)} / S:{result.get('bearish_score', 0)})"
            )
        
        # Near-miss detection
        diagnostic['near_miss'] = (
            result.get('bullish_score', 0) >= 5 or result.get('bearish_score', 0) >= 5
        ) and not result.get('signal')
        
        if diagnostic['near_miss']:
            diagnostic['near_miss_details'] = {
                'message': 'Signal was close to triggering but filtered',
                'needed': 8 - max(result.get('bullish_score', 0), result.get('bearish_score', 0)),
                'suggestion': 'Consider lowering threshold to 6 for more alerts'
            }
        
        return jsonify(diagnostic)
        
    except Exception as e:
        logger.error(f"Diagnostic test failed for {symbol}: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/diagnostics/watchlist-scan')
def diagnostic_watchlist_scan():
    """
    NEW: Scan entire watchlist and show near-miss signals
    Helps identify if threshold is too high
    """
    try:
        symbols = watchlist_manager.load_symbols()
        results = []
        
        for symbol in symbols:
            try:
                result = analyzer.generate_professional_signal(symbol)
                
                bullish = result.get('bullish_score', 0)
                bearish = result.get('bearish_score', 0)
                max_score = max(bullish, bearish)
                
                # Include if it's a signal OR a near-miss (5+ factors)
                if max_score >= 5:
                    results.append({
                        'symbol': symbol,
                        'bullish_score': bullish,
                        'bearish_score': bearish,
                        'triggered': result.get('signal') is not None,
                        'alert_type': result.get('alert_type', 'MONITOR'),
                        'near_miss': max_score >= 5 and max_score < 8,
                        'needed_factors': 8 - max_score if max_score < 8 else 0
                    })
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {str(e)}")
                continue
        
        # Sort by score
        results.sort(key=lambda x: max(x['bullish_score'], x['bearish_score']), reverse=True)
        
        summary = {
            'total_scanned': len(symbols),
            'signals_triggered': sum(1 for r in results if r['triggered']),
            'near_misses': sum(1 for r in results if r['near_miss']),
            'results': results
        }
        
        return jsonify(summary)
        
    except Exception as e:
        logger.error(f"Watchlist scan failed: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/health')
def health_check():
    """
    Health check endpoint (Phase 1 enhanced + DIAGNOSTICS + MARKET IMPACT + PRE-MARKET VOL)
    """
    earnings_status = earnings_manager.get_status()
    
    return jsonify({
        'status': 'healthy',
        'version': '4.0-phase1-market-impact-premarket-vol',
        'polygon_enabled': bool(POLYGON_API_KEY),
        'alerts_enabled': alert_manager is not None,
        'earnings_monitoring': {
            'enabled': earnings_status['enabled'],
            'symbols_count': earnings_status['symbols_count'],
            'week_number': earnings_status['week_number']
        },
        'sunday_routine_enabled': scheduler.get_job('sunday_earnings') is not None,
        'watchlist_path': watchlist_path,
        'phase1_features': {
            'volume_analysis': analyzer.volume_analyzer is not None,
            'key_level_detection': analyzer.key_level_detector is not None,
            'signal_metrics': metrics_tracker is not None,
            'rr_enforcement': False,  # Disabled per user request
            'dynamic_scan_intervals': True
        },
        'diagnostics': {
            'enabled': True,
            'endpoints': [
                '/api/diagnostics/test/<symbol>',
                '/api/diagnostics/watchlist-scan'
            ]
        },
        'alert_stats': alert_manager.stats if alert_manager else None,
        'openai_monitor': {
            'enabled': openai_monitor is not None,
            'volume_confirmation': openai_monitor.volume_enabled if openai_monitor else False,
            'stats': openai_monitor.stats if openai_monitor else {}
        },
        'market_impact_monitor': {
            'enabled': market_impact_monitor is not None,
            'volume_confirmation': market_impact_monitor.volume_enabled if market_impact_monitor else False,
            'watchlist_count': len(market_impact_monitor.watchlist) if market_impact_monitor else 0,
            'stats': market_impact_monitor.stats if market_impact_monitor else {}
        },
        'premarket_volume_monitor': {
            'enabled': premarket_monitor is not None,
            'spike_threshold': premarket_monitor.spike_threshold if premarket_monitor else 0,
            'cooldown_minutes': premarket_monitor.cooldown_minutes if premarket_monitor else 0,
            'stats': premarket_monitor.stats if premarket_monitor else {}
        }
    })


@app.route('/api/phase1/status')
def phase1_status():
    """Get Phase 1 feature status"""
    try:
        return jsonify({
            'phase1_enabled': True,
            'features': {
                'volume_analyzer': {
                    'enabled': analyzer.volume_analyzer is not None,
                    'rvol_threshold': 2.0,
                    'spike_threshold': 1.5
                },
                'key_level_detector': {
                    'enabled': analyzer.key_level_detector is not None,
                    'confluence_scoring': True,
                    'min_confluence': 6
                },
                'risk_management': {
                    'min_rr': 2.0,
                    'enforcement': False  # Disabled
                },
                'signal_metrics': {
                    'enabled': metrics_tracker is not None,
                    'tracking': True
                },
                'dynamic_scanning': {
                    'enabled': True,
                    'first_hour_interval': 60,
                    'midday_interval': 120
                },
                'openai_monitor': {
                    'enabled': openai_monitor is not None,
                    'volume_confirmation': openai_monitor.volume_enabled if openai_monitor else False
                },
                'market_impact_monitor': {
                    'enabled': market_impact_monitor is not None,
                    'volume_confirmation': market_impact_monitor.volume_enabled if market_impact_monitor else False,
                    'min_rvol': market_impact_monitor.min_rvol if market_impact_monitor else 0
                },
                'premarket_volume_monitor': {
                    'enabled': premarket_monitor is not None,
                    'spike_threshold': premarket_monitor.spike_threshold if premarket_monitor else 0,
                    'cooldown_minutes': premarket_monitor.cooldown_minutes if premarket_monitor else 0
                }
            },
            'total_factors': 26
        })
    except Exception as e:
        logger.error(f"Error getting Phase 1 status: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🚀 STARTING PROFESSIONAL TRADING DASHBOARD v4.0")
    print("   (PHASE 1 + DIAGNOSTICS + MARKET IMPACT + PRE-MARKET VOL)")
    print("=" * 60)
    print(f"\n📊 Dashboard: http://localhost:5001")
    print(f"🩺 API Health: http://localhost:5001/api/health")
    print(f"📈 Phase 1 Status: http://localhost:5001/api/phase1/status")
    
    # Show earnings status
    earnings_status = earnings_manager.get_status()
    print(f"\n📅 Earnings Monitoring: {'✅ ENABLED' if earnings_status['enabled'] else '📕 DISABLED'}")
    print(f"📊 Earnings Symbols: {earnings_status['symbols_count']}")
    if earnings_status['symbols']:
        print(f"   {', '.join(earnings_status['symbols'][:5])}" + 
              (f" + {earnings_status['symbols_count'] - 5} more" if earnings_status['symbols_count'] > 5 else ""))
    
    # PHASE 1: Show enhanced features
    print(f"\n🚀 PHASE 1 FEATURES:")
    print(f"   ✅ Volume Analysis (RVOL, spikes, dry-ups)")
    print(f"   ✅ Key Level Detection (confluence scoring)")
    print(f"   ✅ 1:2 R:R Enforcement: DISABLED")
    print(f"   ✅ Signal Metrics Tracking")
    print(f"   ✅ Dynamic Scan Intervals (60s first hour, 120s midday)")
    print(f"   ✅ 26 Total Factors (was 15)")
    
    # OpenAI Monitor status
    if openai_monitor:
        print(f"\n🔍 OpenAI News Monitor: ENABLED")
        print(f"   📡 Check interval: {openai_monitor.check_interval}s")
        print(f"   📊 Volume confirmation: {'ENABLED' if openai_monitor.volume_enabled else 'DISABLED'}")
        print(f"   🎯 Tech stocks: {len(openai_monitor.tech_stocks)}")
        print(f"   ⚡ Min RVOL: {openai_monitor.min_rvol}x")
    
    # Market Impact Monitor status
    if market_impact_monitor:
        print(f"\n🌍 Market Impact Monitor: ENABLED")
        print(f"   📡 Check interval: {market_impact_monitor.check_interval}s")
        print(f"   📊 Volume confirmation: {'ENABLED' if market_impact_monitor.volume_enabled else 'DISABLED'}")
        print(f"   🎯 Watchlist stocks: {len(market_impact_monitor.watchlist)}")
        print(f"   🌍 Macro keywords: {len(market_impact_monitor.macro_keywords)}")
        print(f"   🔗 Spillover maps: {len(market_impact_monitor.spillover_map)}")
        print(f"   ⚡ Min RVOL: {market_impact_monitor.min_rvol}x")
        print(f"   📬 Routes to: DISCORD_NEWS_ALERTS")
    
    # NEW: Pre-Market Monitor status
    if premarket_monitor:
        print(f"\n📊 Pre-Market Volume Monitor: ENABLED")
        print(f"   📡 Check interval: {premarket_monitor.check_interval}s")
        print(f"   ⚡ Spike threshold: {premarket_monitor.spike_threshold}x RVOL")
        print(f"   ⏱️  Cooldown: {premarket_monitor.cooldown_minutes}min")
        print(f"   📊 Sessions: Pre-market (4-9:30 AM) + After-hours (4-8 PM)")
        print(f"   📬 Routes to: DISCORD_VOLUME_SPIKE")
    
    # Alert system status
    if alert_manager:
        print(f"\n✅ Alert System (Phase 1): ENABLED")
        print(f"   📢 Discord: {'ENABLED' if alert_manager.discord else 'DISABLED'}")
        
        alert_thread = threading.Thread(target=run_alert_system, daemon=True)
        alert_thread.start()
        print(f"\n📢 Phase 1 alert system started in background")
        print(f"   ⏱️ First Hour: 60s intervals")
        print(f"   ⏱️ Mid-Day: 120s intervals")
        
        # Check if alert thread is running
        import time
        time.sleep(1)
        if alert_thread.is_alive():
            print(f"   ✅ Alert thread is RUNNING")
        else:
            print(f"   ❌ Alert thread FAILED to start")
    
    # Start OpenAI Monitor
    if openai_monitor:
        print(f"\n🔍 Starting OpenAI News Monitor...")
        openai_monitor_thread = threading.Thread(target=run_openai_monitor, daemon=True)
        openai_monitor_thread.start()
        print(f"   ✅ OpenAI monitor started in background")
        print(f"   📡 Checking every {openai_monitor.check_interval}s")
        print(f"   📊 Monitoring {len(openai_monitor.tech_stocks)} tech stocks")
    
    # Start Market Impact Monitor
    if market_impact_monitor:
        print(f"\n🌍 Starting Market Impact Monitor...")
        market_impact_thread = threading.Thread(target=run_market_impact_monitor, daemon=True)
        market_impact_thread.start()
        print(f"   ✅ Market Impact monitor started in background")
        print(f"   📡 Checking every {market_impact_monitor.check_interval}s")
        print(f"   📊 Monitoring: Macro, M&A, Analyst, Spillover")
        print(f"   📬 Alerts to: DISCORD_NEWS_ALERTS")
    
    # NEW: Start Pre-Market Volume Monitor
    if premarket_monitor:
        print(f"\n📊 Starting Pre-Market Volume Spike Monitor...")
        premarket_monitor_thread = threading.Thread(target=run_premarket_monitor, daemon=True)
        premarket_monitor_thread.start()
        print(f"   ✅ Pre-Market monitor started in background")
        print(f"   📡 Checking every {premarket_monitor.check_interval}s")
        print(f"   📊 Monitoring: Pre-market (4-9:30 AM) + After-hours (4-8 PM)")
        print(f"   ⚡ Spike threshold: {premarket_monitor.spike_threshold}x RVOL")
        print(f"   📬 Alerts to: DISCORD_VOLUME_SPIKE")
    
    # Metrics tracker status
    if metrics_tracker:
        print(f"\n📊 Signal Metrics: ENABLED")
        print(f"   📈 View at: http://localhost:5001/api/metrics/winrate?days=7")
    
    # Schedule Sunday routine
    schedule_sunday_routine()
    print(f"\n🗓️ Sunday Routine: ENABLED")
    print(f"   📅 Schedule: Every Sunday at 8:00 PM")
    print(f"   📢 Updates earnings watchlist + sends Discord calendar")
    
    if datetime.now().weekday() == 6:
        print(f"   ✨ It's Sunday! Routine will run shortly...")
    
    # NEW: Diagnostic endpoints
    print(f"\n🔍 DIAGNOSTIC ENDPOINTS:")
    print(f"   http://localhost:5001/api/diagnostics/test/NVDA")
    print(f"   http://localhost:5001/api/diagnostics/watchlist-scan")
    print(f"   http://localhost:5001/api/market-impact/status")
    print(f"   http://localhost:5001/api/market-impact/check (POST)")
    print(f"   http://localhost:5001/api/premarket-volume/status")
    print(f"   http://localhost:5001/api/premarket-volume/check (POST)")
    
    print("\n" + "=" * 60)
    print("Press CTRL+C to stop")
    print("=" * 60 + "\n")
    
    app.run(host='0.0.0.0', port=5001, debug=False)