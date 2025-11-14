#!/bin/bash
#
# validate_monitors.sh - Verify monitors respect config.yaml enabled flags
# Usage: ./validate_monitors.sh
#

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

LOG_FILE="backend/logs/always_on_trader.log"
CONFIG_FILE="backend/config/config.yaml"

echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}    MONITOR VALIDATION - Config vs Reality${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""

# Check files exist
if [ ! -f "$LOG_FILE" ]; then
    echo -e "${RED}✗ Log file not found: $LOG_FILE${NC}"
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}✗ Config file not found: $CONFIG_FILE${NC}"
    exit 1
fi

echo -e "${YELLOW}Checking monitor status...${NC}"
echo ""

# Function to check monitor
check_monitor() {
    local monitor_name=$1
    local config_key=$2
    local log_pattern=$3
    
    # Check config
    enabled=$(grep -A 1 "^${config_key}:" "$CONFIG_FILE" | grep "enabled:" | head -1 | grep -o "true\|false" || echo "not_found")
    
    # Check if initialized in logs (last 50 lines)
    if tail -50 "$LOG_FILE" | grep -q "$log_pattern.*initialized"; then
        initialized="YES"
    else
        initialized="NO"
    fi
    
    # Determine status
    if [ "$enabled" = "true" ] && [ "$initialized" = "YES" ]; then
        status="${GREEN}✓ OK${NC}"
        result="Enabled & Running"
    elif [ "$enabled" = "false" ] && [ "$initialized" = "NO" ]; then
        status="${GREEN}✓ OK${NC}"
        result="Disabled & Stopped"
    elif [ "$enabled" = "true" ] && [ "$initialized" = "NO" ]; then
        status="${RED}✗ ERROR${NC}"
        result="Should be enabled but not running"
    elif [ "$enabled" = "false" ] && [ "$initialized" = "YES" ]; then
        status="${RED}✗ ERROR${NC}"
        result="Should be disabled but still running!"
    else
        status="${YELLOW}? UNKNOWN${NC}"
        result="Config: $enabled, Initialized: $initialized"
    fi
    
    printf "%-30s %s %s\n" "$monitor_name" "$(echo -e "$status")" "$result"
}

# Check all monitors
echo "Monitor Status:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_monitor "Unusual Activity" "unusual_activity_monitor" "Unusual Activity Monitor"
check_monitor "0DTE Gamma" "odte_gamma_monitor" "0DTE Gamma Monitor"
check_monitor "Wall Strength" "wall_strength_monitor" "Wall Strength Monitor"
check_monitor "Relative Strength" "relative_strength_monitor" "Relative Strength Monitor"
check_monitor "Opening Range" "opening_range_monitor" "Opening Range Monitor"
check_monitor "Momentum Signal" "momentum_signal_monitor" "Momentum Signal Monitor"
check_monitor "Volume Spike (RT)" "realtime_volume_spike_monitor" "Volume Spike Monitor"
check_monitor "Extended Hours Vol" "extended_hours_volume_monitor" "Extended Hours.*Monitor"
check_monitor "Market Impact" "market_impact_monitor" "Market Impact Monitor"
check_monitor "OpenAI Monitor" "openai_monitor" "OpenAI.*Monitor"
check_monitor "Earnings" "earnings_monitor" "Earnings Monitor"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo -e "${BLUE}Checking for active monitor loops (last 100 log lines)...${NC}"

# Check for recent monitor activity
if tail -100 "$LOG_FILE" | grep -q "RS Check"; then
    echo -e "${RED}✗ Relative Strength monitor is actively checking${NC}"
fi

if tail -100 "$LOG_FILE" | grep -q "Volume spike detected"; then
    echo -e "${RED}✗ Volume Spike monitor is actively checking${NC}"
fi

if tail -100 "$LOG_FILE" | grep -q "Opening range"; then
    echo -e "${RED}✗ Opening Range monitor is actively checking${NC}"
fi

echo -e "${GREEN}✓ Validation complete${NC}"
echo ""
echo "If you see any ${RED}✗ ERROR${NC} status, the fix didn't work properly."
echo "All monitors should show ${GREEN}✓ OK${NC}"
