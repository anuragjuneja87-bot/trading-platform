"""
backend/app.py - COMPLETE VERSION v4.5
WITH ALERT CONSOLE + WALL STRENGTH + UNUSUAL ACTIVITY

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

# ALERT CONSOLE: Initialize Config Manager
config_manager = None
if CONFIG_MANAGER_AVAILABLE:
    try:
        config_manager = ConfigManager()
        logger.info("✅ Config Manager initialized")
    except Exception as e:
        logger.error(f"❌ Config Manager failed: {str(e)}")

# Initialize all monitors
openai_monitor = None
if OPENAI_MONITOR_AVAILABLE:
    try:
        openai_monitor = OpenAINewsMonitor(polygon_api_key=POLYGON_API_KEY, config=config_yaml)
        webhook = os.getenv('DISCORD_OPENAI_NEWS')
        if webhook:
            openai_monitor.set_discord_webhook(webhook)
            logger.info("✅ OpenAI News Monitor initialized")
    except Exception as e:
        logger.error(f"❌ OpenAI News Monitor failed: {str(e)}")

market_impact_monitor = None
if MARKET_IMPACT_AVAILABLE:
    try:
        market_impact_monitor = MarketImpactMonitor(
            polygon_api_key=POLYGON_API_KEY,
            config=config_yaml,
            watchlist_manager=watchlist_manager
        )
        webhook = os.getenv('DISCORD_NEWS_ALERTS')
        if webhook:
            market_impact_monitor.set_discord_webhook(webhook)
            logger.info("✅ Market Impact Monitor initialized")
    except Exception as e:
        logger.error(f"❌ Market Impact Monitor failed: {str(e)}")

extended_hours_monitor = None
if EXTENDED_HOURS_MONITOR_AVAILABLE:
    try:
        extended_hours_monitor = ExtendedHoursVolumeMonitor(
            polygon_api_key=POLYGON_API_KEY,
            config=config_yaml,
            watchlist_manager=watchlist_manager
        )
        webhook = os.getenv('DISCORD_VOLUME_SPIKE')
        if webhook:
            extended_hours_monitor.set_discord_webhook(webhook)
            logger.info("✅ Extended Hours Volume Monitor initialized")
    except Exception as e:
        logger.error(f"❌ Extended Hours Volume Monitor failed: {str(e)}")

realtime_monitor = None
if REALTIME_MONITOR_AVAILABLE:
    try:
        realtime_monitor = RealtimeVolumeSpikeMonitor(
            polygon_api_key=POLYGON_API_KEY,
            config=config_yaml,
            watchlist_manager=watchlist_manager
        )
        webhook = os.getenv('DISCORD_VOLUME_SPIKE')
        if webhook:
            realtime_monitor.set_discord_webhook(webhook)
            logger.info("✅ Real-Time Volume Spike Monitor initialized")
    except Exception as e:
        logger.error(f"❌ Real-Time Volume Spike Monitor failed: {str(e)}")

momentum_monitor = None
if MOMENTUM_MONITOR_AVAILABLE:
    try:
        momentum_monitor = MomentumSignalMonitor(
            polygon_api_key=POLYGON_API_KEY,
            config=config_yaml,
            watchlist_manager=watchlist_manager
        )
        webhook = os.getenv('DISCORD_MOMENTUM_SIGNALS')
        if webhook:
            momentum_monitor.set_discord_webhook(webhook)
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
# EARNINGS MONITORING
# ============================================================================

scheduler = BackgroundScheduler()

def run_sunday_earnings_scan():
    """Run Sunday earnings scan"""
    logger.info("🗓️ Running Sunday earnings scan...")
    try:
        if openai_monitor:
            openai_monitor.run_weekly_earnings_scan()
    except Exception as e:
        logger.error(f"Sunday earnings scan failed: {str(e)}")

def schedule_sunday_routine():
    """Schedule Sunday earnings scan"""
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
        return jsonify(result)
    
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
                results.append({'symbol': symbol, 'error': str(e)})
        
        return jsonify({
            'results': results,
            'count': len(results)
        })
    
    except Exception as e:
        logger.error(f"Error in analyze-all: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/gamma/<symbol>')
def get_gamma_analysis(symbol):
    """Get gamma analysis for symbol"""
    try:
        symbol = symbol.upper()
        logger.info(f"🎯 Gamma analysis for {symbol}")
        
        quote = analyzer.get_real_time_quote(symbol)
        current_price = quote.get('price', 0)
        
        if current_price == 0:
            return jsonify({'error': 'Unable to get current price'}), 400
        
        result = analyzer.analyze_open_interest(symbol, current_price)
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error in gamma analysis: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/gex/<symbol>')
def get_gex_analysis(symbol):
    """Get GEX analysis for symbol"""
    try:
        symbol = symbol.upper()
        logger.info(f"💰 GEX analysis for {symbol}")
        
        quote = analyzer.get_real_time_quote(symbol)
        current_price = quote.get('price', 0)
        
        if current_price == 0:
            return jsonify({'error': 'Unable to get current price'}), 400
        
        result = analyzer.analyze_full_gex(symbol, current_price)
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error in GEX analysis: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/earnings/status')
def get_earnings_status():
    """Get earnings monitoring status"""
    try:
        status = earnings_manager.get_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/earnings/toggle', methods=['POST'])
def toggle_earnings():
    """Toggle earnings monitoring"""
    try:
        data = request.json
        enabled = data.get('enabled', False)
        
        earnings_manager.set_enabled(enabled)
        
        return jsonify({
            'success': True,
            'enabled': enabled,
            'status': earnings_manager.get_status()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/wall-strength/check', methods=['POST'])
def check_wall_strength():
    """Manual wall strength check"""
    if not wall_strength_monitor:
        return jsonify({'error': 'Wall strength monitor not available'}), 503
    
    try:
        watchlist = watchlist_manager.load_symbols()
        alerts_sent = wall_strength_monitor.run_single_check(watchlist)
        return jsonify({
            'success': True,
            'alerts_sent': alerts_sent,
            'stats': wall_strength_monitor.stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/unusual-activity/check', methods=['POST'])
def check_unusual_activity():
    """Manual unusual activity check"""
    if not unusual_activity_monitor:
        return jsonify({'error': 'Unusual activity monitor not available'}), 503
    
    try:
        watchlist = watchlist_manager.load_symbols()
        alerts_sent = unusual_activity_monitor.run_single_check(watchlist)
        return jsonify({
            'success': True,
            'alerts_sent': alerts_sent,
            'stats': unusual_activity_monitor.stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pin-probability/<symbol>')
def get_pin_probability(symbol):
    """Get 0DTE pin probability analysis"""
    try:
        symbol = symbol.upper()
        logger.info(f"📍 Pin probability requested for {symbol}")
        
        if not pin_calculator:
            return jsonify({
                'symbol': symbol,
                'available': False,
                'reason': 'Pin calculator not initialized'
            }), 503
        
        quote = analyzer.get_real_time_quote(symbol)
        current_price = quote.get('price', 0)
        
        if current_price == 0:
            return jsonify({
                'symbol': symbol,
                'available': False,
                'reason': 'Unable to get current price'
            }), 400
        
        gamma_data = analyzer.analyze_full_gex(symbol, current_price)
        
        if not gamma_data.get('available'):
            return jsonify({
                'symbol': symbol,
                'available': False,
                'reason': 'No options data available'
            })
        
        options_data = analyzer.get_options_chain(symbol)
        
        if not options_data:
            return jsonify({
                'symbol': symbol,
                'available': False,
                'reason': 'No options chain available'
            })
        
        expiration = gamma_data.get('expiration', datetime.now().strftime('%Y%m%d'))
        
        result = pin_calculator.analyze_pin_probability(
            symbol,
            current_price,
            options_data,
            gamma_data,
            expiration
        )
        
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
    """Get confluence analysis combining all signals"""
    try:
        symbol = symbol.upper()
        logger.info(f"🎯 Confluence analysis requested for {symbol}")
        
        if not confluence_system:
            return jsonify({
                'symbol': symbol,
                'available': False,
                'reason': 'Confluence system not initialized'
            }), 503
        
        analysis_data = analyzer.generate_professional_signal(symbol)
        
        if not analysis_data:
            return jsonify({
                'symbol': symbol,
                'available': False,
                'reason': 'Unable to analyze symbol'
            }), 400
        
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
    """Get all news from cache (for news dashboard)"""
    try:
        if not alert_manager:
            return jsonify({'error': 'Alert manager not available'}), 503
        
        # Get all symbols from watchlist
        watchlist = watchlist_manager.load_symbols()
        
        news_data = {}
        for symbol in watchlist:
            news_list = alert_manager.get_symbol_news_history(symbol, hours=24)
            if news_list:
                news_data[symbol] = news_list
        
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
        'version': '4.5-alert-console',
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
            'momentum': momentum_monitor
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
    
    print(f"\n" + "=" * 60)
    print("✅ ALL SYSTEMS ONLINE - READY FOR TRADING!")
    print("=" * 60)
    print(f"\n🎯 ACTIVE FEATURES:")
    print(f"   • Wall Strength Tracker - Monitors gamma walls")
    print(f"   • Unusual Activity Detector - Smart money tracking")
    print(f"   • Alert Management Console - Real-time config")
    print(f"   • 5-minute monitoring during market hours")
    print("=" * 60 + "\n")
    
    # Start Flask server
    app.run(host='0.0.0.0', port=5001, debug=False)