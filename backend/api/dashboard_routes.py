"""
Dashboard API Routes
Endpoints for the main trading dashboard/screener
"""
from flask import Blueprint, jsonify, request
import logging
import sys
from pathlib import Path

# Ensure backend directory is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.watchlist_manager import watchlist_manager
from config import config

# Import analyzer (will be available after user adds the file)
try:
    from analyzers.enhanced_professional_analyzer import EnhancedProfessionalAnalyzer
    ANALYZER_AVAILABLE = True
except ImportError:
    ANALYZER_AVAILABLE = False
    print("⚠️  Enhanced analyzer not found. Add enhanced_professional_analyzer.py to backend/analyzers/")

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/watchlist', methods=['GET'])
def get_watchlist():
    """
    Get all symbols from watchlist
    
    Returns:
        JSON list of symbols
    """
    try:
        symbols = watchlist_manager.load_symbols()
        return jsonify({
            'success': True,
            'symbols': symbols,
            'count': len(symbols)
        })
    except Exception as e:
        logger.error(f"Error getting watchlist: {str(e)}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/watchlist/add', methods=['POST'])
def add_to_watchlist():
    """
    Add symbol to watchlist
    
    Request body:
        {
            "symbol": "AMD"
        }
    """
    try:
        data = request.get_json()
        symbol = data.get('symbol', '').upper()
        
        if not symbol:
            return jsonify({'error': 'Symbol is required'}), 400
        
        success = watchlist_manager.add_symbol(symbol)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'{symbol} added to watchlist'
            }), 201
        else:
            return jsonify({
                'success': False,
                'message': f'{symbol} already in watchlist'
            }), 200
            
    except Exception as e:
        logger.error(f"Error adding to watchlist: {str(e)}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/watchlist/remove', methods=['POST'])
def remove_from_watchlist():
    """
    Remove symbol from watchlist
    
    Request body:
        {
            "symbol": "AMD"
        }
    """
    try:
        data = request.get_json()
        symbol = data.get('symbol', '').upper()
        
        if not symbol:
            return jsonify({'error': 'Symbol is required'}), 400
        
        success = watchlist_manager.remove_symbol(symbol)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'{symbol} removed from watchlist'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'{symbol} not found in watchlist'
            }), 404
            
    except Exception as e:
        logger.error(f"Error removing from watchlist: {str(e)}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/analyze/<symbol>', methods=['GET'])
def analyze_symbol(symbol):
    """
    Analyze a single symbol with full professional analysis
    
    Args:
        symbol: Stock symbol to analyze
    """
    try:
        symbol = symbol.upper()
        
        if not ANALYZER_AVAILABLE:
            # Return placeholder data if analyzer not available
            return jsonify({
                'symbol': symbol,
                'message': 'Analyzer not available. Add enhanced_professional_analyzer.py',
                'current_price': 0,
                'vwap': 0,
                'signal': None,
                'alert_type': 'MONITOR',
                'confidence': 0,
                'bias_1h': 'NEUTRAL',
                'bias_daily': 'NEUTRAL',
                'options_sentiment': 'NEUTRAL',
                'dark_pool_activity': 'NEUTRAL',
                'news_sentiment': 'NEUTRAL'
            })
        
        # Initialize analyzer
        analyzer = EnhancedProfessionalAnalyzer(api_key=config.POLYGON_API_KEY)
        
        # Get full analysis
        result = analyzer.generate_professional_signal(symbol)
        
        # Ensure all required fields exist
        if 'error' in result:
            logger.error(f"Analysis error for {symbol}: {result['error']}")
            return jsonify({
                'symbol': symbol,
                'error': result['error'],
                'current_price': 0,
                'alert_type': 'ERROR'
            }), 500
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {str(e)}")
        return jsonify({
            'symbol': symbol,
            'error': str(e),
            'current_price': 0,
            'alert_type': 'ERROR'
        }), 500

@dashboard_bp.route('/analyze-all', methods=['GET'])
def analyze_all():
    """
    Analyze all symbols in watchlist
    
    Returns:
        JSON array of analysis results
    """
    try:
        symbols = watchlist_manager.load_symbols()
        
        if not ANALYZER_AVAILABLE:
            results = []
            for symbol in symbols:
                results.append({
                    'symbol': symbol,
                    'message': 'Add enhanced_professional_analyzer.py to enable analysis',
                    'signal': None,
                    'alert_type': 'MONITOR'
                })
            
            return jsonify({
                'success': True,
                'results': results,
                'count': len(results)
            })
        
        # Initialize analyzer once
        analyzer = EnhancedProfessionalAnalyzer(api_key=config.POLYGON_API_KEY)
        
        results = []
        for symbol in symbols:
            try:
                result = analyzer.generate_professional_signal(symbol)
                results.append(result)
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {str(e)}")
                results.append({
                    'symbol': symbol,
                    'error': str(e),
                    'alert_type': 'ERROR'
                })
        
        return jsonify({
            'success': True,
            'results': results,
            'count': len(results)
        })
        
    except Exception as e:
        logger.error(f"Error analyzing all: {str(e)}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/status', methods=['GET'])
def get_status():
    """Get dashboard status and capabilities"""
    return jsonify({
        'success': True,
        'analyzer_available': ANALYZER_AVAILABLE,
        'watchlist_count': len(watchlist_manager.load_symbols()),
        'api_key_set': bool(config.POLYGON_API_KEY)
    })