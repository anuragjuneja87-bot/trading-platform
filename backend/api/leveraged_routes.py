"""
Leveraged Calculator API Routes
Endpoints for leveraged ETF calculations
"""
from flask import Blueprint, jsonify, request
import logging

from analyzers.leveraged_calculator import leveraged_calculator

logger = logging.getLogger(__name__)

leveraged_bp = Blueprint('leveraged', __name__)

@leveraged_bp.route('/pairs', methods=['GET'])
def get_pairs():
    """
    Get all configured leveraged pairs
    
    Returns:
        JSON list of pairs
    """
    try:
        pairs = leveraged_calculator.get_pairs()
        return jsonify({
            'success': True,
            'pairs': pairs,
            'count': len(pairs)
        })
    except Exception as e:
        logger.error(f"Error getting pairs: {str(e)}")
        return jsonify({'error': str(e)}), 500

@leveraged_bp.route('/pairs', methods=['POST'])
def add_pair():
    """
    Add a new leveraged pair
    
    Request body:
        {
            "underlying": "NVDA",
            "leveraged": "NVDL",
            "name": "NVIDIA 1.5x"
        }
    """
    try:
        data = request.get_json()
        
        underlying = data.get('underlying', '').upper()
        leveraged = data.get('leveraged', '').upper()
        name = data.get('name', '')
        
        if not all([underlying, leveraged, name]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        result = leveraged_calculator.add_pair(underlying, leveraged, name)
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result), 201
        
    except Exception as e:
        logger.error(f"Error adding pair: {str(e)}")
        return jsonify({'error': str(e)}), 500

@leveraged_bp.route('/pairs/<pair_id>', methods=['PUT'])
def update_pair(pair_id):
    """
    Update an existing pair
    
    Request body:
        {
            "name": "New Name",
            "active": false
        }
    """
    try:
        data = request.get_json()
        result = leveraged_calculator.update_pair(pair_id, data)
        
        if 'error' in result:
            return jsonify(result), 404
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error updating pair: {str(e)}")
        return jsonify({'error': str(e)}), 500

@leveraged_bp.route('/pairs/<pair_id>', methods=['DELETE'])
def delete_pair(pair_id):
    """Delete a leveraged pair"""
    try:
        result = leveraged_calculator.delete_pair(pair_id)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error deleting pair: {str(e)}")
        return jsonify({'error': str(e)}), 500

@leveraged_bp.route('/calculate', methods=['GET'])
def calculate():
    """
    Calculate projected leveraged price
    
    Query params:
        underlying: Underlying symbol (e.g., NVDA)
        leveraged: Leveraged ETF symbol (e.g., NVDL)
        price: Projected underlying price
    
    Example:
        /api/leveraged/calculate?underlying=NVDA&leveraged=NVDL&price=150.50
    """
    try:
        underlying = request.args.get('underlying', '').upper()
        leveraged = request.args.get('leveraged', '').upper()
        price_str = request.args.get('price', '')
        
        if not all([underlying, leveraged, price_str]):
            return jsonify({'error': 'Missing required parameters'}), 400
        
        try:
            projected_price = float(price_str)
        except ValueError:
            return jsonify({'error': 'Invalid price value'}), 400
        
        result = leveraged_calculator.calculate_leveraged_price(
            underlying, leveraged, projected_price
        )
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify({
            'success': True,
            'calculation': result
        })
        
    except Exception as e:
        logger.error(f"Error calculating: {str(e)}")
        return jsonify({'error': str(e)}), 500

@leveraged_bp.route('/price/<symbol>', methods=['GET'])
def get_price(symbol):
    """
    Get current price for a symbol
    
    Args:
        symbol: Stock symbol
    
    Returns:
        Current price (cached for 30 seconds)
    """
    try:
        symbol = symbol.upper()
        price = leveraged_calculator.get_current_price(symbol)
        
        if price == 0:
            return jsonify({'error': f'Could not fetch price for {symbol}'}), 404
        
        return jsonify({
            'success': True,
            'symbol': symbol,
            'price': price
        })
        
    except Exception as e:
        logger.error(f"Error getting price for {symbol}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@leveraged_bp.route('/batch-prices', methods=['POST'])
def batch_prices():
    """
    Get current prices for multiple symbols
    
    Request body:
        {
            "symbols": ["NVDA", "NVDL", "PLTR", "PLTU"]
        }
    """
    try:
        data = request.get_json()
        symbols = data.get('symbols', [])
        
        if not symbols:
            return jsonify({'error': 'No symbols provided'}), 400
        
        prices = {}
        for symbol in symbols:
            symbol = symbol.upper()
            prices[symbol] = leveraged_calculator.get_current_price(symbol)
        
        return jsonify({
            'success': True,
            'prices': prices
        })
        
    except Exception as e:
        logger.error(f"Error getting batch prices: {str(e)}")
        return jsonify({'error': str(e)}), 500
