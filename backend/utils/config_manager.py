"""
backend/utils/config_manager.py
Configuration Manager for Alert Console

Handles:
- Reading/writing config.yaml
- Validating configuration changes
- Hot-reloading monitors without restart
- Backup and restore
"""

import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from datetime import datetime
import shutil


class ConfigManager:
    def __init__(self, config_path: str = None):
        """
        Initialize Configuration Manager
        
        Args:
            config_path: Path to config.yaml (default: backend/config/config.yaml)
        """
        self.logger = logging.getLogger(__name__)
        
        if config_path is None:
            backend_dir = Path(__file__).parent.parent
            config_path = os.path.join(backend_dir, 'config', 'config.yaml')
        
        self.config_path = config_path
        self.backup_dir = os.path.join(os.path.dirname(config_path), 'backups')
        
        # Create backup directory
        os.makedirs(self.backup_dir, exist_ok=True)
        
        self.config = self.load_config()
        
        self.logger.info(f"✅ Config Manager initialized: {config_path}")
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            self.logger.info("✅ Configuration loaded successfully")
            return config
        
        except Exception as e:
            self.logger.error(f"❌ Failed to load config: {str(e)}")
            return {}
    
    def save_config(self, config: Dict[str, Any] = None) -> bool:
        """
        Save configuration to YAML file
        
        Args:
            config: Configuration dict (uses self.config if None)
        
        Returns:
            True if saved successfully
        """
        if config is None:
            config = self.config
        
        try:
            # Create backup first
            self.create_backup()
            
            # Write new config
            with open(self.config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
            self.config = config
            self.logger.info("✅ Configuration saved successfully")
            return True
        
        except Exception as e:
            self.logger.error(f"❌ Failed to save config: {str(e)}")
            return False
    
    def create_backup(self) -> str:
        """
        Create backup of current config
        
        Returns:
            Path to backup file
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join(self.backup_dir, f'config_backup_{timestamp}.yaml')
            
            shutil.copy2(self.config_path, backup_path)
            
            self.logger.info(f"✅ Config backup created: {backup_path}")
            
            # Keep only last 10 backups
            self.cleanup_old_backups()
            
            return backup_path
        
        except Exception as e:
            self.logger.error(f"❌ Failed to create backup: {str(e)}")
            return ""
    
    def cleanup_old_backups(self, keep_count: int = 10):
        """Remove old backups, keeping only the most recent"""
        try:
            backups = sorted(
                Path(self.backup_dir).glob('config_backup_*.yaml'),
                key=os.path.getmtime,
                reverse=True
            )
            
            # Remove old backups
            for backup in backups[keep_count:]:
                os.remove(backup)
                self.logger.debug(f"Removed old backup: {backup}")
        
        except Exception as e:
            self.logger.error(f"Error cleaning up backups: {str(e)}")
    
    def restore_backup(self, backup_path: str = None) -> bool:
        """
        Restore configuration from backup
        
        Args:
            backup_path: Path to backup file (uses most recent if None)
        
        Returns:
            True if restored successfully
        """
        try:
            if backup_path is None:
                # Get most recent backup
                backups = sorted(
                    Path(self.backup_dir).glob('config_backup_*.yaml'),
                    key=os.path.getmtime,
                    reverse=True
                )
                
                if not backups:
                    self.logger.error("No backups found")
                    return False
                
                backup_path = str(backups[0])
            
            # Restore backup
            shutil.copy2(backup_path, self.config_path)
            self.config = self.load_config()
            
            self.logger.info(f"✅ Config restored from: {backup_path}")
            return True
        
        except Exception as e:
            self.logger.error(f"❌ Failed to restore backup: {str(e)}")
            return False
    
    def get_monitor_config(self, monitor_name: str) -> Dict[str, Any]:
        """
        Get configuration for specific monitor
        
        Args:
            monitor_name: Monitor name (e.g., 'realtime_volume_spike')
        
        Returns:
            Monitor configuration dict
        """
        # Map monitor names to config keys
        config_map = {
            'realtime_volume': 'realtime_volume_spike_monitor',
            'extended_hours': 'extended_hours_volume_monitor',
            'market_impact': 'market_impact_monitor',
            'openai': 'openai_monitor',
            'odte': 'odte_gamma_monitor',
            'wall_strength': 'wall_strength_monitor',
            'unusual_activity': 'unusual_activity_monitor',
            'momentum': 'momentum_signal_monitor'
        }
        
        config_key = config_map.get(monitor_name, monitor_name)
        
        return self.config.get(config_key, {})
    
    def update_monitor_config(self, monitor_name: str, updates: Dict[str, Any]) -> bool:
        """
        Update configuration for specific monitor
        
        Args:
            monitor_name: Monitor name
            updates: Dictionary of updates
        
        Returns:
            True if updated successfully
        """
        try:
            # Map monitor names to config keys
            config_map = {
                'realtime_volume': 'realtime_volume_spike_monitor',
                'extended_hours': 'extended_hours_volume_monitor',
                'market_impact': 'market_impact_monitor',
                'openai': 'openai_monitor',
                'odte': 'odte_gamma_monitor',
                'wall_strength': 'wall_strength_monitor',
                'unusual_activity': 'unusual_activity_monitor',
                'momentum': 'momentum_signal_monitor'
            }
            
            config_key = config_map.get(monitor_name, monitor_name)
            
            # Update config
            if config_key not in self.config:
                self.config[config_key] = {}
            
            self.config[config_key].update(updates)
            
            # Save to file
            return self.save_config()
        
        except Exception as e:
            self.logger.error(f"❌ Failed to update {monitor_name}: {str(e)}")
            return False
    
    def get_global_config(self) -> Dict[str, Any]:
        """Get global configuration settings"""
        return {
            'analysis': self.config.get('analysis', {}),
            'market_schedule': self.config.get('market_schedule', {}),
            'discord': self.config.get('discord', {}),
            'signal_metrics': self.config.get('signal_metrics', {})
        }
    
    def update_global_config(self, section: str, updates: Dict[str, Any]) -> bool:
        """
        Update global configuration section
        
        Args:
            section: Section name (e.g., 'analysis', 'discord')
            updates: Dictionary of updates
        
        Returns:
            True if updated successfully
        """
        try:
            if section not in self.config:
                self.config[section] = {}
            
            self.config[section].update(updates)
            
            return self.save_config()
        
        except Exception as e:
            self.logger.error(f"❌ Failed to update {section}: {str(e)}")
            return False
    
    def reset_to_defaults(self) -> bool:
        """Reset configuration to default values"""
        try:
            # Create backup before reset
            self.create_backup()
            
            # Load default config template
            default_config_path = os.path.join(
                os.path.dirname(self.config_path),
                'config.default.yaml'
            )
            
            if os.path.exists(default_config_path):
                with open(default_config_path, 'r') as f:
                    default_config = yaml.safe_load(f)
                
                self.config = default_config
                return self.save_config()
            else:
                self.logger.warning("Default config not found, keeping current config")
                return False
        
        except Exception as e:
            self.logger.error(f"❌ Failed to reset config: {str(e)}")
            return False
    
    def validate_config(self, config: Dict[str, Any] = None) -> tuple[bool, list]:
        """
        Validate configuration
        
        Args:
            config: Configuration to validate (uses self.config if None)
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        if config is None:
            config = self.config
        
        errors = []
        
        # Validate monitor configs
        monitors = [
            'realtime_volume_spike_monitor',
            'extended_hours_volume_monitor',
            'market_impact_monitor',
            'openai_monitor',
            'odte_gamma_monitor',
            'wall_strength_monitor',
            'unusual_activity_monitor',
            'momentum_signal_monitor'
        ]
        
        for monitor in monitors:
            if monitor not in config:
                errors.append(f"Missing monitor config: {monitor}")
                continue
            
            monitor_config = config[monitor]
            
            # Check required fields
            if 'enabled' not in monitor_config:
                errors.append(f"{monitor}: Missing 'enabled' field")
            
            if 'check_interval' in monitor_config:
                interval = monitor_config['check_interval']
                if not isinstance(interval, (int, float)) or interval <= 0:
                    errors.append(f"{monitor}: Invalid check_interval")
        
        # Validate global settings
        if 'analysis' in config:
            analysis = config['analysis']
            if 'thresholds' in analysis:
                thresholds = analysis['thresholds']
                for key, value in thresholds.items():
                    if not isinstance(value, (int, float)) or value < 0:
                        errors.append(f"analysis.thresholds.{key}: Invalid value")
        
        is_valid = len(errors) == 0
        
        if not is_valid:
            self.logger.warning(f"⚠️ Config validation failed: {len(errors)} errors")
            for error in errors:
                self.logger.warning(f"  - {error}")
        
        return is_valid, errors
    
    def get_all_config(self) -> Dict[str, Any]:
        """Get complete configuration"""
        return self.config.copy()
    
    def get_discord_channels(self) -> Dict[str, str]:
        """Get Discord channel mapping"""
        discord_config = self.config.get('discord', {})
        
        return {
            'trading': discord_config.get('webhook_trading', ''),
            'news': discord_config.get('webhook_news', ''),
            'earnings_weekly': discord_config.get('webhook_earnings_weekly', ''),
            'earnings_realtime': discord_config.get('webhook_earnings_realtime', ''),
            'market_impact': discord_config.get('webhook_market_impact', ''),
            'volume_spike': discord_config.get('webhook_volume_spike', ''),
            'momentum_signals': discord_config.get('webhook_momentum_signals', ''),
            'odte_levels': discord_config.get('webhook_odte_levels', ''),
            'unusual_activity': discord_config.get('webhook_unusual_activity', ''),
            'openai_news': discord_config.get('webhook_openai_news', '')
        }
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """Get configuration statistics summary"""
        enabled_monitors = 0
        total_monitors = 0
        
        monitors = [
            'realtime_volume_spike_monitor',
            'extended_hours_volume_monitor',
            'market_impact_monitor',
            'openai_monitor',
            'odte_gamma_monitor',
            'wall_strength_monitor',
            'unusual_activity_monitor',
            'momentum_signal_monitor'
        ]
        
        for monitor in monitors:
            total_monitors += 1
            if self.config.get(monitor, {}).get('enabled', False):
                enabled_monitors += 1
        
        return {
            'total_monitors': total_monitors,
            'enabled_monitors': enabled_monitors,
            'disabled_monitors': total_monitors - enabled_monitors,
            'config_path': self.config_path,
            'last_modified': datetime.fromtimestamp(
                os.path.getmtime(self.config_path)
            ).isoformat() if os.path.exists(self.config_path) else None,
            'backup_count': len(list(Path(self.backup_dir).glob('config_backup_*.yaml')))
        }


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    manager = ConfigManager()
    
    print("=" * 80)
    print("CONFIG MANAGER TEST")
    print("=" * 80)
    
    # Get stats
    stats = manager.get_stats_summary()
    print(f"\nConfiguration Statistics:")
    print(f"  Total Monitors: {stats['total_monitors']}")
    print(f"  Enabled: {stats['enabled_monitors']}")
    print(f"  Disabled: {stats['disabled_monitors']}")
    print(f"  Backups: {stats['backup_count']}")
    
    # Get Discord channels
    channels = manager.get_discord_channels()
    print(f"\nDiscord Channels:")
    for name, url in channels.items():
        status = "✅" if url else "❌"
        print(f"  {status} {name}: {'configured' if url else 'not configured'}")
    
    # Validate config
    is_valid, errors = manager.validate_config()
    print(f"\nValidation: {'✅ PASSED' if is_valid else '❌ FAILED'}")
    if errors:
        for error in errors:
            print(f"  - {error}")
    
    print("\n" + "=" * 80)