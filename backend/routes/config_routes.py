"""
backend/routes/config_routes.py
API Routes for Alert Management Console

Endpoints:
- GET /api/config - Get full configuration
- GET /api/config/<monitor> - Get specific monitor config
- POST /api/config/<monitor> - Update specific monitor
- POST /api/config/save-all - Save all configuration
- POST /api/config/reset - Reset to defaults
- POST /api/restart-monitors - Restart all monitors
- POST /api/test-alert/<monitor> - Send test alert
- GET /api/stats/<monitor> - Get monitor statistics
- GET /api/stats/all - Get all statistics
"""

from flask import Blueprint, jsonify, request
import logging
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from utils.config_manager import ConfigManager

# Create blueprint
config_bp = Blueprint('config', __name__)
logger = logging.getLogger(__name__)

# Initialize config manager (will be set by app.py)
config_manager = None
alert_manager = None
monitor_instances = {}


def init_config_routes(app_config_manager, app_alert_manager, monitors: dict):
    """
    Initialize config routes with manager instances
    
    Args:
        app_config_manager: ConfigManager instance
        app_alert_manager: AlertManager instance
        monitors: Dict of monitor instances
    """
    global config_manager, alert_manager, monitor_instances
    config_manager = app_config_manager
    alert_manager = app_alert_manager
    monitor_instances = monitors
    
    logger.info("✅ Config routes initialized")


# ============================================================================
# CONFIGURATION ENDPOINTS
# ============================================================================

@config_bp.route('/api/config', methods=['GET'])
def get_full_config():
    """Get complete configuration"""
    try:
        if not config_manager:
            return jsonify({'error': 'Config manager not initialized'}), 500
        
        config = config_manager.get_all_config()
        
        # Add Discord channel mapping
        channels = config_manager.get_discord_channels()
        
        # Add monitor stats
        stats = {}
        for name, monitor in monitor_instances.items():
            if hasattr(monitor, 'stats'):
                stats[name] = monitor.stats
        
        return jsonify({
            'config': config,
            'discord_channels': channels,
            'stats': stats,
            'summary': config_manager.get_stats_summary()
        })
    
    except Exception as e:
        logger.error(f"Error getting config: {str(e)}")
        return jsonify({'error': str(e)}), 500


@config_bp.route('/api/config/<monitor_name>', methods=['GET'])
def get_monitor_config(monitor_name):
    """Get configuration for specific monitor"""
    try:
        if not config_manager:
            return jsonify({'error': 'Config manager not initialized'}), 500
        
        config = config_manager.get_monitor_config(monitor_name)
        
        if not config:
            return jsonify({'error': f'Monitor not found: {monitor_name}'}), 404
        
        return jsonify({
            'monitor': monitor_name,
            'config': config
        })
    
    except Exception as e:
        logger.error(f"Error getting monitor config: {str(e)}")
        return jsonify({'error': str(e)}), 500


@config_bp.route('/api/config/<monitor_name>', methods=['POST'])
def update_monitor_config(monitor_name):
    """Update configuration for specific monitor"""
    try:
        if not config_manager:
            return jsonify({'error': 'Config manager not initialized'}), 500
        
        updates = request.json
        
        if not updates:
            return jsonify({'error': 'No updates provided'}), 400
        
        # Validate updates
        is_valid, errors = validate_monitor_updates(monitor_name, updates)
        if not is_valid:
            return jsonify({'error': 'Invalid configuration', 'details': errors}), 400
        
        # Update config
        success = config_manager.update_monitor_config(monitor_name, updates)
        
        if success:
            # Hot-reload monitor if possible
            reload_monitor(monitor_name, updates)
            
            logger.info(f"✅ Updated config for {monitor_name}")
            return jsonify({
                'success': True,
                'monitor': monitor_name,
                'message': 'Configuration updated successfully'
            })
        else:
            return jsonify({'error': 'Failed to save configuration'}), 500
    
    except Exception as e:
        logger.error(f"Error updating monitor config: {str(e)}")
        return jsonify({'error': str(e)}), 500


@config_bp.route('/api/config/save-all', methods=['POST'])
def save_all_config():
    """Save complete configuration"""
    try:
        if not config_manager:
            return jsonify({'error': 'Config manager not initialized'}), 500
        
        updates = request.json
        
        if not updates:
            return jsonify({'error': 'No configuration provided'}), 400
        
        # Validate all updates
        is_valid, errors = config_manager.validate_config(updates)
        if not is_valid:
            return jsonify({'error': 'Invalid configuration', 'details': errors}), 400
        
        # Save config
        success = config_manager.save_config(updates)
        
        if success:
            logger.info("✅ Saved complete configuration")
            return jsonify({
                'success': True,
                'message': 'All configuration saved successfully',
                'backup_created': True
            })
        else:
            return jsonify({'error': 'Failed to save configuration'}), 500
    
    except Exception as e:
        logger.error(f"Error saving config: {str(e)}")
        return jsonify({'error': str(e)}), 500


