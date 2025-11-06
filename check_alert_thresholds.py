#!/usr/bin/env python3
"""
Alert Threshold Diagnostic
Check why you're not getting unusual activity, volume spike, or momentum alerts
"""

import yaml
import os
from datetime import datetime

config_path = 'backend/config/config.yaml'

print("="*70)
print("ALERT THRESHOLD DIAGNOSTIC")
print("="*70)

# Load config
try:
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
except:
    print("❌ Could not load config.yaml")
    exit(1)

print("\n🔍 Checking threshold settings...\n")

issues_found = []

# Check Unusual Activity Monitor
if 'unusual_activity_monitor' in config:
    monitor = config['unusual_activity_monitor']
    enabled = monitor.get('enabled', False)
    
    print(f"📊 UNUSUAL ACTIVITY MONITOR:")
    print(f"   Enabled: {enabled}")
    
    if enabled:
        thresholds = monitor.get('thresholds', {})
        oi_change = thresholds.get('min_oi_change_pct', 0)
        vol_ratio = thresholds.get('min_volume_ratio', 0)
        min_score = thresholds.get('min_score', 0)
        
        print(f"   Min OI Change: {oi_change}%")
        print(f"   Min Volume Ratio: {vol_ratio}x")
        print(f"   Min Score: {min_score}")
        
        # Check if too strict
        if oi_change > 30:
            print(f"   ⚠️  OI threshold TOO HIGH! Should be 15-20%")
            issues_found.append(('unusual_activity', 'min_oi_change_pct', 15))
        elif oi_change > 20:
            print(f"   ✅ OI threshold OK (could be lower for more alerts)")
        else:
            print(f"   ✅ OI threshold GOOD")
            
        if vol_ratio > 2.0:
            print(f"   ⚠️  Volume ratio TOO HIGH! Should be 1.2-1.5x")
            issues_found.append(('unusual_activity', 'min_volume_ratio', 1.2))
        else:
            print(f"   ✅ Volume ratio GOOD")
            
        if min_score > 6:
            print(f"   ⚠️  Min score TOO HIGH! Should be 4-5")
            issues_found.append(('unusual_activity', 'min_score', 4.0))
        else:
            print(f"   ✅ Min score GOOD")
    else:
        print(f"   ❌ MONITOR IS DISABLED!")
        issues_found.append(('unusual_activity', 'enabled', True))
else:
    print(f"📊 UNUSUAL ACTIVITY MONITOR: ❌ NOT CONFIGURED")
    issues_found.append(('unusual_activity', 'missing', True))

print()

# Check Volume Spike Monitor
found_volume = False
for key in ['realtime_volume_spike_monitor', 'volume_spike_monitor']:
    if key in config:
        found_volume = True
        monitor = config[key]
        enabled = monitor.get('enabled', False)
        
        print(f"📊 VOLUME SPIKE MONITOR ({key}):")
        print(f"   Enabled: {enabled}")
        
        if enabled:
            thresholds = monitor.get('thresholds', {})
            spike_mult = thresholds.get('min_spike_multiple', 0)
            
            print(f"   Min Spike Multiple: {spike_mult}x")
            
            if spike_mult > 2.5:
                print(f"   ⚠️  Spike multiple TOO HIGH! Should be 1.3-2.0x")
                issues_found.append(('volume_spike', 'min_spike_multiple', 1.3))
            elif spike_mult > 2.0:
                print(f"   ✅ Spike multiple OK (could be lower for more alerts)")
            else:
                print(f"   ✅ Spike multiple GOOD")
        else:
            print(f"   ❌ MONITOR IS DISABLED!")
            issues_found.append(('volume_spike', 'enabled', True))
        break

if not found_volume:
    print(f"📊 VOLUME SPIKE MONITOR: ❌ NOT CONFIGURED")
    issues_found.append(('volume_spike', 'missing', True))

print()

# Check Momentum Signal Monitor
if 'momentum_signal_monitor' in config:
    monitor = config['momentum_signal_monitor']
    enabled = monitor.get('enabled', False)
    
    print(f"📊 MOMENTUM SIGNAL MONITOR:")
    print(f"   Enabled: {enabled}")
    
    if enabled:
        thresholds = monitor.get('thresholds', {})
        min_rvol = thresholds.get('min_rvol', 0)
        min_confluence = thresholds.get('min_confluence', 0)
        
        print(f"   Min RVOL: {min_rvol}x")
        print(f"   Min Confluence: {min_confluence} factors")
        
        if min_rvol > 1.8:
            print(f"   ⚠️  RVOL TOO HIGH! Should be 1.2-1.5x")
            issues_found.append(('momentum', 'min_rvol', 1.2))
        else:
            print(f"   ✅ RVOL GOOD")
            
        if min_confluence > 4:
            print(f"   ⚠️  Confluence TOO HIGH! Should be 3")
            issues_found.append(('momentum', 'min_confluence', 3))
        else:
            print(f"   ✅ Confluence GOOD")
    else:
        print(f"   ❌ MONITOR IS DISABLED!")
        issues_found.append(('momentum', 'enabled', True))
else:
    print(f"📊 MOMENTUM SIGNAL MONITOR: ❌ NOT CONFIGURED")
    issues_found.append(('momentum', 'missing', True))

print()
print("="*70)

if issues_found:
    print(f"⚠️  FOUND {len(issues_found)} ISSUES!")
    print("="*70)
    print("\n💡 RECOMMENDATIONS:")
    
    for issue in issues_found:
        monitor, field, value = issue
        if field == 'missing':
            print(f"\n   ❌ {monitor.upper()} monitor not in config!")
            print(f"      → Add monitor configuration to config.yaml")
        elif field == 'enabled':
            print(f"\n   ❌ {monitor.upper()} monitor is disabled!")
            print(f"      → Set 'enabled: true' in config.yaml")
        else:
            print(f"\n   ⚠️  {monitor.upper()} - {field} too strict")
            print(f"      → Recommended: {value}")
    
    print(f"\n📝 To fix automatically, I can update your config.yaml")
    print(f"   This will lower thresholds to catch more alerts")
    print(f"   (You can always tune them up later)")
    
else:
    print(f"✅ ALL THRESHOLDS LOOK GOOD!")
    print("="*70)
    print(f"\n🤔 If monitors are running but not alerting:")
    print(f"   1. Market conditions may not be triggering alerts yet")
    print(f"   2. Pre-market has less activity than market hours")
    print(f"   3. Check logs: tail -50 backend/logs/always_on_trader.log")
    print(f"   4. Wait until 9:30 AM market open for more action")

print()
print("="*70)
print("NEXT STEPS:")
print("="*70)
print()
print("1. Check if monitors are scanning:")
print("   tail -30 backend/logs/always_on_trader.log | grep 'scan\\|check'")
print()
print("2. See if they're finding anything:")
print("   grep 'detected\\|found\\|Alert' backend/logs/always_on_trader.log | tail -20")
print()
print("3. Check Discord webhooks are set:")
print("   grep 'DISCORD_UNUSUAL\\|DISCORD_VOLUME\\|DISCORD_MOMENTUM' .env")
print()
print("="*70)
