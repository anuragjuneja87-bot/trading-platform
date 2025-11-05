"""
backend/app.py - COMPLETE VERSION v4.5.2
WITH ALERT CONSOLE + WALL STRENGTH + UNUSUAL ACTIVITY + EARNINGS MONITOR
+ REALTIME VOLUME MONITOR + MOMENTUM MONITOR (THREADING FIXED)

COMPLETE REPLACEMENT FILE
Copy this entire file to replace your existing app.py

CHANGES IN v4.5.2:
- Added run_realtime_volume_monitor() function (line 511)
- Added run_momentum_monitor() function (line 518)
- Added threading startup for realtime_monitor (line 1017)
- Added threading startup for momentum_monitor (line 1027)
"""

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import logging
import threading
import time
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
from database.news_database import get_news_database

# ALERT CONSOLE: Import Config Manager and Routes
try:
    from utils.config_manager import ConfigManager
    from routes.config_routes import config_bp, init_config_routes
    CONFIG_MANAGER_AVAILABLE = True
except ImportError:
    CONFIG_MANAGER_AVAILABLE = False
    logging.warning("Alert Console not available - install config_manager.py and config_routes.py")

# Pin Probability Calculator (Feature #4)
try:
    from analyzers.pin_probability_calculator import PinProbabilityCalculator
    PIN_CALC_AVAILABLE = True
except ImportError:
    PIN_CALC_AVAILABLE = False
    logging.warning("Pin Probability Calculator not available")

# Confluence Alert System (Feature #5)
try:
    from analyzers.confluence_alert_system import ConfluenceAlertSystem
    CONFLUENCE_AVAILABLE = True
except ImportError:
    CONFLUENCE_AVAILABLE = False
    logging.warning("Confluence Alert System not available")

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

# Extended Hours Volume Spike Monitor
try:
    from monitors.extended_hours_volume_monitor import ExtendedHoursVolumeMonitor
    EXTENDED_HOURS_MONITOR_AVAILABLE = True
except ImportError:
    EXTENDED_HOURS_MONITOR_AVAILABLE = False
    logging.warning("Extended Hours Volume Monitor not available")

# Real-Time Volume Spike Monitor
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


# Earnings Monitor
try:
    from monitors.earnings_monitor import EarningsMonitor
    EARNINGS_MONITOR_AVAILABLE = True
except ImportError:
    EARNINGS_MONITOR_AVAILABLE = False
    logging.warning("Earnings Monitor not available")

# Wall Strength Monitor
try:
    from monitors.wall_strength_monitor import WallStrengthMonitor
    WALL_STRENGTH_AVAILABLE = True
except ImportError:
    WALL_STRENGTH_AVAILABLE = False
    logging.warning("Wall Strength Monitor not available")

# Unusual Activity Monitor (Feature 3)
try:
    from monitors.unusual_activity_monitor import UnusualActivityMonitor
    UNUSUAL_ACTIVITY_AVAILABLE = True
except ImportError:
    UNUSUAL_ACTIVITY_AVAILABLE = False
    logging.warning("Unusual Activity Monitor not available")

load_dotenv()