@config_bp.route('/api/config/reset', methods=['POST'])
def reset_config():
    """Reset configuration to defaults"""
    try:
        if not config_manager:
            return jsonify({'error': 'Config manager not initialized'}), 500
        
        # Create backup before reset
        backup_path = config_manager.create_backup()
        
        # Reset to defaults
        success = config_manager.reset_to_defaults()
        
        if success:
            logger.info("✅ Configuration reset to defaults")
            return jsonify({
                'success': True,
                'message': 'Configuration reset to defaults',
                'backup_path': backup_path
            })
        else:
            return jsonify({'error': 'Failed to reset configuration'}), 500
    
    except Exception as e:
        logger.error(f"Error resetting config: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# MONITOR CONTROL ENDPOINTS
# ============================================================================

@config_bp.route('/api/restart-monitors', methods=['POST'])
def restart_monitors():
    """Restart all monitors"""
    try:
        logger.info("🔄 Restarting all monitors...")
        
        # Reload config
        if config_manager:
            config_manager.load_config()
        
        # Restart each monitor
        restarted = []
        failed = []
        
        for name, monitor in monitor_instances.items():
            try:
                if hasattr(monitor, 'reload_config'):
                    monitor.reload_config()
                    restarted.append(name)
                else:
                    logger.warning(f"{name}: No reload_config method")
            except Exception as e:
                logger.error(f"Failed to restart {name}: {str(e)}")
                failed.append(name)
        
        return jsonify({
            'success': True,
            'restarted': restarted,
            'failed': failed,
            'message': f'Restarted {len(restarted)} monitors'
        })
    
    except Exception as e:
        logger.error(f"Error restarting monitors: {str(e)}")
        return jsonify({'error': str(e)}), 500


@config_bp.route('/api/test-alert/<monitor_name>', methods=['POST'])
def test_alert(monitor_name):
    """Send test alert for specific monitor"""
    try:
        logger.info(f"🧪 Sending test alert for {monitor_name}")
        
        # Map monitor names to test methods
        test_methods = {
            'realtime_volume': send_test_volume_alert,
            'extended_hours': send_test_extended_hours_alert,
            'market_impact': send_test_market_impact_alert,
            'openai': send_test_openai_alert,
            'odte': send_test_odte_alert,
            'wall_strength': send_test_wall_strength_alert,
            'unusual_activity': send_test_unusual_activity_alert,
            'momentum': send_test_momentum_alert
        }
        
        test_method = test_methods.get(monitor_name)
        
        if not test_method:
            return jsonify({'error': f'Unknown monitor: {monitor_name}'}), 404
        
        # Send test alert
        success = test_method()
        
        if success:
            return jsonify({
                'success': True,
                'monitor': monitor_name,
                'message': 'Test alert sent to Discord'
            })
        else:
            return jsonify({'error': 'Failed to send test alert'}), 500
    
    except Exception as e:
        logger.error(f"Error sending test alert: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# STATISTICS ENDPOINTS
# ============================================================================

@config_bp.route('/api/stats/<monitor_name>', methods=['GET'])
def get_monitor_stats(monitor_name):
    """Get statistics for specific monitor"""
    try:
        monitor = monitor_instances.get(monitor_name)
        
        if not monitor:
            return jsonify({'error': f'Monitor not found: {monitor_name}'}), 404
        
        if not hasattr(monitor, 'stats'):
            return jsonify({'error': f'Monitor has no stats: {monitor_name}'}), 404
        
        return jsonify({
            'monitor': monitor_name,
            'stats': monitor.stats
        })
    
    except Exception as e:
        logger.error(f"Error getting monitor stats: {str(e)}")
        return jsonify({'error': str(e)}), 500


@config_bp.route('/api/stats/all', methods=['GET'])
def get_all_stats():
    """Get statistics for all monitors"""
    try:
        all_stats = {}
        
        for name, monitor in monitor_instances.items():
            if hasattr(monitor, 'stats'):
                all_stats[name] = monitor.stats
        
        return jsonify({
            'stats': all_stats,
            'summary': {
                'total_monitors': len(monitor_instances),
                'active_monitors': len([m for m in monitor_instances.values() if hasattr(m, 'enabled') and m.enabled])
            }
        })
    
    except Exception as e:
        logger.error(f"Error getting all stats: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def validate_monitor_updates(monitor_name: str, updates: dict) -> tuple[bool, list]:
    """Validate monitor configuration updates"""
    errors = []
    
    # Common validations
    if 'check_interval' in updates:
        interval = updates['check_interval']
        if not isinstance(interval, (int, float)) or interval <= 0:
            errors.append('check_interval must be positive number')
    
    if 'cooldown' in updates:
        cooldown = updates['cooldown']
        if not isinstance(cooldown, (int, float)) or cooldown < 0:
            errors.append('cooldown must be non-negative number')
    
    # Monitor-specific validations
    if monitor_name == 'realtime_volume':
        if 'rvol_threshold' in updates:
            if updates['rvol_threshold'] < 1.0 or updates['rvol_threshold'] > 10.0:
                errors.append('rvol_threshold must be between 1.0 and 10.0')
        
        if 'price_filter' in updates:
            if updates['price_filter'] < 0 or updates['price_filter'] > 10.0:
                errors.append('price_filter must be between 0 and 10.0')
    
    return len(errors) == 0, errors


def reload_monitor(monitor_name: str, config: dict):
    """Hot-reload monitor with new configuration"""
    try:
        monitor = monitor_instances.get(monitor_name)
        
        if not monitor:
            logger.warning(f"Monitor not found for reload: {monitor_name}")
            return
        
        # Update monitor configuration
        if hasattr(monitor, 'enabled'):
            monitor.enabled = config.get('enabled', monitor.enabled)
        
        if hasattr(monitor, 'check_interval'):
            monitor.check_interval = config.get('check_interval', monitor.check_interval)
        
        if hasattr(monitor, 'cooldown_minutes'):
            monitor.cooldown_minutes = config.get('cooldown', monitor.cooldown_minutes)
        
        # Monitor-specific reloads
        if monitor_name == 'realtime_volume':
            if hasattr(monitor, 'thresholds'):
                monitor.thresholds['ELEVATED'] = config.get('rvol_threshold', monitor.thresholds['ELEVATED'])
            if hasattr(monitor, 'min_price_change_pct'):
                monitor.min_price_change_pct = config.get('price_filter', monitor.min_price_change_pct)
        
        logger.info(f"✅ Hot-reloaded {monitor_name}")
    
    except Exception as e:
        logger.error(f"Error reloading {monitor_name}: {str(e)}")


# ============================================================================
# TEST ALERT FUNCTIONS
# ============================================================================

def send_test_volume_alert() -> bool:
    """Send test volume spike alert"""
    try:
        monitor = monitor_instances.get('realtime_volume')
        if not monitor or not hasattr(monitor, 'discord_webhook'):
            return False
        
        import requests
        
        embed = {
            'title': '🧪 TEST ALERT - Volume Spike Monitor',
            'description': 'This is a test alert from the Alert Management Console',
            'color': 0x00ff00,
            'fields': [
                {'name': 'Monitor', 'value': 'Realtime Volume Spike', 'inline': True},
                {'name': 'Status', 'value': '✅ Active', 'inline': True},
                {'name': 'Test Time', 'value': 'Now', 'inline': True}
            ]
        }
        
        response = requests.post(
            monitor.discord_webhook,
            json={'embeds': [embed]},
            timeout=10
        )
        response.raise_for_status()
        
        return True
    except Exception as e:
        logger.error(f"Test alert failed: {str(e)}")
        return False


def send_test_extended_hours_alert() -> bool:
    """Send test extended hours alert"""
    # Similar to send_test_volume_alert but for extended hours
    return send_generic_test_alert('extended_hours', 'Extended Hours Volume Monitor')


def send_test_market_impact_alert() -> bool:
    """Send test market impact alert"""
    return send_generic_test_alert('market_impact', 'Market Impact Monitor')


def send_test_openai_alert() -> bool:
    """Send test OpenAI alert"""
    return send_generic_test_alert('openai', 'OpenAI News Monitor')


def send_test_odte_alert() -> bool:
    """Send test 0DTE alert"""
    return send_generic_test_alert('odte', '0DTE Gamma Monitor')


def send_test_wall_strength_alert() -> bool:
    """Send test wall strength alert"""
    return send_generic_test_alert('wall_strength', 'Wall Strength Monitor')


def send_test_unusual_activity_alert() -> bool:
    """Send test unusual activity alert"""
    return send_generic_test_alert('unusual_activity', 'Unusual Activity Monitor')


def send_test_momentum_alert() -> bool:
    """Send test momentum alert"""
    return send_generic_test_alert('momentum', 'Momentum Signal Monitor')


def send_generic_test_alert(monitor_name: str, display_name: str) -> bool:
    """Send generic test alert"""
    try:
        monitor = monitor_instances.get(monitor_name)
        if not monitor or not hasattr(monitor, 'discord_webhook'):
            logger.warning(f"Monitor {monitor_name} not found or no webhook")
            return False
        
        import requests
        from datetime import datetime
        
        embed = {
            'title': f'🧪 TEST ALERT - {display_name}',
            'description': 'This is a test alert from the Alert Management Console',
            'color': 0x00ff00,
            'fields': [
                {'name': 'Monitor', 'value': display_name, 'inline': True},
                {'name': 'Status', 'value': '✅ Active', 'inline': True},
                {'name': 'Test Time', 'value': datetime.now().strftime('%H:%M:%S ET'), 'inline': True}
            ],
            'footer': {
                'text': 'Alert Management Console • Test Mode'
            }
        }
        
        response = requests.post(
            monitor.discord_webhook,
            json={'embeds': [embed]},
            timeout=10
        )
        response.raise_for_status()
        
        logger.info(f"✅ Test alert sent for {monitor_name}")
        return True
    
    except Exception as e:
        logger.error(f"Test alert failed for {monitor_name}: {str(e)}")
        return False


# Export blueprint
__all__ = ['config_bp', 'init_config_routes']