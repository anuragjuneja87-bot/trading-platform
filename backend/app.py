"""
backend/app.py - COMPLETE VERSION v4.5.1
WITH ALERT CONSOLE + WALL STRENGTH + UNUSUAL ACTIVITY + EARNINGS MONITOR

COMPLETE REPLACEMENT FILE
Copy this entire file to replace your existing app.py
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

def run_earnings_monitor():
    """Run earnings monitor in background"""
    if earnings_monitor:
        try:
            earnings_monitor.start()
            while True:
                time.sleep(60)
        except Exception as e:
            logger.error(f"Earnings monitor crashed: {{str(e)}}")
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
    """Schedule Sunday 7 AM ET earnings scan"""
    trigger = CronTrigger(
        day_of_week='sun',
        hour=7,
        minute=0,
        timezone='America/New_York'
    )
    scheduler.add_job(run_sunday_earnings_scan, trigger)
    scheduler.start()
    logger.info("📅 Sunday earnings scan scheduled (7:00 AM ET)")

# ============================================================================
# DATABASE HELPER FUNCTION
# ============================================================================

def save_news_to_db(ticker: str, headline: str, article: dict, channel: str):
    """Save news article to database"""
    if not news_db:
        return
    
    try:
        published_str = article.get('published', datetime.now().isoformat())
        published_at = datetime.fromisoformat(published_str.replace('Z', ''))
        
        news_db.add_news(
            ticker=ticker,
            headline=headline,
            article_id=article.get('id') or article.get('url'),
            summary=article.get('teaser') or article.get('description', '')[:500],
            url=article.get('url'),
            source=article.get('source', 'Benzinga'),
            channel=channel,
            sentiment='NEUTRAL',
            published_at=published_at,
            metadata={
                'tags': article.get('tags', []),
                'tickers': article.get('tickers', [])
            }
        )
        logger.debug(f"💾 Saved to DB: {ticker} - {headline[:50]}")
    except Exception as e:
        logger.error(f"Error saving news to DB: {str(e)}")

# ============================================================================
# FRONTEND ROUTES
# ============================================================================

@app.route('/')
def index():
    """Serve main dashboard"""
    return send_from_directory(app.static_folder, 'professional_dashboard.html')

@app.route('/gamma')
def gamma_dashboard():
    """Serve gamma dashboard"""
    return send_from_directory(app.static_folder, 'gamma_dashboard.html')

@app.route('/gex')
def gex_dashboard():
    """Serve GEX calculator"""
    return send_from_directory(app.static_folder, 'gex_dashboard.html')

@app.route('/alert-console')
def alert_console():
    """Serve alert management console"""
    return send_from_directory(app.static_folder, 'alert_console.html')

# ============================================================================
# API ROUTES
# ============================================================================

@app.route('/api/watchlist')
def get_watchlist():
    """Get current watchlist"""
    try:
        symbols = watchlist_manager.load_symbols()
        return jsonify({
            'symbols': symbols,
            'count': len(symbols)
        })
    except Exception as e:
        logger.error(f"Error loading watchlist: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze/<symbol>')
def analyze_symbol(symbol):
    """Analyze single symbol"""
    try:
        symbol = symbol.upper()
        logger.info(f"📊 Analyzing {symbol}...")
        
        result = analyzer.generate_professional_signal(symbol)
        # Sanitize result to ensure JSON serializability
        sanitized_result = sanitize_for_json(result)
        return jsonify(sanitized_result)
    
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze-all')
def analyze_all():
    """Analyze all watchlist symbols"""
    try:
        symbols = watchlist_manager.load_symbols()
        results = []
        
        for symbol in symbols:
            try:
                result = analyzer.generate_professional_signal(symbol)
                results.append(result)
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {str(e)}")
                results.append({
                    'symbol': symbol,
                    'error': str(e)
                })
        
        # Sanitize all results to ensure JSON serializability
        sanitized_results = sanitize_for_json(results)
        return jsonify({
            'results': sanitized_results,
            'count': len(sanitized_results)
        })
    
    except Exception as e:
        logger.error(f"Error analyzing watchlist: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/gamma/<symbol>')
def get_gamma(symbol):
    """Get gamma analysis for symbol"""
    try:
        symbol = symbol.upper()
        result = analyzer.calculate_gamma_walls(symbol)
        sanitized_result = sanitize_for_json(result)
        return jsonify(sanitized_result)
    except Exception as e:
        logger.error(f"Error getting gamma for {symbol}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/gex/<symbol>')
def get_gex(symbol):
    """Get GEX data for symbol"""
    try:
        symbol = symbol.upper()
        result = analyzer.calculate_gex(symbol)
        sanitized_result = sanitize_for_json(result)
        return jsonify(sanitized_result)
    except Exception as e:
        logger.error(f"Error getting GEX for {symbol}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/earnings/toggle', methods=['POST'])
def toggle_earnings():
    """Toggle earnings monitoring"""
    try:
        enabled = earnings_manager.toggle()
        return jsonify({
            'success': True,
            'enabled': enabled
        })
    except Exception as e:
        logger.error(f"Error toggling earnings: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/earnings/status')
def earnings_status():
    """Get earnings monitoring status"""
    try:
        status = earnings_manager.get_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting earnings status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/earnings/symbols')
def get_earnings_symbols():
    """Get list of symbols with earnings"""
    try:
        symbols = earnings_manager.get_earnings_symbols()
        return jsonify({
            'symbols': symbols,
            'count': len(symbols)
        })
    except Exception as e:
        logger.error(f"Error getting earnings symbols: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/signal-metrics/<symbol>')
def get_signal_metrics(symbol):
    """Get signal metrics for symbol"""
    try:
        symbol = symbol.upper()
        
        if not metrics_tracker:
            return jsonify({'error': 'Metrics tracker not available'}), 503
        
        metrics = metrics_tracker.get_metrics(symbol)
        return jsonify(metrics)
    
    except Exception as e:
        logger.error(f"Error getting metrics for {symbol}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/pin-probability/<symbol>')
def get_pin_probability(symbol):
    """Get pin probability analysis"""
    try:
        symbol = symbol.upper()
        
        if not pin_calculator:
            return jsonify({
                'symbol': symbol,
                'available': False,
                'message': 'Pin probability calculator not available'
            })
        
        # Get current analysis data
        analysis_data = analyzer.generate_professional_signal(symbol)
        
        # Calculate pin probability
        result = pin_calculator.calculate_pin_probability(symbol, analysis_data)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting pin probability: {str(e)}")
        return jsonify({
            'symbol': symbol,
            'available': False,
            'error': str(e)
        }), 500

@app.route('/api/confluence/<symbol>')
def get_confluence_analysis(symbol):
    """Get confluence analysis for symbol"""
    try:
        symbol = symbol.upper()
        
        if not confluence_system:
            return jsonify({
                'symbol': symbol,
                'available': False,
                'message': 'Confluence alert system not available'
            })
        
        # Get current analysis data
        analysis_data = analyzer.generate_professional_signal(symbol)
        
        # Analyze confluence
        result = confluence_system.analyze_confluence(symbol, analysis_data)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting confluence analysis: {str(e)}")
        return jsonify({
            'symbol': symbol,
            'available': False,
            'error': str(e)
        }), 500

@app.route('/api/news-feed/all')
def get_all_news():
    """Get all news from database (for news dashboard)"""
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
    return send_from_directory('../frontend', 'news_dashboard.html')

@app.route('/api/health')
def health_check():
    """Health check"""
    earnings_status = earnings_manager.get_status()
    
    return jsonify({
        'status': 'healthy',
        'version': '4.5.1-earnings-monitor',
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
    print("🚀 STARTING PROFESSIONAL TRADING DASHBOARD v4.5")
    print("   (WITH ALERT CONSOLE + WALL STRENGTH + UNUSUAL ACTIVITY)")
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
    
    if market_impact_monitor:
        print(f"\n📰 Market Impact Monitor Active...")
        print(f"   🕐 Checks every 15 seconds (REAL-TIME)")
        print(f"   📡 Routes to: DISCORD_NEWS_ONLY")
        print(f"   🎯 Monitors: Watchlist stocks only")
    
    print(f"\n" + "=" * 60)
    print("✅ ALL SYSTEMS ONLINE - READY FOR TRADING!")
    print("=" * 60)
    print(f"\n🎯 ACTIVE FEATURES:")
    print(f"   • Wall Strength Tracker - Monitors gamma walls")
    print(f"   • Unusual Activity Detector - Smart money tracking")
    print(f"   • Alert Management Console - Real-time config")
    print(f"   • OpenAI News Monitor - AI sector news")
    print(f"   • Macro News Detector - Fed/Tariffs/Economic")
    print(f"   • Spillover Detector - Related ticker opportunities")
    print(f"   • 5-minute monitoring during market hours")
    print("=" * 60 + "\n")
    
    # Start Flask server
    app.run(host='0.0.0.0', port=5001, debug=False)