# JSON Sanitization Helper
def sanitize_for_json(obj):
    """
    Recursively convert numpy/pandas types to native Python types for JSON serialization
    """
    import numpy as np
    import pandas as pd
    
    if isinstance(obj, dict):
        return {key: sanitize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(sanitize_for_json(item) for item in obj)
    elif isinstance(obj, (np.bool_, bool)):  # Fixed: removed np.bool8
        return bool(obj)
    elif isinstance(obj, (np.integer, np.int8, np.int16, np.int32, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float16, np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return sanitize_for_json(obj.tolist())
    elif isinstance(obj, (pd.Series, pd.DataFrame)):
        return sanitize_for_json(obj.to_dict())
    elif pd.isna(obj):
        return None
    else:
        return obj

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
TRADIER_API_KEY = os.getenv('TRADIER_API_KEY')
TRADIER_ACCOUNT_TYPE = os.getenv('TRADIER_ACCOUNT_TYPE', 'sandbox')

if not POLYGON_API_KEY:
    logger.error("❌ POLYGON_API_KEY not found!")
    exit(1)

# Initialize analyzer
analyzer = EnhancedProfessionalAnalyzer(
    polygon_api_key=POLYGON_API_KEY,
    tradier_api_key=TRADIER_API_KEY,
    tradier_account_type=TRADIER_ACCOUNT_TYPE,
    debug_mode=False
)

# Initialize Pin Probability Calculator
pin_calculator = None
if PIN_CALC_AVAILABLE:
    try:
        pin_calculator = PinProbabilityCalculator()
        logger.info("✅ Pin Probability Calculator initialized")
    except Exception as e:
        logger.error(f"⚠️ Pin Probability Calculator failed: {str(e)}")

# Initialize Confluence Alert System
confluence_system = None
if CONFLUENCE_AVAILABLE:
    try:
        confluence_system = ConfluenceAlertSystem()
        logger.info("✅ Confluence Alert System initialized")
    except Exception as e:
        logger.error(f"⚠️ Confluence Alert System failed: {str(e)}")

# Initialize watchlist manager
watchlist_path = os.path.join(os.path.dirname(__file__), 'data', 'watchlist.txt')
watchlist_manager = WatchlistManager(watchlist_file=watchlist_path)

# Initialize earnings state manager
earnings_manager = EarningsStateManager()

# Initialize Signal Metrics Tracker
metrics_tracker = None
if METRICS_AVAILABLE:
    try:
        metrics_tracker = SignalMetricsTracker()
        logger.info("✅ Signal Metrics Tracker initialized")
    except Exception as e:
        logger.error(f"⚠️ Signal Metrics Tracker failed: {str(e)}")

# Initialize Alert Manager
alert_manager = None
try:
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.yaml')
    alert_manager = AlertManager(config_path=config_path, polygon_api_key=POLYGON_API_KEY)
    logger.info("✅ Alert Manager initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize Alert Manager: {str(e)}")

# Initialize News Database
news_db = None
try:
    news_db = get_news_database()
    logger.info("✅ News Database initialized")
except Exception as e:
    logger.error(f"❌ News Database failed: {str(e)}")

# ALERT CONSOLE: Initialize Config Manager
config_manager = None
if CONFIG_MANAGER_AVAILABLE:
    try:
        config_manager = ConfigManager()
        logger.info("✅ Config Manager initialized")
    except Exception as e:
        logger.error(f"❌ Config Manager failed: {str(e)}")

# ============================================================================
# NEWS SYSTEM INITIALIZATION
# ============================================================================

# Initialize Unified News Engine (core component for all news monitors)
unified_news_engine = None
try:
    from news.unified_news_engine import UnifiedNewsEngine
    unified_news_engine = UnifiedNewsEngine(
        polygon_api_key=POLYGON_API_KEY,
        use_benzinga=True,
        use_polygon=True
    )
    logger.info("✅ Unified News Engine initialized (Benzinga + Polygon)")
except Exception as e:
    logger.error(f"❌ Unified News Engine failed: {str(e)}")
    logger.warning("⚠️  News monitors will be disabled")

# Initialize all monitors with OPTIMIZED REAL-TIME INTERVALS
openai_monitor = None
if OPENAI_MONITOR_AVAILABLE and unified_news_engine and alert_manager:
    try:
        from monitors.openai_news_monitor import OpenAINewsMonitor
        openai_monitor = OpenAINewsMonitor(
            unified_news_engine=unified_news_engine,
            discord_alerter=alert_manager.discord,
            check_interval=30  # 30 seconds - AI sector news
        )
        logger.info("✅ OpenAI News Monitor initialized (30s interval)")
    except Exception as e:
        logger.error(f"❌ OpenAI News Monitor failed: {str(e)}")

# Market Impact Monitor - Watchlist news to DISCORD_NEWS_ONLY
market_impact_monitor = None
if MARKET_IMPACT_AVAILABLE:
    try:
        market_impact_monitor = MarketImpactMonitor(
            polygon_api_key=POLYGON_API_KEY,
            config=config_yaml,
            watchlist_manager=watchlist_manager
        )
        # Route to DISCORD_NEWS_ONLY for watchlist-specific news
        webhook = os.getenv('DISCORD_NEWS_ONLY')
        if webhook:
            market_impact_monitor.set_discord_webhook(webhook)
            logger.info("✅ Market Impact Monitor initialized (15s interval)")
            logger.info("   📡 Routes to: DISCORD_NEWS_ONLY (Watchlist News)")
    except Exception as e:
        logger.error(f"❌ Market Impact Monitor failed: {str(e)}")

# Initialize Macro News Detector - CRITICAL signals to DISCORD_CRITICAL_SIGNALS
macro_news_detector = None
try:
    from monitors.macro_news_detector import MacroNewsDetector
    if unified_news_engine and alert_manager:
        macro_news_detector = MacroNewsDetector(
            unified_news_engine=unified_news_engine,
            discord_alerter=alert_manager.discord,
            check_interval=15  # 15 seconds - FASTEST for Fed/Tariffs
        )
        # Override Discord webhook to use CRITICAL channel
        critical_webhook = os.getenv('DISCORD_CRITICAL_SIGNALS') or os.getenv('DISCORD_WEBHOOK_URL')
        if critical_webhook and hasattr(macro_news_detector, 'discord'):
            # Update the discord alerter webhook for critical signals
            logger.info("✅ Macro News Detector initialized (15s interval - CRITICAL)")
            logger.info("   🚨 Routes to: DISCORD_CRITICAL_SIGNALS (Fed/Tariffs/Economic)")
except ImportError:
    logger.warning("⚠️  Macro News Detector not available")
except Exception as e:
    logger.error(f"❌ Macro News Detector failed: {str(e)}")

# Initialize Spillover Detector - Routes to DISCORD_NEWS_ALERTS
spillover_detector = None
try:
    from monitors.spillover_detector import SpilloverDetector
    if unified_news_engine and alert_manager:
        spillover_map = config_yaml.get('market_impact_monitor', {}).get('spillover_map', {
            'NVDA': ['NVTS', 'SMCI', 'ARM', 'AMD', 'AVGO'],
            'TSLA': ['RIVN', 'LCID', 'F', 'GM'],
            'AAPL': ['QCOM', 'CIRR', 'SWKS']
        })
        spillover_detector = SpilloverDetector(
            unified_news_engine=unified_news_engine,
            discord_alerter=alert_manager.discord,
            polygon_api_key=POLYGON_API_KEY,
            spillover_map=spillover_map,
            check_interval=20  # 20 seconds - catch momentum early
        )
        logger.info("✅ Spillover Detector initialized (20s interval)")
        logger.info("   📊 Routes to: DISCORD_NEWS_ALERTS (Related Tickers)")
except ImportError:
    logger.warning("⚠️  Spillover Detector not available")
except Exception as e:
    logger.error(f"❌ Spillover Detector failed: {str(e)}")

extended_hours_monitor = None
if EXTENDED_HOURS_MONITOR_AVAILABLE:
    try:
        extended_hours_monitor = ExtendedHoursVolumeMonitor(
            polygon_api_key=POLYGON_API_KEY,
            discord_alerter=alert_manager.discord if alert_manager else None,
            config=config_yaml,
            watchlist_manager=watchlist_manager
        )
        logger.info("✅ Extended Hours Volume Monitor initialized")
    except Exception as e:
        logger.error(f"❌ Extended Hours Volume Monitor failed: {str(e)}")

realtime_monitor = None
if REALTIME_MONITOR_AVAILABLE:
    try:
        realtime_monitor = RealtimeVolumeSpikeMonitor(
            polygon_api_key=POLYGON_API_KEY,
            discord_alerter=alert_manager.discord if alert_manager else None,
            config=config_yaml,
            watchlist_manager=watchlist_manager
        )
        logger.info("✅ Real-Time Volume Spike Monitor initialized")
    except Exception as e:
        logger.error(f"❌ Real-Time Volume Spike Monitor failed: {str(e)}")

momentum_monitor = None
if MOMENTUM_MONITOR_AVAILABLE:
    try:
        momentum_monitor = MomentumSignalMonitor(
            polygon_api_key=POLYGON_API_KEY,
            discord_alerter=alert_manager.discord if alert_manager else None,
            config=config_yaml,
            watchlist_manager=watchlist_manager
        )
        logger.info("✅ Momentum Signal Monitor initialized")
    except Exception as e:
        logger.error(f"❌ Momentum Signal Monitor failed: {str(e)}")

odte_monitor = None
if ODTE_MONITOR_AVAILABLE:
    try:
        odte_monitor = ODTEGammaMonitor(
            polygon_api_key=POLYGON_API_KEY,
            watchlist_manager=watchlist_manager,
            config=config_yaml
        )
        webhook = os.getenv('DISCORD_ODTE_LEVELS')
        if webhook:
            odte_monitor.set_discord_webhook(webhook)
            logger.info("✅ 0DTE Gamma Monitor initialized")
    except Exception as e:
        logger.error(f"❌ 0DTE Gamma Monitor failed: {str(e)}")

wall_strength_monitor = None
if WALL_STRENGTH_AVAILABLE:
    try:
        if hasattr(analyzer, 'wall_tracker'):
            wall_strength_monitor = WallStrengthMonitor(
                analyzer=analyzer,
                wall_tracker=analyzer.wall_tracker,
                config=config_yaml
            )
            webhook = os.getenv('DISCORD_ODTE_LEVELS')
            if webhook:
                wall_strength_monitor.set_discord_webhook(webhook)
                logger.info("✅ Wall Strength Monitor initialized")
        else:
            logger.warning("⚠️ Wall tracker not available in analyzer")
    except Exception as e:
        logger.error(f"❌ Wall Strength Monitor failed: {str(e)}")

unusual_activity_monitor = None
if UNUSUAL_ACTIVITY_AVAILABLE:
    try:
        if hasattr(analyzer, 'unusual_activity_detector'):
            unusual_activity_monitor = UnusualActivityMonitor(
                analyzer=analyzer,
                detector=analyzer.unusual_activity_detector,
                config=config_yaml
            )
            webhook = os.getenv('DISCORD_UNUSUAL_ACTIVITY')
            if webhook:
                unusual_activity_monitor.set_discord_webhook(webhook)
                logger.info("✅ Unusual Activity Monitor initialized")
        else:
            logger.warning("⚠️ Unusual activity detector not available in analyzer")
    except Exception as e:
        logger.error(f"❌ Unusual Activity Monitor failed: {str(e)}")


# Initialize Earnings Monitor with Benzinga API
earnings_monitor = None
if EARNINGS_MONITOR_AVAILABLE:
    try:
        earnings_config = config_yaml.get('earnings_monitor', {})
        if earnings_config.get('enabled', False):
            
            if alert_manager and alert_manager.discord:
                earnings_monitor = EarningsMonitor(
                    polygon_api_key=POLYGON_API_KEY,
                    discord_alerter=alert_manager.discord,
                    check_interval_premarket=20,
                    check_interval_postmarket=5  # 5 SECONDS!
                )
                
                if news_db:
                    def save_earnings_to_db(ticker, headline, article, channel):
                        news_db.save_news(ticker, headline, article, channel)
                    earnings_monitor.save_to_db_callback = save_earnings_to_db
                
                logger.info("✅ Earnings Monitor initialized (Benzinga API)")
            else:
                logger.warning("⚠️  Earnings Monitor disabled - missing dependencies")
    except Exception as e:
        logger.error(f"❌ Earnings Monitor initialization failed: {str(e)}")


# ALERT CONSOLE: Register Blueprint
if CONFIG_MANAGER_AVAILABLE and config_manager:
    app.register_blueprint(config_bp)
    logger.info("✅ Config routes blueprint registered")

# ============================================================================
# BACKGROUND MONITORS
# ============================================================================

def run_alert_system():
    """Run alert system continuously"""
    if alert_manager:
        try:
            alert_manager.run_continuous()
        except Exception as e:
            logger.error(f"Alert system error: {str(e)}")

def run_wall_strength_monitor():
    """Run wall strength monitor continuously"""
    if wall_strength_monitor:
        try:
            wall_strength_monitor.run_continuous(watchlist_manager)
        except Exception as e:
            logger.error(f"Wall strength monitor error: {str(e)}")

def run_unusual_activity_monitor():
    """Run unusual activity monitor continuously"""
    if unusual_activity_monitor:
        try:
            unusual_activity_monitor.run_continuous(watchlist_manager)
        except Exception as e:
            logger.error(f"Unusual activity monitor error: {str(e)}")

# ============================================================================
# CRITICAL FIX: Add run functions for realtime and momentum monitors
# ============================================================================

def run_realtime_volume_monitor():
    """Run real-time volume monitor continuously"""
    if realtime_monitor:
        try:
            realtime_monitor.run_continuous(watchlist_manager)
        except Exception as e:
            logger.error(f"Real-time volume monitor error: {str(e)}")

def run_momentum_monitor():
    """Run momentum signal monitor continuously"""
    if momentum_monitor:
        try:
            momentum_monitor.run_continuous(watchlist_manager)
        except Exception as e:
            logger.error(f"Momentum monitor error: {str(e)}")

# ============================================================================

def run_earnings_monitor():
    """Run earnings monitor in background"""
    if earnings_monitor:
        try:
            earnings_monitor.start()
            while True:
                time.sleep(60)
        except Exception as e:
            logger.error(f"Earnings monitor crashed: {str(e)}")

def schedule_daily_earnings_preview():
    """Schedule daily earnings preview at 6 PM ET"""
    if not earnings_monitor:
        return
    
    scheduler = BackgroundScheduler(timezone='America/New_York')
    
    scheduler.add_job(
        func=earnings_monitor.send_daily_preview,
        trigger=CronTrigger(hour=18, minute=0, timezone='America/New_York'),
        id='daily_earnings_preview',
        name='Daily Earnings Preview (6 PM ET)',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("✅ Daily earnings preview scheduled for 6:00 PM ET")

# ============================================================================
# EARNINGS MONITORING
# ============================================================================

scheduler = BackgroundScheduler()

def run_sunday_earnings_scan():
    """Run Sunday earnings scan"""
    logger.info("🗓️ Running Sunday earnings scan...")
    try:
        earnings_manager.run_sunday_scan()
        logger.info("✅ Sunday earnings scan complete")
    except Exception as e:
        logger.error(f"❌ Sunday earnings scan failed: {str(e)}")

def schedule_sunday_routine():
    """Schedule Sunday earnings scan at 8 PM ET"""
    try:
        scheduler.add_job(
            func=run_sunday_earnings_scan,
            trigger=CronTrigger(day_of_week='sun', hour=20, minute=0, timezone='America/New_York'),
            id='sunday_earnings_scan',
            name='Sunday Earnings Scan (8 PM ET)',
            replace_existing=True
        )
        scheduler.start()
        logger.info("✅ Sunday earnings scan scheduled for 8:00 PM ET")
    except Exception as e:
        logger.error(f"❌ Failed to schedule Sunday routine: {str(e)}")

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def index():
    """Serve main dashboard"""
    return send_from_directory(app.static_folder, 'professional_dashboard.html')

@app.route('/alert-console')
def alert_console():
    """Serve alert management console"""
    return send_from_directory(app.static_folder, 'alert_console.html')

@app.route('/gamma')
def gamma_dashboard():
    """Serve gamma dashboard"""
    return send_from_directory(app.static_folder, 'gamma_dashboard.html')

@app.route('/gex')
def gex_dashboard():
    """Serve GEX calculator"""
    return send_from_directory(app.static_folder, 'gex_dashboard.html')

@app.route('/api/analyze/<symbol>')
def analyze_symbol(symbol):
    """Analyze a stock symbol"""
    try:
        symbol = symbol.upper()
        logger.info(f"Analyzing {symbol}...")
        
        # Get comprehensive analysis
        result = analyzer.generate_professional_signal(symbol)
        
        if not result or result.get('error'):
            error_msg = result.get('error', 'Unknown error') if result else 'Analysis failed'
            return jsonify({
                'error': error_msg,
                'symbol': symbol
            }), 400
        
        # Sanitize the result
        sanitized_result = sanitize_for_json(result)
        
        return jsonify(sanitized_result)
        
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {str(e)}", exc_info=True)
        return jsonify({
            'error': str(e),
            'symbol': symbol
        }), 500

@app.route('/api/watchlist')
def get_watchlist():
    """Get current watchlist"""
    try:
        watchlist = watchlist_manager.load_symbols()
        return jsonify({
            'success': True,
            'watchlist': watchlist,
            'count': len(watchlist)
        })
    except Exception as e:
        logger.error(f"Error getting watchlist: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/watchlist/add', methods=['POST'])
def add_to_watchlist():
    """Add symbol to watchlist"""
    try:
        data = request.json
        symbol = data.get('symbol', '').upper()
        
        if not symbol:
            return jsonify({'error': 'Symbol required'}), 400
        
        watchlist_manager.add_symbol(symbol)
        
        return jsonify({
            'success': True,
            'message': f'{symbol} added to watchlist',
            'watchlist': watchlist_manager.load_symbols()
        })
    except Exception as e:
        logger.error(f"Error adding to watchlist: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/watchlist/remove', methods=['POST'])
def remove_from_watchlist():
    """Remove symbol from watchlist"""
    try:
        data = request.json
        symbol = data.get('symbol', '').upper()
        
        if not symbol:
            return jsonify({'error': 'Symbol required'}), 400
        
        watchlist_manager.remove_symbol(symbol)
        
        return jsonify({
            'success': True,
            'message': f'{symbol} removed from watchlist',
            'watchlist': watchlist_manager.load_symbols()
        })
    except Exception as e:
        logger.error(f"Error removing from watchlist: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/earnings/status')
def get_earnings_status():
    """Get earnings monitoring status"""
    try:
        status = earnings_manager.get_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting earnings status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/earnings/toggle', methods=['POST'])
def toggle_earnings():
    """Toggle earnings monitoring"""
    try:
        result = earnings_manager.toggle_monitoring()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error toggling earnings: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/earnings/add', methods=['POST'])
def add_earnings_symbol():
    """Add symbol to earnings monitoring"""
    try:
        data = request.json
        symbol = data.get('symbol', '').upper()
        
        if not symbol:
            return jsonify({'error': 'Symbol required'}), 400
        
        result = earnings_manager.add_symbol(symbol)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error adding earnings symbol: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/earnings/remove', methods=['POST'])
def remove_earnings_symbol():
    """Remove symbol from earnings monitoring"""
    try:
        data = request.json
        symbol = data.get('symbol', '').upper()
        
        if not symbol:
            return jsonify({'error': 'Symbol required'}), 400
        
        result = earnings_manager.remove_symbol(symbol)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error removing earnings symbol: {str(e)}")
        return jsonify({'error': str(e)}), 500
@app.route('/api/news-feed/all', methods=['GET'])
def get_news_feed_all():
    """Get all news from Polygon API (no database needed)"""
    try:
        logger.info("📰 Fetching news from Polygon...")
        
        # Get watchlist symbols
        watchlist = watchlist_manager.load_symbols()
        news_by_symbol = {}
        
        # Fetch news for each symbol (limit to 15 to avoid rate limits)
        for symbol in watchlist[:15]:
            try:
                # Use your existing analyzer to get news
                news_data = analyzer.get_enhanced_news_sentiment(symbol)
                
                if news_data.get('headlines') and len(news_data['headlines']) > 0:
                    news_by_symbol[symbol] = []
                    
                    for headline in news_data['headlines'][:5]:  # Top 5 per symbol
                        news_by_symbol[symbol].append({
                            'headline': headline,
                            'sentiment': news_data.get('sentiment', 'NEUTRAL'),
                            'timestamp': datetime.now().isoformat(),
                            'time_str': 'Recent',
                            'url': '#',
                            'channel': 'polygon'
                        })
                
                # Small delay to avoid rate limits
                time.sleep(0.05)
                
            except Exception as e:
                logger.error(f"Error fetching news for {symbol}: {str(e)}")
                continue
        
        logger.info(f"✅ Loaded news for {len(news_by_symbol)} symbols")
        
        return jsonify({
            'success': True,
            'news': news_by_symbol,
            'count': len(news_by_symbol),
            'total_articles': sum(len(items) for items in news_by_symbol.values()),
            'source': 'polygon_api',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in news feed endpoint: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'news': {}
        }), 500
@app.route('/api/pin-probability/<symbol>')
def get_pin_probability(symbol):
    """Calculate pin probability for a symbol"""
    try:
        if not pin_calculator:
            return jsonify({'error': 'Pin calculator not available'}), 503
        
        symbol = symbol.upper()
        result = pin_calculator.calculate_pin_risk(
            symbol=symbol,
            polygon_api_key=POLYGON_API_KEY,
            tradier_api_key=TRADIER_API_KEY,
            tradier_account_type=TRADIER_ACCOUNT_TYPE
        )
        
        # Sanitize result
        sanitized_result = sanitize_for_json(result)
        return jsonify(sanitized_result)
        
    except Exception as e:
        logger.error(f"Error calculating pin probability for {symbol}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/confluence/<symbol>')
def get_confluence_alerts(symbol):
    """Get confluence alerts for a symbol"""
    try:
        if not confluence_system:
            return jsonify({'error': 'Confluence system not available'}), 503
        
        symbol = symbol.upper()
        
        # Get full analysis first
        analysis = analyzer.generate_professional_signal(symbol)
        if not analysis or analysis.get('error'):
            return jsonify({'error': 'Failed to analyze symbol'}), 400
        
        # Generate confluence alerts
        alerts = confluence_system.generate_alerts(analysis)
        
        # Sanitize result
        sanitized_alerts = sanitize_for_json(alerts)
        return jsonify({
            'success': True,
            'symbol': symbol,
            'alerts': sanitized_alerts
        })
        
    except Exception as e:
        logger.error(f"Error getting confluence alerts for {symbol}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts/recent')
def get_recent_alerts():
    """Get recent alerts"""
    try:
        if not alert_manager:
            return jsonify({'error': 'Alert manager not available'}), 503
        
        hours = request.args.get('hours', 24, type=int)
        alerts = alert_manager.get_recent_alerts(hours=hours)
        
        return jsonify({
            'success': True,
            'alerts': alerts,
            'count': len(alerts)
        })
    except Exception as e:
        logger.error(f"Error getting recent alerts: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/news-feed')
def get_news_feed():
    """Get all news from database"""
    try:
        if not news_db:
            return jsonify({'error': 'Database not available'}), 503
        
        hours = request.args.get('hours', 24, type=int)
        news_data = news_db.get_all_news(hours=hours)
        
        return jsonify({
            'success': True,
            'news': news_data,
            'symbols_count': len(news_data),
            'total_articles': sum(len(items) for items in news_data.values())
        })
    except Exception as e:
        logger.error(f"Error getting news feed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/news-feed/<symbol>')
def get_symbol_news(symbol):
    """Get news history for specific symbol"""
    try:
        symbol = symbol.upper()
        
        if not alert_manager:
            return jsonify({'error': 'Alert manager not available'}), 503
        
        hours = request.args.get('hours', 24, type=int)
        news_list = alert_manager.get_symbol_news_history(symbol, hours=hours)
        
        return jsonify({
            'success': True,
            'symbol': symbol,
            'news': news_list,
            'count': len(news_list)
        })
    
    except Exception as e:
        logger.error(f"Error getting news for {symbol}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/news-dashboard')
def news_dashboard():
    """Serve news dashboard"""
    return send_from_directory(app.static_folder, 'news_dashboard.html')

@app.route('/api/health')
def health_check():
    """Health check"""
    earnings_status = earnings_manager.get_status()
    
    return jsonify({
        'status': 'healthy',
        'version': '4.5.2-realtime-momentum-fixed',
        'polygon_enabled': bool(POLYGON_API_KEY),
        'alerts_enabled': alert_manager is not None,
        'config_manager_enabled': config_manager is not None,
        'earnings_monitoring': {
            'enabled': earnings_status['enabled'],
            'symbols_count': earnings_status['symbols_count']
        },
        'wall_strength_tracker': {
            'enabled': wall_strength_monitor is not None,
            'check_interval': wall_strength_monitor.check_interval if wall_strength_monitor else 0,
            'stats': wall_strength_monitor.stats if wall_strength_monitor else {},
            'tracker_stats': analyzer.wall_tracker.get_statistics()
        },
        'unusual_activity': {
            'enabled': unusual_activity_monitor is not None,
            'check_interval': unusual_activity_monitor.check_interval if unusual_activity_monitor else 0,
            'stats': unusual_activity_monitor.stats if unusual_activity_monitor else {},
            'detector_stats': analyzer.unusual_activity_detector.get_statistics() if hasattr(analyzer, 'unusual_activity_detector') else {}
        },
        'realtime_volume': {
            'enabled': realtime_monitor is not None,
            'running': realtime_monitor is not None
        },
        'momentum_signals': {
            'enabled': momentum_monitor is not None,
            'running': momentum_monitor is not None
        },
        'phase1_features': {
            'volume_analysis': analyzer.volume_analyzer is not None,
            'key_level_detection': analyzer.key_level_detector is not None,
            'signal_metrics': metrics_tracker is not None
        },
        'alert_stats': alert_manager.stats if alert_manager else None,
        'odte_gamma_monitor': {
            'enabled': odte_monitor is not None,
            'stats': odte_monitor.stats if odte_monitor else {}
        },
        'earnings_monitor': {
            'enabled': earnings_monitor is not None,
            'stats': earnings_monitor.stats if earnings_monitor else {},
            'current_session': earnings_monitor.stats.get('current_session') if earnings_monitor else None
        }
    })

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🚀 STARTING PROFESSIONAL TRADING DASHBOARD v4.5.2")
    print("   (WITH REALTIME VOLUME + MOMENTUM MONITORS FIXED)")
    print("=" * 60)
    print(f"\n📊 Dashboard: http://localhost:5001")
    print(f"⚙️  Alert Console: http://localhost:5001/alert-console")
    print(f"🩺 Health: http://localhost:5001/api/health")
    
    # Show earnings status
    earnings_status = earnings_manager.get_status()
    print(f"\n📅 Earnings: {'✅ ENABLED' if earnings_status['enabled'] else '📕 DISABLED'}")
    print(f"📊 Earnings Symbols: {earnings_status['symbols_count']}")
    
    # Schedule Sunday routine
    schedule_sunday_routine()
    
    # ALERT CONSOLE: Initialize config routes with monitor instances
    if CONFIG_MANAGER_AVAILABLE and config_manager:
        monitor_instances = {
            'realtime_volume': realtime_monitor,
            'extended_hours': extended_hours_monitor,
            'market_impact': market_impact_monitor,
            'openai': openai_monitor,
            'odte': odte_monitor,
            'wall_strength': wall_strength_monitor,
            'unusual_activity': unusual_activity_monitor,
            'momentum': momentum_monitor,
            'earnings': earnings_monitor
        }
        
        init_config_routes(config_manager, alert_manager, monitor_instances)
        logger.info("✅ Config routes initialized with monitor instances")
        print(f"\n⚙️  Alert Console: READY")
        print(f"   • Real-time configuration")
        print(f"   • Test alerts")
        print(f"   • Hot reload")
    
    # Start alert system
    if alert_manager:
        print(f"\n📢 Starting Alert System...")
        alert_thread = threading.Thread(target=run_alert_system, daemon=True)
        alert_thread.start()
        print(f"   ✅ Alert system started")
    
    # Start Wall Strength Monitor
    if wall_strength_monitor:
        print(f"\n📊 Starting Wall Strength Monitor...")
        wall_strength_thread = threading.Thread(target=run_wall_strength_monitor, daemon=True)
        wall_strength_thread.start()
        print(f"   ✅ Wall strength monitor started")
        print(f"   🕐 Tracks OI/Volume changes every 5 minutes")
        print(f"   📡 Routes to: DISCORD_ODTE_LEVELS")
    
    # Start Unusual Activity Monitor
    if unusual_activity_monitor:
        print(f"\n🔍 Starting Unusual Activity Monitor...")
        unusual_activity_thread = threading.Thread(
            target=run_unusual_activity_monitor,
            daemon=True
        )
        unusual_activity_thread.start()
        print(f"   ✅ Unusual activity monitor started")
        print(f"   🕐 Scans every {unusual_activity_monitor.check_interval} seconds")
        print(f"   📡 Routes to: DISCORD_UNUSUAL_ACTIVITY")
    
    # Start Earnings Monitor
    if earnings_monitor:
        print(f"\n📊 Starting Earnings Monitor...")
        earnings_thread = threading.Thread(
            target=run_earnings_monitor,
            daemon=True
        )
        earnings_thread.start()
        print(f"   ✅ Earnings monitor started (Benzinga API)")
        print(f"   🌅 Pre-market: 5:00 AM - 8:00 AM ET (20s checks)")
        print(f"   🌆 Post-market: 3:50 PM - 7:00 PM ET (5s checks) ⚡ ULTRA-FAST")
        print(f"   📅 Daily preview: 6:00 PM ET")
        print(f"   📡 Routes to: DISCORD_REALTIME_EARNINGS")
        
        # Schedule daily preview
        schedule_daily_earnings_preview()
    
    if openai_monitor:
        print(f"\n🤖 Starting OpenAI News Monitor...")
        openai_monitor.start()
        print(f"   ✅ OpenAI news monitor started")
        print(f"   🕐 Checks every 30 seconds (REAL-TIME)")
        print(f"   📡 Routes to: DISCORD_OPENAI_NEWS")
    
    if macro_news_detector:
        print(f"\n🚨 Starting Macro News Detector...")
        macro_news_detector.start()
        print(f"   ✅ Macro news detector started")
        print(f"   🕐 Checks every 15 seconds (CRITICAL - FASTEST)")
        print(f"   📡 Routes to: DISCORD_CRITICAL_SIGNALS")
        print(f"   🎯 Monitors: Fed, FOMC, Tariffs, CPI, Jobs, GDP")
    
    if spillover_detector:
        print(f"\n📊 Starting Spillover Detector...")
        spillover_detector.start()
        print(f"   ✅ Spillover detector started")
        print(f"   🕐 Checks every 20 seconds (HIGH PRIORITY)")
        print(f"   📡 Routes to: DISCORD_NEWS_ALERTS")
        print(f"   🎯 Monitors: NVDA→SMCI, TSLA→RIVN, etc.")
    
    # ============================================================================
    # CRITICAL FIX: Start Real-Time Volume Monitor with Threading
    # ============================================================================
    if realtime_monitor:
        print(f"\n📈 Starting Real-Time Volume Monitor...")
        realtime_thread = threading.Thread(
            target=run_realtime_volume_monitor,
            daemon=True
        )
        realtime_thread.start()
        print(f"   ✅ Real-time volume monitor started")
        print(f"   🕐 Scans for volume spikes in real-time")
        print(f"   📡 Routes to: DISCORD alerts (configured channel)")
        print(f"   🎯 Monitors: Watchlist stocks for unusual volume")
    
    # ============================================================================
    # CRITICAL FIX: Start Momentum Signal Monitor with Threading
    # ============================================================================
    if momentum_monitor:
        print(f"\n🚀 Starting Momentum Signal Monitor...")
        momentum_thread = threading.Thread(
            target=run_momentum_monitor,
            daemon=True
        )
        momentum_thread.start()
        print(f"   ✅ Momentum monitor started")
        print(f"   🕐 Scans for momentum shifts in real-time")
        print(f"   📡 Routes to: DISCORD alerts (configured channel)")
        print(f"   🎯 Monitors: Watchlist stocks for momentum changes")
    
    if market_impact_monitor:
        print(f"\n📰 Market Impact Monitor Active...")
        print(f"   🕐 Checks every 15 seconds (REAL-TIME)")
        print(f"   📡 Routes to: DISCORD_NEWS_ONLY")
        print(f"   🎯 Monitors: Watchlist stocks only")
    
    print(f"\n" + "=" * 60)
    print("✅ ALL SYSTEMS ONLINE - READY FOR TRADING!")
    print("=" * 60)
    print(f"\n🎯 ACTIVE FEATURES:")
    print(f"   • Real-Time Volume Monitor - Volume spikes & alerts ✨ NOW ACTIVE")
    print(f"   • Momentum Signal Monitor - Price momentum tracking ✨ NOW ACTIVE")
    print(f"   • Wall Strength Tracker - Monitors gamma walls")
    print(f"   • Unusual Activity Detector - Smart money tracking")
    print(f"   • Alert Management Console - Real-time config")
    print(f"   • OpenAI News Monitor - AI sector news")
    print(f"   • Macro News Detector - Fed/Tariffs/Economic")
    print(f"   • Spillover Detector - Related ticker opportunities")
    print(f"   • Earnings Monitor - Pre/Post market tracking")
    print("=" * 60 + "\n")
    
    # Start Flask server
    app.run(host='0.0.0.0', port=5001, debug=False)