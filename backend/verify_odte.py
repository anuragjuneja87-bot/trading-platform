#!/usr/bin/env python3
"""
Quick verification script for ODTE Gamma Wall Alert fixes
Run after deploying fixed files
"""
from dotenv import load_dotenv
load_dotenv()
import os
import sys
from pathlib import Path
import requests

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def check(condition, success_msg, fail_msg):
    """Print check result"""
    if condition:
        print(f"{GREEN}✅ {success_msg}{RESET}")
        return True
    else:
        print(f"{RED}❌ {fail_msg}{RESET}")
        return False

def warn(msg):
    """Print warning"""
    print(f"{YELLOW}⚠️  {msg}{RESET}")

print("\n" + "="*70)
print("🔍 ODTE GAMMA WALL ALERT - VERIFICATION SCRIPT")
print("="*70 + "\n")

checks_passed = 0
checks_total = 0

# Check 1: ThetaData Terminal
print("1️⃣ Checking ThetaData Terminal...")
checks_total += 1
try:
    response = requests.get("http://localhost:25503/v3", timeout=5)
    if response.status_code in [200, 404, 410]:
        if check(True, "ThetaData Terminal is running on port 25503", ""):
            checks_passed += 1
    else:
        warn(f"ThetaData returned unexpected status: {response.status_code}")
        check(False, "", "ThetaData not responding correctly")
except:
    check(False, "", "ThetaData Terminal not running on port 25503")
    print(f"    💡 Start it: cd ~/ThetaData && java -jar ThetaTerminal.jar &")

# Check 2: Discord Webhook
print("\n2️⃣ Checking Discord Webhook...")
checks_total += 1
webhook = os.getenv('DISCORD_ODTE_LEVELS')
if check(webhook is not None, "DISCORD_ODTE_LEVELS environment variable is set", 
         "DISCORD_ODTE_LEVELS not found in environment"):
    checks_passed += 1
    if webhook.startswith('https://discord.com/api/webhooks/'):
        print(f"    📡 Webhook: {webhook[:50]}...")
    else:
        warn("Webhook doesn't look like a Discord URL")

# Check 3: Fixed files exist
print("\n3️⃣ Checking fixed files...")
checks_total += 1
backend_path = Path(__file__).parent
analyzer_path = backend_path / 'analyzers' / 'enhanced_professional_analyzer.py'
monitor_path = backend_path / 'monitors' / 'wall_strength_monitor.py'

files_exist = analyzer_path.exists() and monitor_path.exists()
if check(files_exist, "Both fixed files are present", "Fixed files not found"):
    checks_passed += 1

# Check 4: Verify the bug fix
print("\n4️⃣ Checking bug fix in enhanced_professional_analyzer.py...")
checks_total += 1
if analyzer_path.exists():
    with open(analyzer_path, 'r') as f:
        content = f.read()
        has_bug = 'or not True' in content
        if check(not has_bug, "Bug 'or not True' has been removed", 
                 "BUG STILL PRESENT: 'or not True' found in file"):
            checks_passed += 1
        else:
            print(f"    🔧 Fix required: Remove 'or not True' from line 354")

# Check 5: Verify cooldown changes
print("\n5️⃣ Checking cooldown settings in wall_strength_monitor.py...")
checks_total += 1
if monitor_path.exists():
    with open(monitor_path, 'r') as f:
        content = f.read()
        has_old_cooldown = "'WALL_BUILDING': 10" in content
        has_new_cooldown = "'WALL_BUILDING': 5" in content
        
        if check(has_new_cooldown and not has_old_cooldown, 
                "Cooldowns updated to 5/5/3 minutes", 
                "Cooldowns still showing old values"):
            checks_passed += 1
        else:
            if has_old_cooldown:
                print(f"    🔧 Fix required: Update cooldown from 10 to 5 minutes")

# Check 6: Watchlist
print("\n6️⃣ Checking watchlist...")
checks_total += 1
watchlist_path = backend_path / 'data' / 'watchlist.txt'
if watchlist_path.exists():
    with open(watchlist_path, 'r') as f:
        symbols = [line.strip() for line in f if line.strip()]
    if check(len(symbols) > 0, f"Watchlist has {len(symbols)} symbols", 
             "Watchlist is empty"):
        checks_passed += 1
        print(f"    📋 Symbols: {', '.join(symbols[:5])}{'...' if len(symbols) > 5 else ''}")
else:
    check(False, "", "Watchlist file not found")

# Check 7: App running
print("\n7️⃣ Checking if app is running...")
checks_total += 1
try:
    response = requests.get("http://localhost:5001/api/health", timeout=3)
    if response.status_code == 200:
        data = response.json()
        if check(True, "App is running and responding", ""):
            checks_passed += 1
            print(f"    📊 Status: {data.get('status', 'unknown')}")
    else:
        check(False, "", "App returned unexpected status")
except:
    check(False, "", "App is not running on port 5001")
    print(f"    💡 Start it: cd ~/Desktop/trading-platform/backend && python3 app.py")

# Summary
print("\n" + "="*70)
print(f"📊 VERIFICATION SUMMARY")
print("="*70)
print(f"Checks passed: {checks_passed}/{checks_total}")

if checks_passed == checks_total:
    print(f"\n{GREEN}✅ ALL CHECKS PASSED!{RESET}")
    print(f"\n🎯 Next steps:")
    print(f"   1. Monitor logs: tail -f logs/always_on_trader.log | grep -i 'gamma\\|wall'")
    print(f"   2. Watch for alerts in Discord #odte-levels channel")
    print(f"   3. First alert expected within 1-2 hours (market dependent)")
elif checks_passed >= checks_total - 2:
    print(f"\n{YELLOW}⚠️  MOSTLY READY - Fix remaining issues{RESET}")
    print(f"\n🔧 Review failed checks above and fix them")
else:
    print(f"\n{RED}❌ MULTIPLE ISSUES FOUND{RESET}")
    print(f"\n🚨 Action required:")
    print(f"   1. Fix all failed checks above")
    print(f"   2. Re-run this script to verify")
    print(f"   3. Review DEPLOYMENT_GUIDE.md for details")

print("\n" + "="*70 + "\n")
