"""
backend/app.py - COMPLETE VERSION v4.2
INCLUDES: All existing features + 0DTE Gamma Monitor
Nothing stripped - everything preserved!

NEW IN V4.2:
- 0DTE Gamma Level Monitor (9AM EST alerts)
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

# Extended Hours Volume Spike Monitor (Pre-Market + After-Hours)
try:
    from monitors.extended_hours_volume_monitor import ExtendedHoursVolumeMonitor
    EXTENDED_HOURS_MONITOR_AVAILABLE = True
except ImportError:
    EXTENDED_HOURS_MONITOR_AVAILABLE = False
    logging.warning("Extended Hours Volume Monitor not available")

# Real-Time Volume Spike Monitor (Market Hours)
try:
    from monitors.realtime_volume_spike_monitor import RealtimeVolumeSpikeMonitor
    REALTIME_MONITOR_AVAILABLE = True
except ImportError:
    REALTIME_MONITOR_AVAILABLE = False
    logging.warning("Real-Time Volume Monitor not available")

# Momentum Signal Monitor
try:
    from monitors.momentum_signal_monitor import MomentumSignalMonitor
    MOMENTUM_MONITOR_AVAILABLE = True
except ImportError:
    MOMENTUM_MONITOR_AVAILABLE = False
    logging.warning("Momentum Signal Monitor not available")

# 0DTE Gamma Monitor
try:
    from monitors.odte_gamma_monitor import ODTEGammaMonitor
    ODTE_MONITOR_AVAILABLE = True
except ImportError:
    ODTE_MONITOR_AVAILABLE = False
    logging.warning("0DTE Gamma Monitor not available")

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
TRADIER_API_KEY = os.getenv('TRADIER_API_KEY')
TRADIER_ACCOUNT_TYPE = os.getenv('TRADIER_ACCOUNT_TYPE', 'sandbox')

if not POLYGON_API_KEY:
    logger.error("❌ POLYGON_API_KEY not found in .env file!")
    exit(1)

# Initialize analyzer (Phase 1 enhanced)
analyzer = EnhancedProfessionalAnalyzer(
    polygon_api_key=POLYGON_API_KEY,
    twitter_bearer_token=TWITTER_BEARER_TOKEN,
    reddit_client_id=REDDIT_CLIENT_ID,
    reddit_client_secret=REDDIT_CLIENT_SECRET,
    tradier_api_key=TRADIER_API_KEY,
    tradier_account_type=TRADIER_ACCOUNT_TYPE,
    debug_mode=False
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
        
        market_impact_webhook = os.getenv('DISCORD_NEWS_ALERTS')
        if market_impact_webhook:
            market_impact_monitor.set_discord_webhook(market_impact_webhook)
            logger.info("✅ Market Impact Monitor initialized")
        else:
            logger.warning("⚠️ DISCORD_NEWS_ALERTS webhook not configured")
    except Exception as e:
        logger.error(f"❌ Market Impact Monitor failed: {str(e)}")

# Initialize Extended Hours Volume Spike Monitor (Pre-Market + After-Hours)
extended_hours_monitor = None
extended_hours_monitor_thread = None

if EXTENDED_HOURS_MONITOR_AVAILABLE:
    try:
        extended_hours_monitor = ExtendedHoursVolumeMonitor(
            polygon_api_key=POLYGON_API_KEY,
            config=config_yaml,
            watchlist_manager=watchlist_manager
        )
        
        volume_spike_webhook = os.getenv('DISCORD_VOLUME_SPIKE')
        if volume_spike_webhook:
            extended_hours_monitor.set_discord_webhook(volume_spike_webhook)
            logger.info("✅ Extended Hours Volume Monitor initialized")
        else:
            logger.warning("⚠️ DISCORD_VOLUME_SPIKE webhook not configured")
    except Exception as e:
        logger.error(f"❌ Extended Hours Volume Monitor failed: {str(e)}")

# Initialize Real-Time Volume Spike Monitor (Market Hours)
realtime_monitor = None
realtime_monitor_thread = None

if REALTIME_MONITOR_AVAILABLE:
    try:
        realtime_monitor = RealtimeVolumeSpikeMonitor(
            polygon_api_key=POLYGON_API_KEY,
            config=config_yaml,
            watchlist_manager=watchlist_manager
        )
        
        volume_spike_webhook = os.getenv('DISCORD_VOLUME_SPIKE')
        if volume_spike_webhook:
            realtime_monitor.set_discord_webhook(volume_spike_webhook)
            logger.info("✅ Real-Time Volume Monitor initialized")
        else:
            logger.warning("⚠️ DISCORD_VOLUME_SPIKE webhook not configured")
    except Exception as e:
        logger.error(f"❌ Real-Time Volume Monitor failed: {str(e)}")

# Initialize Momentum Signal Monitor
momentum_monitor = None
momentum_monitor_thread = None

if MOMENTUM_MONITOR_AVAILABLE:
    try:
        momentum_monitor = MomentumSignalMonitor(
            polygon_api_key=POLYGON_API_KEY,
            config=config_yaml,
            watchlist_manager=watchlist_manager
        )
        
        momentum_webhook = os.getenv('DISCORD_MOMENTUM_SIGNALS')
        if momentum_webhook:
            momentum_monitor.set_discord_webhook(momentum_webhook)
            logger.info("✅ Momentum Signal Monitor initialized")
        else:
            logger.warning("⚠️ DISCORD_MOMENTUM_SIGNALS webhook not configured")
    except Exception as e:
        logger.error(f"❌ Momentum Signal Monitor failed: {str(e)}")

# Initialize 0DTE Gamma Monitor
odte_monitor = None
odte_monitor_thread = None

if ODTE_MONITOR_AVAILABLE:
    try:
        # Add Tradier keys to config
        config_yaml['tradier_api_key'] = TRADIER_API_KEY
        config_yaml['tradier_account_type'] = TRADIER_ACCOUNT_TYPE
        
        odte_monitor = ODTEGammaMonitor(
            polygon_api_key=POLYGON_API_KEY,
            config=config_yaml,
            watchlist_manager=watchlist_manager
        )
        
        odte_webhook = os.getenv('DISCORD_ODTE_LEVELS')
        if odte_webhook:
            odte_monitor.set_discord_webhook(odte_webhook)
            logger.info("✅ 0DTE Gamma Monitor initialized")
            logger.info(f"   🕐 Alert time: {odte_monitor.alert_time} EST")
            logger.info(f"   📏 Proximity: {odte_monitor.min_proximity_pct}%-{odte_monitor.max_proximity_pct}%")
            logger.info(f"   ⏱️ Alert window: {odte_monitor.alert_window_minutes} minutes")
            logger.info(f"   📅 Weekdays only: {odte_monitor.weekdays_only}")
        else:
            logger.warning("⚠️ DISCORD_ODTE_LEVELS webhook not configured")
    except Exception as e:
        logger.error(f"❌ 0DTE Gamma Monitor failed: {str(e)}")

# Initialize scheduler for Sunday routines
scheduler = BackgroundScheduler()
scheduler.start()

logger.info("=" * 60)
logger.info("🚀 PROFESSIONAL TRADING DASHBOARD v4.2 (WITH 0DTE GAMMA MONITOR)")
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
else:
    logger.info(f"⚠️ Alert System: DISABLED")

if metrics_tracker:
    logger.info(f"✅ Signal Metrics Tracking: ENABLED")
else:
    logger.info(f"⚠️ Signal Metrics Tracking: DISABLED")

if openai_monitor:
    logger.info(f"✅ OpenAI News Monitor: ENABLED")
else:
    logger.info(f"⚠️ OpenAI News Monitor: DISABLED")

if market_impact_monitor:
    logger.info(f"✅ Market Impact Monitor: ENABLED")
else:
    logger.info(f"⚠️ Market Impact Monitor: DISABLED")

if extended_hours_monitor:
    logger.info(f"✅ Extended Hours Volume Monitor: ENABLED")
else:
    logger.info(f"⚠️ Extended Hours Volume Monitor: DISABLED")

if realtime_monitor:
    logger.info(f"✅ Real-Time Volume Monitor: ENABLED")
else:
    logger.info(f"⚠️ Real-Time Volume Monitor: DISABLED")

if momentum_monitor:
    logger.info(f"✅ Momentum Signal Monitor: ENABLED")
else:
    logger.info(f"⚠️ Momentum Signal Monitor: DISABLED")

if odte_monitor:
    logger.info(f"✅ 0DTE Gamma Monitor: ENABLED")
    logger.info(f"   🕐 Alert time: 9:00 AM EST")
    logger.info(f"   📏 Proximity: 1-2% from gamma walls")
else:
    logger.info(f"⚠️ 0DTE Gamma Monitor: DISABLED")

logger.info("=" * 60)


# ============================================================================
# SUNDAY WEEKLY EARNINGS ROUTINE (PRESERVED)
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
# MONITOR BACKGROUND THREADS
# ============================================================================

def run_alert_system():
    """Run alert manager in background thread (Phase 1 enhanced)"""
    if alert_manager:
        logger.info("📢 Starting Phase 1 alert system in background...")
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
        logger.info("🌎 Starting Market Impact monitor in background...")
        try:
            market_impact_monitor.run_continuous()
        except Exception as e:
            logger.error(f"❌ Market Impact monitor error: {str(e)}")


def run_extended_hours_monitor():
    """Run Extended Hours Volume monitor in background thread"""
    if extended_hours_monitor:
        logger.info("🌅 Starting Extended Hours Volume Monitor in background...")
        try:
            extended_hours_monitor.run_continuous()
        except Exception as e:
            logger.error(f"❌ Extended Hours monitor error: {str(e)}")


def run_realtime_monitor():
    """Run Real-Time Volume monitor in background thread"""
    if realtime_monitor:
        logger.info("⚡ Starting Real-Time Volume Monitor in background...")
        try:
            realtime_monitor.run_continuous()
        except Exception as e:
            logger.error(f"❌ Real-Time monitor error: {str(e)}")


def run_momentum_monitor():
    """Run Momentum Signal monitor in background thread"""
    if momentum_monitor:
        logger.info("🎯 Starting Momentum Signal Monitor in background...")
        try:
            momentum_monitor.run_continuous()
        except Exception as e:
            logger.error(f"❌ Momentum monitor error: {str(e)}")


def run_odte_monitor():
    """Run 0DTE Gamma monitor in background thread"""
    if odte_monitor:
        logger.info("🎯 Starting 0DTE Gamma Monitor in background...")
        try:
            odte_monitor.run_continuous()
        except Exception as e:
            logger.error(f"❌ 0DTE monitor error: {str(e)}")


# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route('/')
def index():
    """Serve the dashboard HTML"""
    return send_from_directory(app.static_folder, 'professional_dashboard.html')


@app.route('/api/analyze/<symbol>')
def analyze_symbol(symbol):
    """Analyze a single symbol (Phase 1 enhanced)"""
    try:
        symbol = symbol.upper()
        logger.info(f"Analyzing {symbol} (Phase 1)...")
        
        result = analyzer.generate_professional_signal(symbol)
        
        # PHASE 1: Track signal if metrics enabled
        if metrics_tracker and result.get('alert_type') not in ['MONITOR', None]:
            try:
                signal_id = metrics_tracker.record_signal(result)
                logger.debug(f"📊 Tracked signal: {signal_id}")
            except Exception as e:
                logger.error(f"⚠️ Metrics tracking failed: {str(e)}")
        
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
# EARNINGS MONITORING API ENDPOINTS (PRESERVED)
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
        
        logger.info("🔕 Earnings monitoring disabled via API")
        
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

"""
CONTINUATION OF app.py - Part 3 (FINAL)
All API endpoints + Main section
"""

# ============================================================================
# PHASE 1: SIGNAL METRICS API ENDPOINTS (PRESERVED)
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
# OPENAI MONITOR API ENDPOINTS (PRESERVED)
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
# MARKET IMPACT MONITOR API ENDPOINTS (PRESERVED)
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
# EXTENDED HOURS VOLUME MONITOR API ENDPOINTS (PRESERVED)
# ============================================================================

@app.route('/api/extended-hours-volume/status')
def get_extended_hours_monitor_status():
    """Get Extended Hours Volume monitor status"""
    if not extended_hours_monitor:
        return jsonify({'enabled': False, 'error': 'Monitor not available'}), 503
    
    return jsonify({
        'enabled': extended_hours_monitor.enabled,
        'check_interval': extended_hours_monitor.check_interval,
        'spike_threshold': extended_hours_monitor.spike_threshold,
        'cooldown_minutes': extended_hours_monitor.cooldown_minutes,
        'price_filter': extended_hours_monitor.min_price_change_pct,
        'sessions': ['premarket', 'afterhours'],
        'current_session': extended_hours_monitor.get_current_session(),
        'is_extended_hours': extended_hours_monitor.is_extended_hours(),
        'watchlist_count': len(extended_hours_monitor.watchlist),
        'stats': extended_hours_monitor.stats
    })


@app.route('/api/extended-hours-volume/check', methods=['POST'])
def trigger_extended_hours_check():
    """Manually trigger extended hours volume check"""
    if not extended_hours_monitor:
        return jsonify({'error': 'Monitor not available'}), 503
    
    try:
        alerts_sent = extended_hours_monitor.run_single_check()
        return jsonify({
            'success': True,
            'alerts_sent': alerts_sent,
            'stats': extended_hours_monitor.stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/extended-hours-volume/stats')
def get_extended_hours_stats():
    """Get Extended Hours Volume monitor statistics"""
    if not extended_hours_monitor:
        return jsonify({'error': 'Monitor not available'}), 503
    
    return jsonify(extended_hours_monitor.stats)


# ============================================================================
# REAL-TIME VOLUME MONITOR API ENDPOINTS (PRESERVED)
# ============================================================================

@app.route('/api/realtime-volume/status')
def get_realtime_monitor_status():
    """Get Real-Time Volume monitor status"""
    if not realtime_monitor:
        return jsonify({'enabled': False, 'error': 'Monitor not available'}), 503
    
    return jsonify({
        'enabled': realtime_monitor.enabled,
        'check_interval': realtime_monitor.check_interval,
        'thresholds': realtime_monitor.thresholds,
        'cooldown_minutes': realtime_monitor.cooldown_minutes,
        'price_filter': realtime_monitor.min_price_change_pct,
        'market_hours_only': True,
        'is_market_hours': realtime_monitor.is_market_hours(),
        'watchlist_count': len(realtime_monitor.watchlist),
        'stats': realtime_monitor.stats
    })


@app.route('/api/realtime-volume/check', methods=['POST'])
def trigger_realtime_check():
    """Manually trigger real-time volume check"""
    if not realtime_monitor:
        return jsonify({'error': 'Monitor not available'}), 503
    
    try:
        alerts_sent = realtime_monitor.run_single_check()
        return jsonify({
            'success': True,
            'alerts_sent': alerts_sent,
            'stats': realtime_monitor.stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/realtime-volume/stats')
def get_realtime_stats():
    """Get Real-Time Volume monitor statistics"""
    if not realtime_monitor:
        return jsonify({'error': 'Monitor not available'}), 503
    
    return jsonify(realtime_monitor.stats)


# ============================================================================
# MOMENTUM SIGNAL MONITOR API ENDPOINTS (PRESERVED)
# ============================================================================

@app.route('/api/momentum-signals/status')
def get_momentum_monitor_status():
    """Get Momentum Signal monitor status"""
    if not momentum_monitor:
        return jsonify({'enabled': False, 'error': 'Monitor not available'}), 503
    
    return jsonify({
        'enabled': momentum_monitor.enabled,
        'check_interval': momentum_monitor.check_interval,
        'market_hours_only': momentum_monitor.market_hours_only,
        'min_rvol': momentum_monitor.min_rvol,
        'min_dark_pool_strength': momentum_monitor.min_dark_pool_strength,
        'gamma_wall_distance': momentum_monitor.gamma_wall_distance,
        'cooldowns': momentum_monitor.cooldowns,
        'stats': momentum_monitor.stats
    })


@app.route('/api/momentum-signals/check', methods=['POST'])
def trigger_momentum_check():
    """Manually trigger momentum signal check"""
    if not momentum_monitor:
        return jsonify({'error': 'Monitor not available'}), 503
    
    try:
        alerts_sent = momentum_monitor.run_single_check()
        return jsonify({
            'success': True,
            'alerts_sent': alerts_sent,
            'stats': momentum_monitor.stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/momentum-signals/stats')
def get_momentum_stats():
    """Get Momentum Signal monitor statistics"""
    if not momentum_monitor:
        return jsonify({'error': 'Monitor not available'}), 503
    
    return jsonify(momentum_monitor.stats)


# ============================================================================
# 0DTE GAMMA MONITOR API ENDPOINTS (NEW)
# ============================================================================

@app.route('/api/odte-gamma/status')
def get_odte_monitor_status():
    """Get 0DTE Gamma monitor status"""
    if not odte_monitor:
        return jsonify({'enabled': False, 'error': 'Monitor not available'}), 503
    
    return jsonify({
        'enabled': odte_monitor.enabled,
        'alert_time': odte_monitor.alert_time,
        'alert_window_minutes': odte_monitor.alert_window_minutes,
        'proximity_range': {
            'min_pct': odte_monitor.min_proximity_pct,
            'max_pct': odte_monitor.max_proximity_pct
        },
        'weekdays_only': odte_monitor.weekdays_only,
        'watchlist_only': odte_monitor.watchlist_only,
        'is_alert_time': odte_monitor.is_alert_time(),
        'is_weekday': odte_monitor.is_weekday(),
        'alerted_today': list(odte_monitor.alerted_today),
        'stats': odte_monitor.stats
    })


@app.route('/api/odte-gamma/check', methods=['POST'])
def trigger_odte_check():
    """Manually trigger 0DTE gamma check"""
    if not odte_monitor:
        return jsonify({'error': 'Monitor not available'}), 503
    
    try:
        alerts_sent = odte_monitor.run_single_check()
        return jsonify({
            'success': True,
            'alerts_sent': alerts_sent,
            'stats': odte_monitor.stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/odte-gamma/stats')
def get_odte_stats():
    """Get 0DTE Gamma monitor statistics"""
    if not odte_monitor:
        return jsonify({'error': 'Monitor not available'}), 503
    
    return jsonify(odte_monitor.stats)


@app.route('/api/odte-gamma/test/<symbol>')
def test_odte_symbol(symbol):
    """Test 0DTE detection for specific symbol"""
    if not odte_monitor:
        return jsonify({'error': 'Monitor not available'}), 503
    
    try:
        symbol = symbol.upper()
        
        # Check if 0DTE exists
        odte_exists, gamma_data = odte_monitor.check_odte_exists(symbol)
        
        if not odte_exists:
            return jsonify({
                'symbol': symbol,
                'odte_exists': False,
                'message': 'No 0DTE options found for today'
            })
        
        # Get current price
        quote = odte_monitor.analyzer.get_real_time_quote(symbol)
        current_price = quote['price']
        
        # Check proximity
        alert_data = odte_monitor.check_proximity_to_gamma_walls(
            symbol, current_price, gamma_data
        )
        
        return jsonify({
            'symbol': symbol,
            'odte_exists': True,
            'current_price': current_price,
            'expiration': gamma_data.get('expiration'),
            'hours_until_expiry': gamma_data.get('hours_until_expiry'),
            'gamma_levels': gamma_data.get('gamma_levels', []),
            'proximity_alert': alert_data is not None,
            'proximity_levels': alert_data.get('proximity_levels', []) if alert_data else [],
            'expected_range': gamma_data.get('expected_range', {})
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@app.route('/api/health')
def health_check():
    """
    Health check endpoint (COMPLETE VERSION WITH ALL MONITORS)
    """
    earnings_status = earnings_manager.get_status()
    
    return jsonify({
        'status': 'healthy',
        'version': '4.2-odte-gamma-monitor',
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
            'rr_enforcement': False,
            'dynamic_scan_intervals': True
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
        'extended_hours_volume_monitor': {
            'enabled': extended_hours_monitor is not None,
            'spike_threshold': extended_hours_monitor.spike_threshold if extended_hours_monitor else 0,
            'cooldown_minutes': extended_hours_monitor.cooldown_minutes if extended_hours_monitor else 0,
            'sessions': ['premarket', 'afterhours'],
            'stats': extended_hours_monitor.stats if extended_hours_monitor else {}
        },
        'realtime_volume_monitor': {
            'enabled': realtime_monitor is not None,
            'check_interval': realtime_monitor.check_interval if realtime_monitor else 0,
            'cooldown_minutes': realtime_monitor.cooldown_minutes if realtime_monitor else 0,
            'price_filter': realtime_monitor.min_price_change_pct if realtime_monitor else 0,
            'thresholds': realtime_monitor.thresholds if realtime_monitor else {},
            'stats': realtime_monitor.stats if realtime_monitor else {}
        },
        'momentum_signal_monitor': {
            'enabled': momentum_monitor is not None,
            'check_interval': momentum_monitor.check_interval if momentum_monitor else 0,
            'min_rvol': momentum_monitor.min_rvol if momentum_monitor else 0,
            'triggers': 5 if momentum_monitor else 0,
            'stats': momentum_monitor.stats if momentum_monitor else {}
        },
        'odte_gamma_monitor': {
            'enabled': odte_monitor is not None,
            'alert_time': odte_monitor.alert_time if odte_monitor else None,
            'proximity_range': f"{odte_monitor.min_proximity_pct}-{odte_monitor.max_proximity_pct}%" if odte_monitor else None,
            'is_alert_time': odte_monitor.is_alert_time() if odte_monitor else False,
            'alerted_today': len(odte_monitor.alerted_today) if odte_monitor else 0,
            'stats': odte_monitor.stats if odte_monitor else {}
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
                    'enforcement': False
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
                'extended_hours_volume_monitor': {
                    'enabled': extended_hours_monitor is not None,
                    'spike_threshold': extended_hours_monitor.spike_threshold if extended_hours_monitor else 0,
                    'cooldown_minutes': extended_hours_monitor.cooldown_minutes if extended_hours_monitor else 0
                },
                'realtime_volume_monitor': {
                    'enabled': realtime_monitor is not None,
                    'check_interval': realtime_monitor.check_interval if realtime_monitor else 0,
                    'thresholds': {
                        'elevated': 2.0,
                        'high': 3.0,
                        'extreme': 5.0
                    } if realtime_monitor else {},
                    'cooldown_minutes': realtime_monitor.cooldown_minutes if realtime_monitor else 0,
                    'price_filter': realtime_monitor.min_price_change_pct if realtime_monitor else 0
                },
                'momentum_signal_monitor': {
                    'enabled': momentum_monitor is not None,
                    'check_interval': momentum_monitor.check_interval if momentum_monitor else 0,
                    'triggers': 5 if momentum_monitor else 0
                },
                'odte_gamma_monitor': {
                    'enabled': odte_monitor is not None,
                    'alert_time': odte_monitor.alert_time if odte_monitor else None,
                    'proximity_range': f"{odte_monitor.min_proximity_pct}-{odte_monitor.max_proximity_pct}%" if odte_monitor else None,
                    'weekdays_only': odte_monitor.weekdays_only if odte_monitor else False
                }
            },
            'total_factors': 26
        })
    except Exception as e:
        logger.error(f"Error getting Phase 1 status: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🚀 STARTING PROFESSIONAL TRADING DASHBOARD v4.2")
    print("   (WITH 0DTE GAMMA MONITOR)")
    print("=" * 60)
    print(f"\n📊 Dashboard: http://localhost:5001")
    print(f"🩺 API Health: http://localhost:5001/api/health")
    print(f"📈 Phase 1 Status: http://localhost:5001/api/phase1/status")
    
    # Show earnings status
    earnings_status = earnings_manager.get_status()
    print(f"\n📅 Earnings Monitoring: {'✅ ENABLED' if earnings_status['enabled'] else '🔕 DISABLED'}")
    print(f"📊 Earnings Symbols: {earnings_status['symbols_count']}")
    if earnings_status['symbols']:
        print(f"   {', '.join(earnings_status['symbols'][:5])}" + 
              (f" + {earnings_status['symbols_count'] - 5} more" if earnings_status['symbols_count'] > 5 else ""))
    
    # Schedule Sunday routine
    schedule_sunday_routine()
    
    # Start alert system in background thread
    if alert_manager:
        print(f"\n📢 Starting Phase 1 Alert System...")
        alert_thread = threading.Thread(target=run_alert_system, daemon=True)
        alert_thread.start()
        print(f"   ✅ Alert system started in background")
    
    # Start OpenAI monitor
    if openai_monitor:
        print(f"\n🔍 Starting OpenAI News Monitor...")
        openai_monitor_thread = threading.Thread(target=run_openai_monitor, daemon=True)
        openai_monitor_thread.start()
        print(f"   ✅ OpenAI monitor started in background")
    
    # Start Market Impact monitor
    if market_impact_monitor:
        print(f"\n🌎 Starting Market Impact Monitor...")
        market_impact_thread = threading.Thread(target=run_market_impact_monitor, daemon=True)
        market_impact_thread.start()
        print(f"   ✅ Market Impact monitor started in background")
    
    # Start Extended Hours Volume monitor
    if extended_hours_monitor:
        print(f"\n🌅 Starting Extended Hours Volume Monitor...")
        extended_hours_monitor_thread = threading.Thread(target=run_extended_hours_monitor, daemon=True)
        extended_hours_monitor_thread.start()
        print(f"   ✅ Extended Hours monitor started")
    
    # Start Real-Time Volume monitor
    if realtime_monitor:
        print(f"\n⚡ Starting Real-Time Volume Monitor...")
        realtime_monitor_thread = threading.Thread(target=run_realtime_monitor, daemon=True)
        realtime_monitor_thread.start()
        print(f"   ✅ Real-Time monitor started")
    
    # Start Momentum Signal Monitor
    if momentum_monitor:
        print(f"\n🎯 Starting Momentum Signal Monitor...")
        momentum_monitor_thread = threading.Thread(target=run_momentum_monitor, daemon=True)
        momentum_monitor_thread.start()
        print(f"   ✅ Momentum monitor started in background")
    
    # Start 0DTE Gamma Monitor
    if odte_monitor:
        print(f"\n🎯 Starting 0DTE Gamma Monitor...")
        odte_monitor_thread = threading.Thread(target=run_odte_monitor, daemon=True)
        odte_monitor_thread.start()
        print(f"   ✅ 0DTE monitor started")
        print(f"   🕐 Alert time: {odte_monitor.alert_time} EST")
        print(f"   📏 Proximity: {odte_monitor.min_proximity_pct}%-{odte_monitor.max_proximity_pct}%")
        print(f"   ⏱️ Window: {odte_monitor.alert_window_minutes} minutes")
        print(f"   📬 Routes to: DISCORD_ODTE_LEVELS")
    
    print(f"\n" + "=" * 60)
    print("✅ ALL SYSTEMS ONLINE - READY FOR TRADING!")
    print("=" * 60)
    print(f"\n🎯 NEW: 0DTE Gamma Monitor Active!")
    print(f"   • Alerts at 9:00 AM EST Monday-Friday")
    print(f"   • When price within 1-2% of gamma walls")
    print(f"   • Only when 0DTE options exist")
    print("=" * 60 + "\n")
    
    # Start Flask server
    app.run(host='0.0.0.0', port=5001, debug=False)
# TO BE CONTINUED IN PART 3...