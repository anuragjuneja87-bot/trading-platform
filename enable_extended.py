#!/usr/bin/env python3
"""
Enable Extended Hours Monitoring
Quick script to set market_hours_only: false for all monitors
"""

import yaml
import sys
from datetime import datetime
from pathlib import Path

def enable_extended_hours(config_path='backend/config/config.yaml'):
    """Enable extended hours monitoring for all monitors"""
    
    print("="*80)
    print("ENABLING EXTENDED HOURS MONITORING")
    print("="*80)
    
    # Check if config exists
    if not Path(config_path).exists():
        # Try alternate paths
        alt_paths = ['config/config.yaml', '../config/config.yaml']
        for alt_path in alt_paths:
            if Path(alt_path).exists():
                config_path = alt_path
                break
        else:
            print(f"❌ Config file not found!")
            return False
    
    print(f"\n📄 Config file: {config_path}")
    
    # Backup
    backup_path = f"{config_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"💾 Creating backup: {backup_path}")
    
    try:
        with open(config_path, 'r') as f:
            content = f.read()
        
        with open(backup_path, 'w') as f:
            f.write(content)
        
        print(f"✅ Backup created")
    except Exception as e:
        print(f"❌ Backup failed: {str(e)}")
        return False
    
    # Load config
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Failed to load config: {str(e)}")
        return False
    
    # Monitors to modify
    monitors = [
        'unusual_activity_monitor',
        'momentum_signal_monitor',
        'wall_strength_monitor',
        'realtime_volume_spike_monitor',
        'volume_spike_monitor'
    ]
    
    changes_made = 0
    
    print(f"\n🔧 Modifying monitors...")
    
    for monitor_name in monitors:
        if monitor_name in config:
            current_value = config[monitor_name].get('market_hours_only', None)
            
            if current_value is True:
                config[monitor_name]['market_hours_only'] = False
                print(f"✅ {monitor_name}: True → False")
                changes_made += 1
            elif current_value is False:
                print(f"ℹ️  {monitor_name}: Already False (no change)")
            else:
                print(f"⚠️  {monitor_name}: market_hours_only not found")
        else:
            print(f"⚠️  {monitor_name}: Not in config (skipping)")
    
    # Save modified config
    if changes_made > 0:
        try:
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
            print(f"\n✅ Config updated successfully!")
            print(f"📝 Changes made: {changes_made}")
            
            # Verify changes
            print(f"\n🔍 Verifying changes...")
            with open(config_path, 'r') as f:
                updated_config = yaml.safe_load(f)
            
            all_correct = True
            for monitor_name in monitors:
                if monitor_name in updated_config:
                    value = updated_config[monitor_name].get('market_hours_only', None)
                    if value is False:
                        print(f"✅ {monitor_name}: False ✓")
                    elif value is True:
                        print(f"❌ {monitor_name}: Still True!")
                        all_correct = False
            
            if all_correct:
                print(f"\n🎉 All monitors set to extended hours mode!")
                print(f"\n📋 NEXT STEPS:")
                print(f"1. Restart your app: pkill -f app.py && python3 app.py")
                print(f"2. Watch logs: tail -f logs/always_on_trader.log")
                print(f"3. Check for 'market_hours_only: False' in initialization")
                print(f"4. Wait for alerts (even after-hours!)")
                return True
            else:
                print(f"\n⚠️  Some monitors may not have been updated correctly")
                print(f"Check the config file manually")
                return False
                
        except Exception as e:
            print(f"\n❌ Failed to save config: {str(e)}")
            print(f"Restoring from backup...")
            
            try:
                with open(backup_path, 'r') as f:
                    content = f.read()
                with open(config_path, 'w') as f:
                    f.write(content)
                print(f"✅ Config restored from backup")
            except:
                print(f"❌ Failed to restore backup!")
            
            return False
    else:
        print(f"\n✅ No changes needed - all monitors already set to extended hours!")
        return True

if __name__ == '__main__':
    print("\n")
    success = enable_extended_hours()
    
    if success:
        print("\n" + "="*80)
        print("SUCCESS - Extended hours monitoring enabled!")
        print("="*80)
        sys.exit(0)
    else:
        print("\n" + "="*80)
        print("FAILED - Please check errors above")
        print("="*80)
        sys.exit(1)
