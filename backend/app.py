"""
backend/app.py - COMPLETE VERSION v4.4
WITH WALL STRENGTH TRACKER + UNUSUAL ACTIVITY MONITOR

COMPLETE REPLACEMENT FILE
Copy this entire file to replace your existing app.py

This is Part 1 - Contains imports, initialization, and helper functions
Part 2 contains API routes
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

# Wall Strength Monitor (NEW!)
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
            logger.info("✅ Real-Time Volume Monitor initialized")
    except Exception as e:
        logger.error(f"❌ Real-Time Volume Monitor failed: {str(e)}")

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
        config_yaml['tradier_api_key'] = TRADIER_API_KEY
        config_yaml['tradier_account_type'] = TRADIER_ACCOUNT_TYPE
        
        odte_monitor = ODTEGammaMonitor(
            polygon_api_key=POLYGON_API_KEY,
            config=config_yaml,
            watchlist_manager=watchlist_manager
        )
        webhook = os.getenv('DISCORD_ODTE_LEVELS')
        if webhook:
            odte_monitor.set_discord_webhook(webhook)
            logger.info("✅ 0DTE Gamma Monitor initialized")
    except Exception as e:
        logger.error(f"❌ 0DTE Gamma Monitor failed: {str(e)}")

# Initialize Wall Strength Monitor (NEW!)
wall_strength_monitor = None
if WALL_STRENGTH_AVAILABLE:
    try:
        wall_strength_monitor = WallStrengthMonitor(
            analyzer=analyzer,
            wall_tracker=analyzer.wall_tracker,
            config=config_yaml
        )
        webhook = os.getenv('DISCORD_ODTE_LEVELS')
        if webhook:
            wall_strength_monitor.set_discord_webhook(webhook)
            logger.info("✅ Wall Strength Monitor initialized")
            logger.info(f"   🕐 Check interval: {wall_strength_monitor.check_interval} seconds")
    except Exception as e:
        logger.error(f"❌ Wall Strength Monitor failed: {str(e)}")

# Initialize Unusual Activity Monitor (Feature 3)
unusual_activity_monitor = None
if UNUSUAL_ACTIVITY_AVAILABLE:
    try:
        unusual_activity_monitor = UnusualActivityMonitor(
            analyzer=analyzer,
            detector=analyzer.unusual_activity_detector,
            config=config_yaml
        )
        webhook = os.getenv('DISCORD_UNUSUAL_ACTIVITY')
        if webhook:
            unusual_activity_monitor.set_discord_webhook(webhook)
            logger.info("✅ Unusual Activity Monitor initialized")
            logger.info(f"   🕐 Check interval: {unusual_activity_monitor.check_interval} seconds")
    except Exception as e:
        logger.error(f"❌ Unusual Activity Monitor failed: {str(e)}")

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

logger.info("=" * 60)
logger.info("🚀 PROFESSIONAL TRADING DASHBOARD v4.4")
logger.info("   (WITH WALL STRENGTH + UNUSUAL ACTIVITY)")
logger.info("=" * 60)

# Monitor background thread functions
def run_alert_system():
    """Run alert manager"""
    if alert_manager:
        logger.info("📢 Starting Alert System...")
        try:
            alert_manager.run_continuous()
        except Exception as e:
            logger.error(f"❌ Alert system error: {str(e)}")

def run_wall_strength_monitor():
    """Run Wall Strength monitor (NEW!)"""
    if wall_strength_monitor:
        logger.info("📊 Starting Wall Strength Monitor...")
        try:
            wall_strength_monitor.run_continuous(watchlist_manager)
        except Exception as e:
            logger.error(f"❌ Wall Strength monitor error: {str(e)}")

def run_unusual_activity_monitor():
    """Run Unusual Activity monitor (Feature 3)"""
    if unusual_activity_monitor:
        logger.info("🔍 Starting Unusual Activity Monitor...")
        try:
            unusual_activity_monitor.run_continuous(watchlist_manager)
        except Exception as e:
            logger.error(f"❌ Unusual Activity monitor error: {str(e)}")

# Sunday earnings routine
def get_october_2025_earnings():
    """Get earnings for October 2025"""
    today = datetime.now()
    earnings_by_week = {
        42: [
            {'symbol': 'JPM', 'company': 'JPMorgan', 'date': 'Oct 11', 'time': 'Before Market', 'period': 'Q3'},
            {'symbol': 'WFC', 'company': 'Wells Fargo', 'date': 'Oct 11', 'time': 'Before Market', 'period': 'Q3'},
        ],
        43: [
            {'symbol': 'TSLA', 'company': 'Tesla', 'date': 'Oct 23', 'time': 'After Market', 'period': 'Q3'},
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
    return {
        'this_week': earnings_by_week.get(current_week, []),
        'next_week': earnings_by_week.get(current_week + 1, []),
        'current_week': current_week
    }

def sunday_earnings_routine():
    """Sunday earnings routine"""
    logger.info("\n" + "=" * 80)
    logger.info("🗓️ SUNDAY EARNINGS ROUTINE - STARTING")
    logger.info("=" * 80)
    
    try:
        watchlist_symbols = watchlist_manager.load_symbols()
        earnings_data = get_october_2025_earnings()
        
        all_earnings = earnings_data['this_week'] + earnings_data['next_week']
        all_earnings_symbols = [e['symbol'] for e in all_earnings]
        
        earnings_manager.update_earnings_symbols(all_earnings_symbols, {
            'week': earnings_data['current_week'],
            'this_week_count': len(earnings_data['this_week']),
            'next_week_count': len(earnings_data['next_week'])
        })
        
        logger.info(f"✅ Updated earnings watchlist: {len(all_earnings_symbols)} symbols")
        
    except Exception as e:
        logger.error(f"❌ Sunday earnings routine failed: {str(e)}")
    
    logger.info("=" * 80 + "\n")

def schedule_sunday_routine():
    """Schedule Sunday routine"""
    scheduler.add_job(
        sunday_earnings_routine,
        CronTrigger(day_of_week='sun', hour=20, minute=0),
        id='sunday_earnings',
        name='Sunday Weekly Earnings',
        replace_existing=True
    )
    logger.info("📅 Scheduled: Sunday earnings routine")

# SEE PART 2 FOR API ROUTES AND MAIN SECTION
"""
backend/app.py - Part 2 of 2 - API ROUTES

APPEND THIS TO PART 1

This contains all Flask routes + main section
"""

# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route('/')
def index():
    """Serve dashboard"""
    return send_from_directory(app.static_folder, 'professional_dashboard.html')


@app.route('/api/analyze/<symbol>')
def analyze_symbol(symbol):
    """Analyze symbol"""
    try:
        symbol = symbol.upper()
        logger.info(f"Analyzing {symbol}...")
        
        result = analyzer.generate_professional_signal(symbol)
        
        if metrics_tracker and result.get('alert_type') not in ['MONITOR', None]:
            try:
                signal_id = metrics_tracker.record_signal(result)
                logger.debug(f"📊 Tracked signal: {signal_id}")
            except Exception as e:
                logger.error(f"⚠️ Metrics tracking failed: {str(e)}")
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {str(e)}")
        return jsonify({'symbol': symbol, 'error': str(e), 'signal': None}), 500


@app.route('/api/gex/<symbol>')
def get_gex_analysis(symbol):
    """Get GEX analysis"""
    try:
        symbol = symbol.upper()
        price = request.args.get('price', type=float)  # Get ?price= parameter
        logger.info(f"📊 GEX analysis requested for {symbol}" + (f" with price={price}" if price else ""))
        result = analyzer.analyze_full_gex(symbol, price)  # Pass price
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting GEX: {str(e)}")
        return jsonify({'symbol': symbol, 'error': str(e), 'available': False}), 500


@app.route('/api/watchlist')
def get_watchlist():
    """Get watchlist"""
    try:
        symbols = watchlist_manager.load_symbols()
        return jsonify({'symbols': symbols, 'count': len(symbols), 'path': watchlist_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# EARNINGS API ENDPOINTS
# ============================================================================

@app.route('/api/earnings/status')
def get_earnings_status():
    """Get earnings status"""
    try:
        return jsonify(earnings_manager.get_status())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/earnings/enable', methods=['POST'])
def enable_earnings():
    """Enable earnings monitoring"""
    try:
        earnings_manager.enable()
        if alert_manager:
            alert_manager.earnings_manager = EarningsStateManager()
        logger.info("✅ Earnings monitoring enabled")
        return jsonify({'success': True, 'status': earnings_manager.get_status()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/earnings/disable', methods=['POST'])
def disable_earnings():
    """Disable earnings monitoring"""
    try:
        earnings_manager.disable()
        if alert_manager:
            alert_manager.earnings_manager = EarningsStateManager()
        logger.info("📕 Earnings monitoring disabled")
        return jsonify({'success': True, 'status': earnings_manager.get_status()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# WALL STRENGTH API ENDPOINTS (NEW!)
# ============================================================================

@app.route('/api/wall-strength/<symbol>')
def get_wall_strength(symbol):
    """Get wall strength analysis"""
    try:
        symbol = symbol.upper()
        logger.info(f"📊 Wall strength requested for {symbol}")
        result = analyzer.wall_tracker.get_wall_strength_summary(symbol)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting wall strength: {str(e)}")
        return jsonify({'symbol': symbol, 'available': False, 'error': str(e)}), 500


@app.route('/api/wall-alerts/<symbol>')
def get_wall_alerts(symbol):
    """Get recent wall alerts"""
    try:
        symbol = symbol.upper()
        limit = int(request.args.get('limit', 10))
        alerts = analyzer.wall_tracker.get_recent_alerts(symbol, limit=limit)
        return jsonify({'symbol': symbol, 'alerts': alerts, 'count': len(alerts)})
    except Exception as e:
        return jsonify({'symbol': symbol, 'error': str(e)}), 500


@app.route('/api/wall-strength/status')
def get_wall_strength_monitor_status():
    """Get Wall Strength monitor status"""
    if not wall_strength_monitor:
        return jsonify({'enabled': False, 'error': 'Monitor not available'}), 503
    
    return jsonify({
        'enabled': wall_strength_monitor.enabled,
        'check_interval': wall_strength_monitor.check_interval,
        'market_hours_only': wall_strength_monitor.market_hours_only,
        'cooldown_minutes': wall_strength_monitor.cooldown_minutes,
        'is_market_hours': wall_strength_monitor.is_market_hours(),
        'stats': wall_strength_monitor.stats,
        'tracker_stats': analyzer.wall_tracker.get_statistics()
    })


@app.route('/api/wall-strength/check', methods=['POST'])
def trigger_wall_strength_check():
    """Manually trigger wall strength check"""
    if not wall_strength_monitor:
        return jsonify({'error': 'Monitor not available'}), 503
    
    try:
        watchlist = watchlist_manager.load_symbols()
        alerts_sent = wall_strength_monitor.run_single_check(watchlist)
        return jsonify({'success': True, 'alerts_sent': alerts_sent, 'stats': wall_strength_monitor.stats})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# UNUSUAL ACTIVITY API ENDPOINTS (Feature 3)
# ============================================================================

@app.route('/api/unusual-activity/<symbol>')
def get_unusual_activity(symbol):
    """Get unusual activity analysis"""
    try:
        symbol = symbol.upper()
        logger.info(f"🔍 Unusual activity requested for {symbol}")
        
        # Get options data and analyze
        options_data = analyzer.get_options_chain(symbol)
        if not options_data:
            return jsonify({
                'symbol': symbol,
                'detected': False,
                'reason': 'No options data available'
            })
        
        quote = analyzer.get_real_time_quote(symbol)
        current_price = quote.get('price', 0)
        
        result = analyzer.unusual_activity_detector.analyze_unusual_activity(
            symbol,
            options_data,
            current_price
        )
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting unusual activity: {str(e)}")
        return jsonify({
            'symbol': symbol,
            'detected': False,
            'error': str(e)
        }), 500


@app.route('/api/unusual-activity/alerts/<symbol>')
def get_unusual_activity_alerts(symbol):
    """Get recent unusual activity alerts"""
    try:
        symbol = symbol.upper()
        limit = int(request.args.get('limit', 10))
        alerts = analyzer.unusual_activity_detector.get_recent_alerts(symbol, limit=limit)
        return jsonify({
            'symbol': symbol,
            'alerts': alerts,
            'count': len(alerts)
        })
    except Exception as e:
        return jsonify({'symbol': symbol, 'error': str(e)}), 500


@app.route('/api/unusual-activity/status')
def get_unusual_activity_monitor_status():
    """Get Unusual Activity monitor status"""
    if not unusual_activity_monitor:
        return jsonify({'enabled': False, 'error': 'Monitor not available'}), 503
    
    return jsonify({
        'enabled': unusual_activity_monitor.enabled,
        'check_interval': unusual_activity_monitor.check_interval,
        'market_hours_only': unusual_activity_monitor.market_hours_only,
        'cooldown_minutes': unusual_activity_monitor.cooldown_minutes,
        'is_market_hours': unusual_activity_monitor.is_market_hours(),
        'stats': unusual_activity_monitor.stats,
        'detector_stats': analyzer.unusual_activity_detector.get_statistics()
    })


@app.route('/api/unusual-activity/check', methods=['POST'])
def trigger_unusual_activity_check():
    """Manually trigger unusual activity check"""
    if not unusual_activity_monitor:
        return jsonify({'error': 'Monitor not available'}), 503
    
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


# ============================================================================
# PIN PROBABILITY API ENDPOINTS (Feature #4)
# ============================================================================

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
        
        # Get current price
        quote = analyzer.get_real_time_quote(symbol)
        current_price = quote.get('price', 0)
        
        if current_price == 0:
            return jsonify({
                'symbol': symbol,
                'available': False,
                'reason': 'Unable to get current price'
            }), 400
        
        # Get options data and GEX analysis
        gamma_data = analyzer.analyze_full_gex(symbol, current_price)
        
        if not gamma_data.get('available'):
            return jsonify({
                'symbol': symbol,
                'available': False,
                'reason': 'No options data available'
            })
        
        # Get options chain for max pain calculation
        options_data = analyzer.get_options_chain(symbol)
        
        if not options_data:
            return jsonify({
                'symbol': symbol,
                'available': False,
                'reason': 'No options chain available'
            })
        
        # Get expiration date from gamma data
        expiration = gamma_data.get('expiration', datetime.now().strftime('%Y%m%d'))
        
        # Calculate pin probability
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


# ============================================================================
# CONFLUENCE ALERT SYSTEM API ENDPOINTS (Feature #5)
# ============================================================================

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
        
        # Get complete analysis (includes all signals)
        analysis_data = analyzer.generate_professional_signal(symbol)
        
        if not analysis_data:
            return jsonify({
                'symbol': symbol,
                'available': False,
                'reason': 'Unable to analyze symbol'
            }), 400
        
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


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.route('/api/health')
def health_check():
    """Health check"""
    earnings_status = earnings_manager.get_status()
    
    return jsonify({
        'status': 'healthy',
        'version': '4.4-wall-strength-unusual-activity',
        'polygon_enabled': bool(POLYGON_API_KEY),
        'alerts_enabled': alert_manager is not None,
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
    print("🚀 STARTING PROFESSIONAL TRADING DASHBOARD v4.4")
    print("   (WITH WALL STRENGTH + UNUSUAL ACTIVITY)")
    print("=" * 60)
    print(f"\n📊 Dashboard: http://localhost:5001")
    print(f"🩺 Health: http://localhost:5001/api/health")
    
    # Show earnings status
    earnings_status = earnings_manager.get_status()
    print(f"\n📅 Earnings: {'✅ ENABLED' if earnings_status['enabled'] else '📕 DISABLED'}")
    print(f"📊 Earnings Symbols: {earnings_status['symbols_count']}")
    
    # Schedule Sunday routine
    schedule_sunday_routine()
    
    # Start alert system
    if alert_manager:
        print(f"\n📢 Starting Alert System...")
        alert_thread = threading.Thread(target=run_alert_system, daemon=True)
        alert_thread.start()
        print(f"   ✅ Alert system started")
    
    # Start Wall Strength Monitor (NEW!)
    if wall_strength_monitor:
        print(f"\n📊 Starting Wall Strength Monitor...")
        wall_strength_thread = threading.Thread(target=run_wall_strength_monitor, daemon=True)
        wall_strength_thread.start()
        print(f"   ✅ Wall strength monitor started")
        print(f"   🕐 Tracks OI/Volume changes every 5 minutes")
        print(f"   📡 Routes to: DISCORD_ODTE_LEVELS")
    
    # Start Unusual Activity Monitor (Feature 3)
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
    print(f"   • 5-minute monitoring during market hours")
    print("=" * 60 + "\n")
    
    # Start Flask server
    app.run(host='0.0.0.0', port=5001, debug=False)